"""Phase 3 - embeddings + index.

Transforme chaque chunk en vecteur (Qwen3-Embedding-0.6B, local, GPU Apple)
et range tout dans LanceDB (base = simple dossier index/lancedb), puis cree
l'index plein-texte BM25 sur la colonne text -> recherche hybride possible.

Cout : une seule passe (l'index est ensuite reutilise tel quel, y compris
sur Hugging Face Spaces ou il sera copie).

Usage : .venv/bin/python src/embed_index.py [512|1024] [--limit N]
"""

import json
import sys
import time
from pathlib import Path

import lancedb
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parent.parent
MODEL = "Qwen/Qwen3-Embedding-0.6B"

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

    model = SentenceTransformer(MODEL, device="mps",
                                processor_kwargs={"padding_side": "left"},
                                model_kwargs={"torch_dtype": "float16"})
    model.max_seq_length = 1024  # nos chunks font <= ~600 tokens Qwen

    t0 = time.time()
    BATCH = 24
    vectors = []
    for i in range(0, len(rows), BATCH):
        batch = [r["text"] for r in rows[i:i + BATCH]]
        vectors.extend(model.encode(batch, batch_size=BATCH,
                                    normalize_embeddings=True).tolist())
        if (i // BATCH) % 20 == 0:
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

if __name__ == "__main__":
    main()
