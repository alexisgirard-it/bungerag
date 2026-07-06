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

import os
import time
from pathlib import Path

from dotenv import load_dotenv

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
    r = _oa_client.chat.completions.create(
        model=os.environ.get("CEREBRAS_MODEL", "gpt-oss-120b"),
        messages=msgs, max_completion_tokens=max_tokens, temperature=0)
    return (r.choices[0].message.content or "").strip()

def generate(prompt, system=None, max_tokens=2048, backend=None):
    backend = backend or os.environ.get("LLM_BACKEND", "gemini")
    if backend == "gemini":
        return _gemini(prompt, system, max_tokens)
    if backend == "cerebras":
        return _cerebras(prompt, system, max_tokens)
    raise NotImplementedError(f"backend '{backend}' : prevu pour une phase future")
