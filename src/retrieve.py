"""Le retriever complet de BungeRAG : filet large puis second regard.

Etage 1 (rappel)    : recherche hybride (dense + BM25 fusionnes par RRF),
                      k_candidats eleve (40) pour ne rien rater.
Etage 2 (precision) : reranker cross-encodeur qui relit les 40 candidats
                      avec la question et garde les k_final meilleurs.

Usage : .venv/bin/python src/retrieve.py "ta question" [k_final]
"""

import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from search import MODEL_LOCK, search  # noqa: E402

_reranker = None


def get_reranker():
    global _reranker
    with MODEL_LOCK:
        if _reranker is None:
            from rerank import Reranker

            _reranker = Reranker()
    return _reranker


@lru_cache(maxsize=1)
def compact_reranker():
    with MODEL_LOCK:
        import torch
        from sentence_transformers import CrossEncoder

        device = (
            "mps"
            if torch.backends.mps.is_available()
            else "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )
        return CrossEncoder(
            "Horizon-Labs/multilingual-reranker-small",
            revision="23139fec6f1f448cdf89a5ac2d2c6bf5e8c7b398",
            max_length=512,
            device=device,
            model_kwargs={"dtype": torch.float32 if device == "cpu" else torch.float16},
        )


def rank_v3(question, english, table, breadth, keep):
    from search import search
    from definitions import candidates, strength, terms_for

    rows = search(
        mode="hybrid",
        k=max(40, breadth),
        table=table,
        dense_query=question,
        text_query=english,
    )[:breadth]
    terms = terms_for(question, english)
    rows, preferred = candidates(question, english, rows, search, table)
    if not rows:
        return []
    with MODEL_LOCK:
        scores = compact_reranker().predict(
            [(question, r["text"]) for r in rows], batch_size=4, show_progress_bar=False
        )
    for row, score in zip(rows, scores):
        row["rerank_score"] = float(score)
    rows.sort(key=lambda r: r["rerank_score"], reverse=True)
    result = rows[:keep]
    # Une définition littérale constitue une source utile aux côtés des passages reclassés.
    formal = next(
        (r for r in rows if r["chunk_id"] in preferred and strength(r, terms) == 3),
        None,
    )
    if formal and keep > 1 and all(r["chunk_id"] != formal["chunk_id"] for r in result):
        result[-1] = formal
    return result


def retrieve(query, k_candidates=40, k_final=8, mode="hybrid", rerank=True):
    hits = search(query, mode, k_candidates)
    if not rerank:
        return hits[:k_final]
    with MODEL_LOCK:
        scores = get_reranker().score(query, [h["text"] for h in hits])
    for h, s in zip(hits, scores):
        h["rerank_score"] = s
    hits.sort(key=lambda h: h["rerank_score"], reverse=True)
    return hits[:k_final]


if __name__ == "__main__":
    import time

    query = sys.argv[1]
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    t0 = time.time()
    for h in retrieve(query, k_final=k):
        pages = (
            h["page_start"]
            if h["page_start"] == h["page_end"]
            else f"{h['page_start']}-{h['page_end']}"
        )
        print(f"\n[{h['rerank_score']:.3f}] [{h['title'][:50]} | p.{pages}]")
        print("  " + " ".join(h["text"].split())[:200])
    print(f"\n({time.time() - t0:.1f}s au total)")
