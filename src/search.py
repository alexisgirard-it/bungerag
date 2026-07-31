"""Recherche dans l'index BungeRAG - les 3 modes, pour comparer.

dense  : par similarite de sens (vecteurs Qwen3)
bm25   : par mots-cles exacts (index plein-texte)
hybrid : fusion des deux par RRF (Reciprocal Rank Fusion)

Usage : .venv/bin/python src/search.py "ta question" [dense|bm25|hybrid] [k]
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_model = None
MODEL = "Qwen/Qwen3-Embedding-0.6B"
MODEL_REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"

def get_model():
    global _model
    if _model is None:
        import torch
        from sentence_transformers import SentenceTransformer
        if torch.backends.mps.is_available():
            dev, dtype = "mps", torch.float16
        elif torch.cuda.is_available():
            dev, dtype = "cuda", torch.float16
        else:
            dev, dtype = "cpu", torch.float32
        _model = SentenceTransformer(MODEL, revision=MODEL_REVISION, device=dev,
                                     processor_kwargs={"padding_side": "left"},
                                     model_kwargs={"torch_dtype": dtype})
        _model.max_seq_length = 1024
    return _model

def embed_query(q):
    # prompt_name="query" : Qwen3 attend une instruction cote requete
    # (les documents, eux, sont encodes nus) - voir la lecon de phase.
    return get_model().encode(q, prompt_name="query",
                              normalize_embeddings=True).tolist()

def _open_table(table):
    """Import tardif : les tests purs n'ont pas besoin d'installer LanceDB."""
    import lancedb
    return lancedb.connect(ROOT / "index" / "lancedb").open_table(table)


def _rrf_reranker():
    from lancedb.rerankers import RRFReranker
    return RRFReranker()


def search(query=None, mode="hybrid", k=5, table=None, *,
           dense_query=None, text_query=None):
    """Recherche avec requetes dense et lexicale explicitement separees.

    ``query`` reste accepte pour les anciens appels mono-requete. Le pipeline
    RAG canonique utilise toujours ``dense_query`` (FR) et ``text_query`` (EN)
    afin que l'architecture annoncee corresponde au code execute.
    """
    if mode not in {"dense", "bm25", "hybrid"}:
        raise ValueError(f"mode de recherche inconnu: {mode}")
    dense_query = dense_query if dense_query is not None else query
    text_query = text_query if text_query is not None else query
    if mode in {"dense", "hybrid"} and not dense_query:
        raise ValueError("dense_query est requis pour cette recherche")
    if mode in {"bm25", "hybrid"} and not text_query:
        raise ValueError("text_query est requis pour cette recherche")

    # BUNGE_TABLE reste supporte pour les scripts historiques.
    table = table or os.environ.get("BUNGE_TABLE", "bunge_512")
    tbl = _open_table(table)
    if mode == "dense":
        q = tbl.search(embed_query(dense_query)).limit(k)
    elif mode == "bm25":
        q = tbl.search(text_query, query_type="fts").limit(k)
    else:
        q = (tbl.search(query_type="hybrid")
                .vector(embed_query(dense_query)).text(text_query)
                .rerank(_rrf_reranker()).limit(k))
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
