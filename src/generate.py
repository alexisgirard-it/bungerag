"""LA fonction generate() de BungeRAG - point de branchement unique des LLM.

Tout le projet appelle generate(prompt, system) sans savoir quel modele
tourne derriere. Le backend se choisit par variable d'environnement :
  LLM_BACKEND=gemini (defaut) | ollama (phase 8) | groq (secours)
C'est l'abstraction anti vendor lock-in : changer de fournisseur = changer
une variable, zero ligne de code.

Temperature 0 partout : un RAG de citation doit etre deterministe.
"""

import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_client = None

def _gemini(prompt, system, max_tokens):
    global _client
    from google import genai
    from google.genai import types, errors
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(
        temperature=0,
        max_output_tokens=max_tokens,
        system_instruction=system or None,
        # les tokens de "reflexion" de Gemini 2.5 se decomptent de
        # max_output_tokens (reponses tronquees) et du quota -> coupes
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    # backoff : le free tier repond 429 quand on depasse ~10 req/min
    for attempt in range(4):
        try:
            r = _client.models.generate_content(
                model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=prompt, config=config)
            return r.text.strip()
        except errors.APIError as e:
            if e.code in (429, 503) and attempt < 3:
                wait = 15 * (attempt + 1)
                print(f"  [gemini {e.code}, retry dans {wait}s]", flush=True)
                time.sleep(wait)
            else:
                raise

def generate(prompt, system=None, max_tokens=2048):
    backend = os.environ.get("LLM_BACKEND", "gemini")
    if backend == "gemini":
        return _gemini(prompt, system, max_tokens)
    raise NotImplementedError(f"backend '{backend}' : prevu pour une phase future")
