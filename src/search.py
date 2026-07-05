"""Recherche dans l'index BungeRAG - les 3 modes, pour comparer.

dense  : par similarite de sens (vecteurs Qwen3)
bm25   : par mots-cles exacts (index plein-texte)
hybrid : fusion des deux par RRF (Reciprocal Rank Fusion)

Usage : .venv/bin/python src/search.py "ta question" [dense|bm25|hybrid] [k]
"""

import sys
from pathlib import Path

import lancedb
from lancedb.rerankers import RRFReranker

ROOT = Path(__file__).resolve().parent.parent
_model = None

def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B", device="mps",
                                     processor_kwargs={"padding_side": "left"},
                                model_kwargs={"torch_dtype": "float16"})
        _model.max_seq_length = 1024
    return _model

def embed_query(q):
    # prompt_name="query" : Qwen3 attend une instruction cote requete
    # (les documents, eux, sont encodes nus) - voir la lecon de phase.
    return get_model().encode(q, prompt_name="query",
                              normalize_embeddings=True).tolist()

def search(query, mode="hybrid", k=5, table="bunge_512"):
    tbl = lancedb.connect(ROOT / "index" / "lancedb").open_table(table)
    if mode == "dense":
        q = tbl.search(embed_query(query)).limit(k)
    elif mode == "bm25":
        q = tbl.search(query, query_type="fts").limit(k)
    else:
        q = (tbl.search(query_type="hybrid")
                .vector(embed_query(query)).text(query)
                .rerank(RRFReranker()).limit(k))
    return q.to_list()

if __name__ == "__main__":
    query = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "hybrid"
    k = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    for r in search(query, mode, k):
        pages = r["page_start"] if r["page_start"] == r["page_end"] \
                else f"{r['page_start']}-{r['page_end']}"
        print(f"\n[{r['title']} | p.{pages}]")
        print("  " + " ".join(r["text"].split())[:220])
