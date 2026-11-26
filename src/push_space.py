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

import hashlib
import os
import sqlite3
from contextlib import closing
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
    "reader.py",
    "runtime.py",
    "theme.py",
    "styles.css",
)
MODULES = (
    "search.py",
    "library.py",
    "referentiel.json",
    "workshop.py",
    "definitions.py",
    "evidence.py",
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
    if not (index_dir / "provenance-512.sqlite").is_file():
        raise RuntimeError("Construire la concordance avec src/build_provenance.py")
    manifest = json.loads(manifest_path.read_text())
    required = {"table", "filtered", "exclusions_sha256", "embedding_revision"}
    missing = sorted(required - manifest.keys())
    if (
        missing
        or manifest.get("table") != "bunge_512"
        or manifest.get("filtered") is not True
    ):
        detail = f"champs absents {missing}" if missing else "état incohérent"
        raise RuntimeError(f"manifeste d'index invalide : {detail}")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git_blob(path: Path) -> str:
    content = path.read_bytes()
    header = f"blob {len(content)}".encode() + bytes(1)
    return hashlib.sha1(header + content).hexdigest()


def validate_library(index_dir: Path) -> Path:
    library = index_dir / "lecture.sqlite"
    with closing(
        sqlite3.connect(library.resolve().as_uri() + "?mode=ro", uri=True)
    ) as db:
        check = db.execute("PRAGMA quick_check").fetchone()
        source = db.execute("SELECT value FROM meta WHERE key='provenance'").fetchone()
        db.execute("SELECT uid FROM labels LIMIT 1").fetchone()
        db.execute("SELECT origin FROM mentions LIMIT 1").fetchone()
    if check != ("ok",) or source != (sha256(index_dir / "provenance-512.sqlite"),):
        raise RuntimeError(
            "L’index de lecture ne correspond pas à la concordance locale"
        )
    return library


def main() -> None:
    from huggingface_hub import CommitOperationAdd, HfApi

    from audit_reader import verify_catalogue
    from audit_workshop import verify_dossiers

    write_token = required_secret("HF_WRITE_TOKEN")
    read_token = required_secret("HF_READ_TOKEN")
    if write_token == read_token:
        raise RuntimeError("Les jetons de lecture et d’écriture doivent être distincts")

    validate_local_index()
    index_dir = ROOT / "index"
    library = validate_library(index_dir)
    verify_catalogue()
    verify_dossiers()
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp)
        copied = build_space_bundle(bundle)
        api = HfApi(token=write_token)
        reader = HfApi(token=read_token)
        state = api.dataset_info(DATASET, files_metadata=True)
        if not state.private:
            raise RuntimeError("Le dataset d’index doit être privé")
        indexed = {file.rfilename: file for file in state.siblings}
        manifest = "manifest-bunge_512.json"
        if indexed[manifest].blob_id != git_blob(index_dir / manifest):
            raise RuntimeError(
                "Le manifeste du dataset ne correspond pas à l’index local"
            )
        provenance = "provenance-512.sqlite"
        if indexed[provenance].lfs.sha256 != sha256(index_dir / provenance):
            raise RuntimeError(
                "La concordance distante ne correspond pas à la version locale"
            )

        live = api.space_info(SPACE, files_metadata=True)
        before = {file.rfilename: file.blob_id for file in live.siblings}
        stale = stale_remote_files(list(before), copied)
        if stale:
            raise RuntimeError(f"Fichiers publics hors liste blanche : {stale}")

        index_revision = state.sha
        digest = sha256(library)
        stored = indexed.get(library.name)
        if not stored or not stored.lfs or stored.lfs.sha256 != digest:
            commit = api.create_commit(
                DATASET,
                repo_type="dataset",
                parent_commit=state.sha,
                operations=[
                    CommitOperationAdd(
                        path_in_repo=library.name, path_or_fileobj=library
                    )
                ],
                commit_message="Indexer la bibliothèque par page et les renvois du Traité",
            )
            index_revision = commit.oid
        readable = reader.dataset_info(
            DATASET, revision=index_revision, files_metadata=True
        )
        published = next(
            file for file in readable.siblings if file.rfilename == library.name
        )
        if not readable.private or published.lfs.sha256 != digest:
            raise RuntimeError("La révision privée attendue est illisible")

        variables = api.get_space_variables(SPACE)
        if (
            "INDEX_REVISION" not in variables
            or variables["INDEX_REVISION"].value != index_revision
        ):
            api.add_space_variable(SPACE, "INDEX_REVISION", index_revision)
        expected = {name: git_blob(bundle / name) for name in copied}
        operations = [
            CommitOperationAdd(path_in_repo=name, path_or_fileobj=bundle / name)
            for name, digest in expected.items()
            if before.get(name) != digest
        ]
        space_revision = live.sha
        if operations:
            commit = api.create_commit(
                SPACE,
                repo_type="space",
                parent_commit=live.sha,
                operations=operations,
                commit_message="Publier BungeRAG V3 avec la recherche, l’atlas et l’atelier",
            )
            space_revision = commit.oid
        actual = api.space_info(SPACE, revision=space_revision, files_metadata=True)
        if {
            file.rfilename: file.blob_id
            for file in actual.siblings
            if file.rfilename != ".gitattributes"
        } != expected:
            raise RuntimeError("Le bundle public ne correspond pas à la liste blanche")
        if (
            "RAG_PROFILE" not in variables
            or variables["RAG_PROFILE"].value != "public_v3"
        ):
            api.add_space_variable(SPACE, "RAG_PROFILE", "public_v3")
        print(
            json.dumps(
                {
                    "space": space_revision,
                    "index": index_revision,
                    "previous_space": live.sha,
                    "previous_index": state.sha,
                }
            )
        )


if __name__ == "__main__":
    main()
