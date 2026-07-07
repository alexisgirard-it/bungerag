"""Publication de la demo : dataset prive (index) + Space public (app).

Ce que ca fait :
 1. dataset PRIVE alexisgirard/bungerag-index <- index/lancedb (64 Mo).
    Le texte integral des livres reste inaccessible au public.
 2. Space public alexisgirard/bungerag <- space/ + les modules src/ du
    pipeline (jamais le corpus, jamais l'eval, jamais le .env).
 3. secrets du Space : GEMINI_API_KEY, CEREBRAS_API_KEY, HF_TOKEN
    (lus depuis .env — a faire TOURNER avant toute annonce publique).

Prerequis : HF_TOKEN (write) dans .env.
Usage : .venv/bin/python src/push_space.py
"""

import os
import shutil
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

USER = "alexisgirard"
DATASET = f"{USER}/bungerag-index"
SPACE = f"{USER}/bungerag"
MODULES = ["search.py", "rerank.py", "retrieve.py", "rag.py", "generate.py", "decompose.py"]

def main():
    api = HfApi(token=os.environ["HF_TOKEN"])
    who = api.whoami()
    print(f"connecte en tant que : {who['name']}")

    # 1. dataset prive : l'index
    api.create_repo(DATASET, repo_type="dataset", private=True, exist_ok=True)
    api.upload_folder(folder_path=ROOT / "index" / "lancedb",
                      path_in_repo="lancedb", repo_id=DATASET,
                      repo_type="dataset")
    print(f"index pousse -> {DATASET} (prive)")

    # 2. le Space : app + modules du pipeline
    api.create_repo(SPACE, repo_type="space", space_sdk="gradio", exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # liste blanche stricte : rien d'autre ne part sur le Space public
        for name in ("app.py", "README.md", "requirements.txt"):
            shutil.copy2(ROOT / "space" / name, tmp / name)
        (tmp / "src").mkdir()
        for m in MODULES:
            shutil.copy2(ROOT / "src" / m, tmp / "src" / m)
        api.upload_folder(folder_path=tmp, repo_id=SPACE, repo_type="space")
    print(f"app poussee -> https://huggingface.co/spaces/{SPACE}")

    # 3. secrets + variables
    for name in ("GEMINI_API_KEY", "CEREBRAS_API_KEY", "HF_TOKEN"):
        api.add_space_secret(SPACE, name, os.environ[name])
    api.add_space_variable(SPACE, "GEMINI_MODELS", os.environ.get(
        "GEMINI_MODELS", "gemini-3.5-flash,gemini-2.5-flash,"
        "gemini-3-flash-preview,gemini-2.5-flash-lite,gemini-3.1-flash-lite"))
    api.add_space_variable(SPACE, "RAG_K_CANDIDATES", "12")
    api.add_space_variable(SPACE, "RAG_PANO_K", "8")  # 2 vCPU
    print("secrets + variables configures ; le Space build (~5-10 min)")

if __name__ == "__main__":
    main()
