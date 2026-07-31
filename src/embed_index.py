"""Phase 3 - embeddings + index.

Transforme chaque chunk en vecteur (Qwen3-Embedding-0.6B, local, GPU Apple)
et range tout dans LanceDB (base = simple dossier index/lancedb), puis cree
l'index plein-texte BM25 sur la colonne text -> recherche hybride possible.

Cout : une seule passe (l'index est ensuite reutilise tel quel, y compris
sur Hugging Face Spaces ou il sera copie).

Usage : .venv/bin/python src/embed_index.py [512|1024] [--limit N]
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import lancedb
from sentence_transformers import SentenceTransformer
import torch

ROOT = Path(__file__).resolve().parent.parent
MODEL = "Qwen/Qwen3-Embedding-0.6B"
MODEL_REVISION = os.environ.get(
    "EMBEDDING_REVISION",
    "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3",
)


def select_device():
    """Choisit un accélérateur disponible, avec un CPU réellement supporté."""
    if torch.backends.mps.is_available():
        return "mps", torch.float16
    if torch.cuda.is_available():
        return "cuda", torch.float16
    return "cpu", torch.float32


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def load_chunks(size, limit=None):
    rows = []
    with open(ROOT / "chunks" / f"chunks-{size}.jsonl") as f:
        for line in f:
            c = json.loads(line)
            # LanceDB exige un type unique par colonne : pages en str
            # (l'EPUB utilise deja des labels de chapitre)
            c["page_start"] = str(c["page_start"])
            c["page_end"] = str(c["page_end"])
            rows.append(c)
            if limit and len(rows) >= limit:
                break
    return rows

def main():
    size = next((a for a in sys.argv[1:] if a in ("512", "1024")), "512")
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    rows = load_chunks(size, limit)
    print(f"{len(rows)} chunks a indexer (variante {size})", flush=True)

    device, dtype = select_device()
    print(f"materiel : {device} ({dtype})", flush=True)
    model = SentenceTransformer(MODEL, revision=MODEL_REVISION, device=device,
                                processor_kwargs={"padding_side": "left"},
                                model_kwargs={"torch_dtype": dtype})
    model.max_seq_length = 1024  # nos chunks font <= ~600 tokens Qwen

    t0 = time.time()
    batch_size = int(os.environ.get(
        "EMBEDDING_BATCH_SIZE", "24" if device != "cpu" else "8"
    ))
    vectors = []
    for i in range(0, len(rows), batch_size):
        batch = [r["text"] for r in rows[i:i + batch_size]]
        vectors.extend(model.encode(batch, batch_size=batch_size,
                                    normalize_embeddings=True).tolist())
        if (i // batch_size) % 20 == 0:
            done = i + len(batch)
            rate = done / (time.time() - t0)
            eta = (len(rows) - done) / max(rate, 1e-9) / 60
            print(f"  {done}/{len(rows)}  ({rate:.0f} chunks/s, reste ~{eta:.0f} min)",
                  flush=True)
    for r, v in zip(rows, vectors):
        r["vector"] = v
    print(f"embeddings : {time.time()-t0:.0f}s", flush=True)

    db = lancedb.connect(ROOT / "index" / "lancedb")
    name = f"bunge_{size}" + ("_test" if limit else "")
    db.drop_table(name, ignore_missing=True)
    tbl = db.create_table(name, rows)
    from lancedb.index import FTS
    tbl.create_index("text", config=FTS())  # index lexical BM25 (hybride)
    print(f"table '{name}' : {tbl.count_rows()} lignes + index FTS")

    chunk_file = ROOT / "chunks" / f"chunks-{size}.jsonl"
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "table": name,
        "chunk_variant": int(size),
        "chunk_sha256": sha256(chunk_file),
        "rows_before_filtering": tbl.count_rows(),
        "embedding_model": MODEL,
        "embedding_revision": MODEL_REVISION,
        "device": device,
        "dtype": str(dtype).replace("torch.", ""),
        "batch_size": batch_size,
        "filtered": False,
    }
    manifest_path = ROOT / "index" / f"manifest-{name}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"manifeste reproductible -> {manifest_path}")

if __name__ == "__main__":
    main()
