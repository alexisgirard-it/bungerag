"""LA fonction generate() de BungeRAG - point de branchement unique des LLM.

Tout le projet appelle generate(prompt, system) sans savoir quel modele
tourne derriere. Backend par variable d'env (LLM_BACKEND) ou par appel
(backend=), temperature 0 partout.

ROTATION GEMINI : le free tier reel est de ~20 requetes/JOUR PAR MODELE
(decouvert le 06/07/2026 en plein vol, tres loin des ~1500 'indicatifs').
Le quota etant par modele, on fait tourner une liste de modeles gratuits :
bucket epuise (429) -> modele suivant. GEMINI_LAST_MODEL garde la trace
de qui a effectivement repondu.

Backend cerebras (gpt-oss-120b) : utilise pour les taches utilitaires
(traduction des questions) afin de preserver le quota Gemini pour les
reponses - et c'est aussi le juge d'eval (voir eval_ragas.py).
"""

import logging
import os
from threading import Lock
import time
from pathlib import Path

LOGGER = logging.getLogger(__name__)
TRANSIENT_GEMINI_CODES = {429, 500, 503, 504}
COOLDOWN_TRANSIENT_SECONDS = 300.0
COOLDOWN_QUOTA_SECONDS = 1800.0
_MODEL_COOLDOWN: dict[str, float] = {}
_COOLDOWN_LOCK = Lock()

# Le chargement de .env est un confort local, pas une condition d'import. Cela
# permet aux tests unitaires purs d'importer le pipeline avec le seul stdlib.
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - depend de l'environnement d'execution
    load_dotenv = None
if load_dotenv is not None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

GEMINI_MODELS = os.environ.get(
    "GEMINI_MODELS",
    "gemini-3.5-flash,gemini-2.5-flash,gemini-3-flash-preview,"
    "gemini-2.5-flash-lite,gemini-3.1-flash-lite").split(",")
GEMINI_LAST_MODEL = None

_gem_client = None
_oa_client = None

def _gemini_once(model, prompt, system, max_tokens, thinking_off=True):
    from google.genai import types
    config = types.GenerateContentConfig(
        temperature=0,
        max_output_tokens=max_tokens,
        system_instruction=system or None,
        # les tokens de "reflexion" se decomptent de max_output_tokens
        # et du quota -> coupes quand le modele le permet
        thinking_config=types.ThinkingConfig(thinking_budget=0)
        if thinking_off else None,
    )
    return _gem_client.models.generate_content(
        model=model, contents=prompt, config=config).text.strip()

def _gemini(prompt, system, max_tokens):
    global _gem_client, GEMINI_LAST_MODEL
    from google import genai
    from google.genai import errors
    if _gem_client is None:
        _gem_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    for cycle in range(3):
        for model in GEMINI_MODELS:
            try:
                try:
                    text = _gemini_once(model, prompt, system, max_tokens)
                except errors.APIError as e:
                    # certains modeles refusent thinking_budget=0 -> sans
                    if e.code == 400 and "think" in str(e).lower():
                        text = _gemini_once(model, prompt, system, max_tokens,
                                            thinking_off=False)
                    else:
                        raise
                GEMINI_LAST_MODEL = model
                return text
            except errors.APIError as e:
                if e.code in (429, 503):  # bucket epuise / surcharge -> suivant
                    continue
                raise
        print("  [tous les modeles Gemini a 429, pause 60s]", flush=True)
        time.sleep(60)
    raise RuntimeError("quota Gemini epuise sur tous les modeles")

def _cerebras(prompt, system, max_tokens):
    global _oa_client
    from openai import OpenAI
    if _oa_client is None:
        _oa_client = OpenAI(base_url="https://api.cerebras.ai/v1",
                            api_key=os.environ["CEREBRAS_API_KEY"],
                            max_retries=8, timeout=120)
    msgs = ([{"role": "system", "content": system}] if system else []) \
        + [{"role": "user", "content": prompt}]
    from openai import RateLimitError
    for attempt in range(4):  # en plus des retries internes du client
        try:
            r = _oa_client.chat.completions.create(
                model=os.environ.get("CEREBRAS_MODEL", "gpt-oss-120b"),
                messages=msgs, max_completion_tokens=max_tokens, temperature=0)
            return (r.choices[0].message.content or "").strip()
        except RateLimitError:
            if attempt == 3:
                raise
            wait = 60 * (attempt + 1)
            print(f"  [cerebras sature, retry dans {wait}s]", flush=True)
            time.sleep(wait)

