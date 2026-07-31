"""Empreinte et stockage reproductibles des exécutions d'évaluation."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


VALID_REFERENCE_STATUSES = {"verifiee-corpus", "validee-humain"}
STRICT_ABSTENTION_REASONS = {"pre-generation", "llm"}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources_sha256(root: Path, paths: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(paths):
        path = root / relative
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def git_commit(root: Path) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def validate_references(questions: list[dict]) -> None:
    invalid = [
        question["id"]
        for question in questions
        if question.get("type") == "contenu"
        and question.get("reference_status") not in VALID_REFERENCE_STATUSES
    ]
    if invalid:
        ids = ", ".join(f"q{value:02d}" for value in invalid)
        raise ValueError(f"références non validées : {ids}")


def is_strict_abstention(reason: object) -> bool:
    """Distingue un refus intellectuel d'un rejet par un garde-fou."""
    return reason in STRICT_ABSTENTION_REASONS


def index_identity(path: Path, expected_table: str) -> dict:
    """Retourne l'identité vérifiée de l'index utilisé par l'évaluation."""
    if not path.exists():
        raise FileNotFoundError(f"manifeste d'index absent : {path}")
    manifest = json.loads(path.read_text())
    required = {
        "table",
        "chunk_sha256",
        "rows_after_filtering",
        "embedding_model",
        "embedding_revision",
        "filtered",
        "exclusions_sha256",
    }
    missing = sorted(required - manifest.keys())
    if missing:
        raise ValueError(f"manifeste d'index incomplet : {missing}")
    if manifest["table"] != expected_table:
        raise ValueError(
            f"table d'index {manifest['table']} != configuration {expected_table}"
        )
    if manifest["filtered"] is not True:
        raise ValueError("l'index d'évaluation doit être filtré")
    return {
        "manifest_sha256": file_sha256(path),
        "table": manifest["table"],
        "chunk_sha256": manifest["chunk_sha256"],
        "rows_after_filtering": manifest["rows_after_filtering"],
        "embedding_model": manifest["embedding_model"],
        "embedding_revision": manifest["embedding_revision"],
        "exclusions_sha256": manifest["exclusions_sha256"],
    }


def build_metadata(
    *,
    root: Path,
    config,
    questions_path: Path,
    system_prompt: str,
    index_manifest_path: Path,
    runtime_identity: dict,
) -> dict:
    """Construit une empreinte sans secret de tout ce qui influe sur le run."""

    questions = [json.loads(line) for line in questions_path.open()]
    validate_references(questions)
    code_paths = (
        "src/config.py",
        "src/search.py",
        "src/rerank.py",
        "src/retrieve.py",
        "src/decompose.py",
        "src/rag.py",
        "src/generate.py",
        "src/citations.py",
        "src/schemas.py",
        "src/output_guard.py",
        "src/eval_run.py",
        "src/eval_ragas.py",
    )
    stable = {
        "schema_version": 1,
        "git_commit": git_commit(root),
        "source_sha256": sources_sha256(root, code_paths),
        "questions_sha256": file_sha256(questions_path),
        "system_prompt_sha256": hashlib.sha256(system_prompt.encode()).hexdigest(),
        "dependencies_sha256": file_sha256(root / "requirements.txt"),
        "config": config.public_dict(),
        "config_id": config.config_id,
        "index": index_identity(index_manifest_path, config.table),
        "runtime": runtime_identity,
        "question_count": len(questions),
        "validated_content_references": sum(
            question.get("type") == "contenu" for question in questions
        ),
    }
    run_id = hashlib.sha256(
        json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]
    return {
        **stable,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def prepare_run(
    *,
    root: Path,
    cache_root: Path,
    config,
    questions_path: Path,
    system_prompt: str,
    index_manifest_path: Path,
    runtime_identity: dict,
) -> tuple[Path, dict]:
    metadata = build_metadata(
        root=root,
        config=config,
        questions_path=questions_path,
        system_prompt=system_prompt,
        index_manifest_path=index_manifest_path,
        runtime_identity=runtime_identity,
    )
    run_dir = cache_root / "runs" / metadata["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = run_dir / "metadata.json"
    if metadata_path.exists():
        existing = json.loads(metadata_path.read_text())
        # created_at n'influe pas sur l'identité : le reste doit être identique.
        for key, value in metadata.items():
            if key != "created_at" and existing.get(key) != value:
                raise RuntimeError(f"cache incompatible pour le run {metadata['run_id']}")
        metadata = existing
    else:
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
        )
    return run_dir, metadata
