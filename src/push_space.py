"""Publication sûre de l'index privé et de la démo publique BungeRAG.

Deux jetons Hugging Face distincts sont obligatoires :

* ``HF_WRITE_TOKEN`` reste uniquement sur la machine de déploiement ;
* ``HF_READ_TOKEN`` est limité en lecture au dataset privé et devient le
  secret ``HF_TOKEN`` du Space.

Le bundle public est construit par liste blanche. Le corpus, les caches,
les évaluations et le jeton d'écriture ne peuvent donc pas être publiés par
ce script.
"""

from __future__ import annotations

import os
import json
import shutil
import tempfile
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

USER = "alexisgirard"
DATASET = f"{USER}/bungerag-index"
SPACE = f"{USER}/bungerag"

SPACE_FILES = (
    "app.py",
    "README.md",
    "requirements.txt",
    "presenter.py",
    "runtime.py",
    "theme.py",
    "styles.css",
)
MODULES = (
    "search.py",
    "rerank.py",
    "retrieve.py",
    "rag.py",
    "generate.py",
    "decompose.py",
    "config.py",
    "citations.py",
    "schemas.py",
    "output_guard.py",
)


def required_secret(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"secret requis absent : {name}")
    return value


def build_space_bundle(destination: Path) -> list[str]:
    """Copie exclusivement les fichiers publics attendus dans destination."""

    destination.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in SPACE_FILES:
        source = ROOT / "space" / name
        if not source.is_file():
            raise RuntimeError(f"fichier public requis absent : {source}")
        shutil.copy2(source, destination / name)
        copied.append(name)

    target_src = destination / "src"
    target_src.mkdir()
    for name in MODULES:
        source = ROOT / "src" / name
        if not source.exists():
            raise RuntimeError(f"module runtime absent : {source}")
        shutil.copy2(source, target_src / name)
        copied.append(f"src/{name}")
    return copied


def stale_remote_files(remote_files: list[str], copied: list[str]) -> list[str]:
    """Fichiers à retirer du Space avant publication de la liste blanche."""
    allowed = set(copied) | {".gitattributes"}
    return sorted(set(remote_files) - allowed)


def validate_local_index() -> None:
    index_dir = ROOT / "index"
    manifest_path = index_dir / "manifest-bunge_512.json"
    if not (index_dir / "lancedb").is_dir() or not manifest_path.is_file():
        raise RuntimeError("index 512 ou manifeste vérifié absent")
    manifest = json.loads(manifest_path.read_text())
    required = {"table", "filtered", "exclusions_sha256", "embedding_revision"}
    missing = sorted(required - manifest.keys())
    if missing or manifest.get("table") != "bunge_512" or manifest.get("filtered") is not True:
        detail = f"champs absents {missing}" if missing else "état incohérent"
        raise RuntimeError(f"manifeste d'index invalide : {detail}")


def main() -> None:
    from huggingface_hub import HfApi

    # Tout ce qui peut échouer localement est validé avant le premier appel réseau.
    secrets = {
        name: required_secret(name)
        for name in (
            "HF_WRITE_TOKEN", "HF_READ_TOKEN", "GEMINI_API_KEY", "CEREBRAS_API_KEY"
        )
    }
    write_token = secrets["HF_WRITE_TOKEN"]
    read_token = secrets["HF_READ_TOKEN"]
    if write_token == read_token:
        raise RuntimeError(
            "HF_WRITE_TOKEN et HF_READ_TOKEN doivent être deux jetons distincts"
        )

    validate_local_index()
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp)
        copied = build_space_bundle(bundle)

        api = HfApi(token=write_token)
        who = api.whoami()
        print(f"connecté en tant que : {who['name']}")

        # 1. L'index reste dans un dataset privé. Le commit obtenu est épinglé
        # dans le Space pour que le runtime ne télécharge jamais un état mouvant.
        api.create_repo(DATASET, repo_type="dataset", private=True, exist_ok=True)
        api.upload_folder(
            folder_path=ROOT / "index",
            path_in_repo=".",
            repo_id=DATASET,
            repo_type="dataset",
            ignore_patterns=("*.lock", "*.tmp"),
        )
        index_revision = api.repo_info(DATASET, repo_type="dataset").sha
        read_api = HfApi(token=read_token)
        readable = read_api.repo_info(
            DATASET,
            repo_type="dataset",
            revision=index_revision,
        )
        if readable.sha != index_revision:
            raise RuntimeError("le jeton de lecture ne voit pas la révision publiée")
        print(f"index privé publié : {DATASET}@{index_revision[:12]}")

        # 2. L'application publique est synchronisée exactement avec la liste
        # blanche : les anciens fichiers distants hors bundle sont supprimés.
        api.create_repo(SPACE, repo_type="space", space_sdk="gradio", exist_ok=True)
        remote_before = api.list_repo_files(SPACE, repo_type="space")
        stale = stale_remote_files(remote_before, copied)
        if stale:
            api.delete_files(
                SPACE,
                stale,
                repo_type="space",
                commit_message="security: remove files outside public allowlist",
            )

        # Installer le jeton read-only et la révision avant de déclencher le
        # build du nouveau code évite tout démarrage avec l'ancien secret HF.
        api.add_space_secret(SPACE, "HF_TOKEN", read_token)
        for name in ("GEMINI_API_KEY", "CEREBRAS_API_KEY"):
            api.add_space_secret(SPACE, name, secrets[name])
        api.add_space_variable(SPACE, "INDEX_REVISION", index_revision)
        api.add_space_variable(SPACE, "RAG_PROFILE", "public_v1")
        api.add_space_variable(
            SPACE,
            "GEMINI_MODELS",
            os.environ.get(
                "GEMINI_MODELS",
                "gemini-3.5-flash,gemini-2.5-flash,gemini-3-flash-preview,"
                "gemini-2.5-flash-lite,gemini-3.1-flash-lite",
            ),
        )
        api.upload_folder(folder_path=bundle, repo_id=SPACE, repo_type="space")
        remote_after = set(api.list_repo_files(SPACE, repo_type="space"))
        expected = set(copied) | ({".gitattributes"} & remote_after)
        if remote_after != expected:
            unexpected = sorted(remote_after - expected)
            missing = sorted(set(copied) - remote_after)
            raise RuntimeError(
                f"bundle distant incohérent : extras={unexpected}, absents={missing}"
            )
        print(
            f"bundle public ({len(copied)} fichiers) -> "
            f"https://huggingface.co/spaces/{SPACE}"
        )

        print("secrets minimaux et révision d'index configurés ; build du Space lancé")


if __name__ == "__main__":
    main()