def _ollama(prompt, system, max_tokens):
    """Backend 100% local via l'API native Ollama.
    num_ctx=8192 obligatoire : nos prompts RAG font ~4-5k tokens et le
    defaut d'Ollama (4096) TRONQUERAIT silencieusement les extraits.
    think=False : pas de mode reflexion, on veut du deterministe rapide."""
    import requests
    msgs = ([{"role": "system", "content": system}] if system else []) \
        + [{"role": "user", "content": prompt}]
    r = requests.post("http://localhost:11434/api/chat", json={
        "model": os.environ.get("OLLAMA_MODEL", "qwen3.5:9b"),
        "messages": msgs, "stream": False, "think": False,
        # keep_alive 0 : decharge le modele apres chaque generation ->
        # libere ses ~7 Go pendant la phase de retrieval (sinon macOS
        # tue le processus python sous pression memoire sur 16 Go)
        "keep_alive": os.environ.get("OLLAMA_KEEP_ALIVE", "0"),
        "options": {"temperature": 0, "num_ctx": 8192,
                    "num_predict": max_tokens},
    }, timeout=600)
    r.raise_for_status()
    return r.json()["message"]["content"].strip()

def parse_gemini_models(backend: str) -> list[str]:
    segment = next(
        (seg.strip() for seg in backend.split("|") if seg.strip().startswith("gemini/")),
        backend,
    )
    spec = segment.split("/", 1)[1]
    models = [item.strip() for item in spec.split(",") if item.strip()]
    if not models:
        raise ValueError(f"backend Gemini invalide : {backend!r}")
    return models


def _call_gemini_model(client, model, prompt, system, max_tokens, *, structured):
    from google.genai import errors, types

    # Borner la réflexion sur les modèles pensants pour éviter la troncature du JSON.
    supports_thinking = "lite" not in model
    thinking_budget = 512 if structured else 0
    budgeted_tokens = max_tokens + thinking_budget

    def invoke(with_thinking: bool):
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
            max_output_tokens=budgeted_tokens if with_thinking else max_tokens,
            response_mime_type="application/json" if structured else "text/plain",
            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget)
            if with_thinking
            else None,
        )
        return client.models.generate_content(
            model=model, contents=prompt, config=config
        )

    if not supports_thinking:
        response = invoke(with_thinking=False)
    else:
        try:
            response = invoke(with_thinking=True)
        except errors.APIError as exc:
            if exc.code == 400:
                response = invoke(with_thinking=False)
            else:
                raise
    return response.model_version or model, (response.text or "")


def _cooldown_seconds(code: int | None) -> float:
    return COOLDOWN_QUOTA_SECONDS if code == 429 else COOLDOWN_TRANSIENT_SECONDS


def _mark_cooldown(model: str, code: int | None = None) -> None:
    until = time.monotonic() + _cooldown_seconds(code)
    with _COOLDOWN_LOCK:
        _MODEL_COOLDOWN[model] = max(_MODEL_COOLDOWN.get(model, 0.0), until)


def _active_cascade(models: list[str]) -> list[str]:
    now = time.monotonic()
    with _COOLDOWN_LOCK:
        available = [m for m in models if _MODEL_COOLDOWN.get(m, 0.0) <= now]
    # Si tous les modèles sont en pause, on réessaie la liste complète sans bloquer.
    return available or list(models)


def named_gemini(prompt, system, backend, max_tokens, *, structured):
    """Appelle un modèle Gemini ou une cascade ordonnée avec coupe-circuit temporaire."""
    global GEMINI_LAST_MODEL
    from google import genai
    from google.genai import errors, types

    models = parse_gemini_models(backend)
    cascade = len(models) > 1
    candidates = _active_cascade(models) if cascade else models
    last_error = None
    for index, model in enumerate(candidates):
        remaining = index + 1 < len(candidates)
        timeout_ms = 15_000 if (cascade and remaining) else (30_000 if cascade else 60_000)
        options = types.HttpOptions(
            timeout=timeout_ms,
            retry_options=types.HttpRetryOptions(attempts=1 if cascade else 2),
        )
        try:
            with genai.Client(
                api_key=os.environ["GEMINI_API_KEY"], http_options=options
            ) as client:
                version, text = _call_gemini_model(
                    client, model, prompt, system, max_tokens, structured=structured
                )
            if not text.strip() and remaining:
                _mark_cooldown(model)
                LOGGER.warning("gemini_empty_response model=%s -> cooldown", model)
                continue
            GEMINI_LAST_MODEL = version
            return text
        except errors.APIError as exc:
            last_error = exc
            if remaining and exc.code in TRANSIENT_GEMINI_CODES:
                _mark_cooldown(model, exc.code)
                LOGGER.warning(
                    "gemini_transient_error model=%s code=%s -> cooldown",
                    model,
                    exc.code,
                )
                continue
            raise
        except (TimeoutError, OSError) as exc:
            last_error = exc
            if remaining:
                _mark_cooldown(model)
                LOGGER.warning("gemini_network_error model=%s -> cooldown", model)
                continue
            raise
    if last_error is not None:
        raise last_error
    return ""


