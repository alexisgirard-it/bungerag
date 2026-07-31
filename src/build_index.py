"""Construction canonique et vérifiée de l'index BungeRAG.

Cette commande orchestre les scripts historiques sans masquer leurs étapes :
extraction optionnelle, OCR des sources déclarées, chunking, embeddings,
filtrage des annexes et validation du manifeste d'index.

Exemples :
  .venv/bin/python src/build_index.py --size 512
  .venv/bin/python src/build_index.py --extract --size 512

L'OCR repose sur Apple Vision et nécessite donc macOS. Sans ``--extract``,
la commande est portable dès lors que les fichiers ``extracted/`` existent.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"


def included_books() -> list[dict[str, str]]:
    with open(ROOT / "manifest.csv", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row["inclus"] == "oui"]


def run(script: str, *args: str) -> None:
    command = [sys.executable, str(SRC / script), *args]
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def validate_extracted(rows: list[dict[str, str]]) -> None:
    missing = [
        Path(row["fichier"]).stem
        for row in rows
        if not (ROOT / "extracted" / f"{Path(row['fichier']).stem}.jsonl").exists()
    ]
    if missing:
        preview = ", ".join(missing[:5])
        extra = f" (+{len(missing) - 5})" if len(missing) > 5 else ""
        raise SystemExit(
            f"extractions manquantes : {preview}{extra}. "
            "Relancez avec --extract ou fournissez extracted/."
        )


def extract(rows: list[dict[str, str]]) -> None:
    ocr_rows = [row for row in rows if row["texte"] == "OCR_REQUIS"]
    if ocr_rows and platform.system() != "Darwin":
        names = ", ".join(row["fichier"] for row in ocr_rows)
        raise SystemExit(
            "L'extraction complète requiert macOS/Apple Vision pour : " + names
        )
    run("extract.py")
    for row in ocr_rows:
        run("ocr_scan.py", row["fichier"])


def validate_index(size: str) -> dict:
    path = ROOT / "index" / f"manifest-bunge_{size}.json"
    if not path.exists():
        raise SystemExit(f"manifeste d'index absent : {path}")
    manifest = json.loads(path.read_text())
    required = {
        "chunk_sha256",
        "embedding_model",
        "embedding_revision",
        "rows_after_filtering",
        "exclusions_sha256",
    }
    missing = sorted(required - manifest.keys())
    if missing or not manifest.get("filtered"):
        raise SystemExit(
            "index incomplet : "
            + (f"champs absents {missing}" if missing else "filtrage non appliqué")
        )
    if manifest["rows_after_filtering"] <= 0:
        raise SystemExit("index vide après filtrage")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=("512", "1024"), default="512")
    parser.add_argument(
        "--extract",
        action="store_true",
        help="reconstruit extracted/ depuis corpus/ (OCR macOS si nécessaire)",
    )
    args = parser.parse_args()

    rows = included_books()
    if args.extract:
        extract(rows)
    validate_extracted(rows)

    run("chunk.py")
    run("embed_index.py", args.size)
    run("filter_backmatter.py", args.size)

    manifest = validate_index(args.size)
    print(
        "BUILD OK — "
        f"{manifest['rows_after_filtering']} chunks, "
        f"table {manifest['table']}, "
        f"modèle {manifest['embedding_model']}@"
        f"{manifest['embedding_revision'][:12]}",
        flush=True,
    )


if __name__ == "__main__":
    main()
