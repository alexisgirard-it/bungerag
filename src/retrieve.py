"""Le retriever complet de BungeRAG : filet large puis second regard.

Etage 1 (rappel)    : recherche hybride (dense + BM25 fusionnes par RRF),
                      k_candidats eleve (40) pour ne rien rater.
Etage 2 (precision) : reranker cross-encodeur qui relit les 40 candidats
                      avec la question et garde les k_final meilleurs.

Usage : .venv/bin/python src/retrieve.py "ta question" [k_final]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from search import search  # noqa: E402

_reranker = None

def get_reranker():
    global _reranker
    if _reranker is None:
        from rerank import Reranker
        _reranker = Reranker()
    return _reranker

def retrieve(query, k_candidates=40, k_final=8, mode="hybrid", rerank=True):
    hits = search(query, mode, k_candidates)
    if not rerank:
        return hits[:k_final]
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
        pages = h["page_start"] if h["page_start"] == h["page_end"] \
                else f"{h['page_start']}-{h['page_end']}"
        print(f"\n[{h['rerank_score']:.3f}] [{h['title'][:50]} | p.{pages}]")
        print("  " + " ".join(h["text"].split())[:200])
    print(f"\n({time.time()-t0:.1f}s au total)")