OPENAI_COMPAT_PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "mistral": ("https://api.mistral.ai/v1", "MISTRAL_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
}


def _call_openai_compat(provider: str, model: str, prompt: str, system: str, max_tokens: int, *, structured: bool) -> str:
    from openai import OpenAI

    base_url, env_key = OPENAI_COMPAT_PROVIDERS[provider]
    api_key = os.environ.get(env_key, "").strip()
    if not api_key:
        raise KeyError(env_key)
    client = OpenAI(base_url=base_url, api_key=api_key, max_retries=1, timeout=25)
    msgs = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    kwargs = {"model": model, "messages": msgs, "max_tokens": max_tokens, "temperature": 0}
    if structured:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    return (resp.choices[0].message.content or "").strip()


def _call_provider_segment(segment: str, prompt: str, system: str, max_tokens: int, *, structured: bool) -> str:
    global GEMINI_LAST_MODEL
    if segment.startswith("gemini/"):
        if not os.environ.get("GEMINI_API_KEY", "").strip():
            raise KeyError("GEMINI_API_KEY")
        return named_gemini(prompt, system, segment, max_tokens, structured=structured)
    provider, _, spec = segment.partition("/")
    if provider not in OPENAI_COMPAT_PROVIDERS:
        raise NotImplementedError(f"fournisseur inconnu : {segment!r}")
    models = [m.strip() for m in spec.split(",") if m.strip()]
    candidates = _active_cascade(models) if len(models) > 1 else models
    last_error = None
    for index, model in enumerate(candidates):
        remaining = index + 1 < len(candidates)
        try:
            text = _call_openai_compat(
                provider, model, prompt, system, max_tokens, structured=structured
            )
            if not text.strip() and remaining:
                _mark_cooldown(f"{provider}/{model}")
                continue
            GEMINI_LAST_MODEL = f"{provider}/{model}"
            return text
        except KeyError:
            raise
        except Exception as exc:
            last_error = exc
            code = getattr(exc, "status_code", None)
            if remaining and (code in TRANSIENT_GEMINI_CODES or isinstance(exc, (TimeoutError, OSError))):
                _mark_cooldown(f"{provider}/{model}", code)
                continue
            raise
    if last_error is not None:
        raise last_error
    return ""


def _call_multi_provider(backend: str, prompt: str, system: str, max_tokens: int, *, structured: bool) -> str:
    segments = [seg.strip() for seg in backend.split("|") if seg.strip()]
    last_error = None
    for index, segment in enumerate(segments):
        remaining = index + 1 < len(segments)
        try:
            return _call_provider_segment(
                segment, prompt, system, max_tokens, structured=structured
            )
        except KeyError:
            # Fournisseur de secours optionnel sans clé configurée -> ignorer silencieusement.
            if remaining:
                continue
            if last_error is not None:
                raise last_error
            raise
        except Exception as exc:
            last_error = exc
            code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if remaining and (
                code in TRANSIENT_GEMINI_CODES
                or isinstance(exc, (TimeoutError, OSError))
            ):
                LOGGER.warning("provider_failover segment=%s -> next", segment)
                continue
            raise
    if last_error is not None:
        raise last_error
    return ""


def generate_json(prompt, system, backend, max_tokens):
    if "|" in backend or backend.startswith(("gemini/", "groq/", "mistral/", "openrouter/")):
        return _call_multi_provider(backend, prompt, system, max_tokens, structured=True)
    return generate(prompt, system=system, backend=backend, max_tokens=max_tokens)


def generate(prompt, system=None, max_tokens=2048, backend=None):
    backend = backend or os.environ.get("LLM_BACKEND", "gemini")
    if "|" in backend or backend.startswith(("gemini/", "groq/", "mistral/", "openrouter/")):
        return _call_multi_provider(backend, prompt, system or "", max_tokens, structured=False)
    if backend == "gemini":
        return _gemini(prompt, system, max_tokens)
    if backend == "cerebras":
        return _cerebras(prompt, system, max_tokens)
    if backend == "ollama":
        return _ollama(prompt, system, max_tokens)
    raise NotImplementedError(f"backend '{backend}' : prevu pour une phase future")
