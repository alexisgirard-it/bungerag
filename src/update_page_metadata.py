"""Met à jour uniquement les pages d'un index dont les textes sont inchangés.

Le correctif de localisation du 31/07/2026 a laissé les 11 249 textes et
identifiants strictement identiques, mais corrigé 38 plages de pages. Refaire
les embeddings serait inutile : ce script vérifie d'abord l'égalité exacte de
chaque texte, puis modifie seulement ``page_start`` et ``page_end``.

Usage : .venv/bin/python src/update_page_metadata.py 512
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"
EMBEDDING_REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def changes_for(index_rows: list[dict], chunks: dict[str, dict], *,
                expected_missing: set[str] | None = None) -> list[dict]:
    """Valide l'invariant texte/ID et renvoie les seules pages à modifier."""

    expected_missing = expected_missing or set()
    if len(index_rows) + len(expected_missing) != len(chunks):
        raise ValueError(
            f"nombre de lignes différent : index={len(index_rows)}, "
            f"exclusions={len(expected_missing)}, chunks={len(chunks)}"
        )
    changes = []
    seen = set()
    for row in index_rows:
        chunk_id = row["chunk_id"]
        if chunk_id not in chunks:
            raise ValueError(f"chunk absent du nouveau build : {chunk_id}")
        target = chunks[chunk_id]
        if row["text"] != target["text"]:
            raise ValueError(f"texte modifié : re-embedding requis pour {chunk_id}")
        seen.add(chunk_id)
        before = (str(row["page_start"]), str(row["page_end"]))
        after = (str(target["page_start"]), str(target["page_end"]))
        if before != after:
            changes.append({
                "chunk_id": chunk_id,
                "before": before,
                "after": after,
            })
    missing = chunks.keys() - seen
    if missing != expected_missing:
        unexpected = missing - expected_missing
        restored = expected_missing - missing
        raise ValueError(
            "écart avec la liste d'exclusions : "
            f"{len(unexpected)} absences inattendues, "
            f"{len(restored)} exclusions encore présentes"
        )
    return sorted(changes, key=lambda item: item["chunk_id"])


def merge_manifest(
    existing: dict,
    *,
    table_name: str,
    size: str,
    chunks_path: Path,
    exclusions_path: Path,
    chunk_count: int,
    row_count: int,
    excluded_count: int,
    changes: list[dict],
    applied_at: str,
) -> dict:
    """Preserve le manifeste de build et y ajoute la migration de pages.

    Les premières versions du script remplaçaient le manifeste, supprimant
    ainsi la preuve du filtrage. Cette fonction accepte aussi cet ancien
    rapport et le convertit en entrée ``metadata_migrations``.
    """

    manifest = dict(existing)
    migrations = list(manifest.get("metadata_migrations", []))
    if manifest.get("metadata_only_migration"):
        legacy = {
            "applied_at": manifest.get("created_at", applied_at),
            "page_ranges_updated": manifest.get("page_ranges_updated", 0),
            "changes": manifest.get("changes", []),
        }
        if legacy["changes"] and legacy not in migrations:
            migrations.append(legacy)

    if changes:
        current = {
            "applied_at": applied_at,
            "page_ranges_updated": len(changes),
            "changes": changes,
        }
        if current not in migrations:
            migrations.append(current)

    for obsolete in ("metadata_only_migration", "page_ranges_updated", "changes"):
        manifest.pop(obsolete, None)

    manifest.update({
        "schema_version": max(int(manifest.get("schema_version", 1)), 1),
        "created_at": manifest.get("created_at", applied_at),
        "updated_at": applied_at,
        "table": table_name,
        "chunk_variant": int(size),
        "chunk_sha256": sha256(chunks_path),
        "rows_before_filtering": chunk_count,
        "rows_after_filtering": row_count,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_revision": EMBEDDING_REVISION,
        "filtered": True,
        "excluded_chunks": excluded_count,
        "exclusions_sha256": sha256(exclusions_path),
        "last_operation": "metadata-only-page-migration",
        "metadata_migrations": migrations,
    })
    return manifest


def main() -> None:
    size = next((arg for arg in sys.argv[1:] if arg in ("512", "1024")), "512")
    chunks_path = ROOT / "chunks" / f"chunks-{size}.jsonl"
    chunks = {
        row["chunk_id"]: row
        for row in (json.loads(line) for line in chunks_path.open())
    }
    exclusions_path = ROOT / "eval" / f"excluded-chunks-{size}.txt"
    excluded = {
        line.split("\t", 1)[0]
        for line in exclusions_path.read_text().splitlines()
        if line.strip()
    }

    import lancedb

    table_name = f"bunge_{size}"
    table = lancedb.connect(ROOT / "index" / "lancedb").open_table(table_name)
    rows = table.to_arrow().select(
        ["chunk_id", "text", "page_start", "page_end"]
    ).to_pylist()
    changes = changes_for(rows, chunks, expected_missing=excluded)

    for change in changes:
        escaped = change["chunk_id"].replace("'", "''")
        table.update(
            where=f"chunk_id = '{escaped}'",
            values={
                "page_start": change["after"][0],
                "page_end": change["after"][1],
            },
        )

    # Relire les métadonnées garantit que LanceDB a appliqué chaque mutation.
    updated = table.to_arrow().select(
        ["chunk_id", "text", "page_start", "page_end"]
    ).to_pylist()
    remaining = changes_for(updated, chunks, expected_missing=excluded)
    if remaining:
        raise RuntimeError(f"{len(remaining)} corrections non appliquées")

    manifest = ROOT / "index" / f"manifest-{table_name}.json"
    existing = json.loads(manifest.read_text()) if manifest.exists() else {}
    report = merge_manifest(
        existing,
        table_name=table_name,
        size=size,
        chunks_path=chunks_path,
        exclusions_path=exclusions_path,
        chunk_count=len(chunks),
        row_count=table.count_rows(),
        excluded_count=len(excluded),
        changes=changes,
        applied_at=datetime.now(timezone.utc).isoformat(),
    )
    manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        f"{table_name} : {len(changes)} plages corrigées, "
        f"{table.count_rows()} textes/vecteurs inchangés"
    )
    print(f"manifeste -> {manifest}")


if __name__ == "__main__":
    main()
