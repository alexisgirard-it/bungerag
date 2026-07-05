"""Mini-eval du retrieval : 4 configurations, des chiffres, un verdict.

Metrique : hit@k au niveau LIVRE — la question trouve-t-elle un passage
d'un des livres attendus dans le top-k ? (Le niveau page viendra avec le
grand harnais de la phase 6 ; le niveau livre suffit pour comparer des
configurations entre elles.)

Configs comparees :
  bm25    : mots-cles seuls, top-10
  dense   : vecteurs seuls, top-10
  hybrid  : fusion RRF,      top-10
  rerank  : hybride 40 candidats -> reranker -> top-10

Usage : .venv/bin/python src/eval_retrieval.py
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from retrieve import retrieve  # noqa: E402
from search import search  # noqa: E402

K = 10

def hit_rank(hits, expected):
    """Rang (1-base) du premier passage venant d'un livre attendu, sinon None."""
    for i, h in enumerate(hits, 1):
        if any(h["book"].startswith(e) for e in expected):
            return i
    return None

def main():
    questions = [json.loads(l) for l in open(ROOT / "eval" / "questions-retrieval.jsonl")]
    configs = {
        "bm25":   lambda q: search(q, "bm25", K),
        "dense":  lambda q: search(q, "dense", K),
        "hybrid": lambda q: search(q, "hybrid", K),
        "rerank": lambda q: retrieve(q, k_candidates=40, k_final=K),
    }
    cache_path = ROOT / "eval" / "cache" / "hits.json"
    if cache_path.exists():
        hits_all = json.loads(cache_path.read_text())
        print("hits recharges depuis le cache (re-scoring seul)")
    else:
        hits_all, t0 = {}, time.time()
        for row in questions:
            hits_all[str(row["id"])] = {
                name: [{"book": h["book"], "page": h["page_start"]} for h in fn(row["question"])]
                for name, fn in configs.items()}
            print(f"  q{row['id']:02d} traitee ({time.time()-t0:.0f}s)", flush=True)
        cache_path.parent.mkdir(exist_ok=True)
        cache_path.write_text(json.dumps(hits_all))
    results = {name: [hit_rank(hits_all[str(row["id"])][name], row["expected_books"])
                      for row in questions] for name in configs}

    print(f"\n{'config':8} {'hit@5':>6} {'hit@10':>7} {'rang moyen du 1er bon':>22}")
    print("-" * 48)
    for name, ranks in results.items():
        h5 = sum(1 for r in ranks if r and r <= 5) / len(ranks)
        h10 = sum(1 for r in ranks if r) / len(ranks)
        found = [r for r in ranks if r]
        avg = sum(found) / len(found) if found else float("nan")
        print(f"{name:8} {h5:>6.0%} {h10:>7.0%} {avg:>22.1f}")

    # detail des echecs pour inspection
    print("\nechecs (question -> configs qui ratent) :")
    for i, row in enumerate(questions):
        misses = [n for n in configs if results[n][i] is None]
        if misses:
            print(f"  q{row['id']:02d} «{row['question'][:60]}» -> {', '.join(misses)}")

if __name__ == "__main__":
    main()
