"""Compare le top cinq V1/V2 sur l’index complet avec des traductions fixes."""

import json
from pathlib import Path
from time import monotonic

from config import PUBLIC_V1, PUBLIC_V2
import rag
from rag import ranked_hits

ROOT = Path(__file__).resolve().parents[1]


def main():
    dataset = json.loads((ROOT / "eval/passages-eval.json").read_text())
    questions = dataset["questions"] + [
        {
            "id": "psychon",
            "question": "Qu’est-ce qu’un psychon selon Bunge ?",
            "en": "What is a psychon according to Bunge?",
            "targets": ["scientific-materialism-1981:00066"],
        },
        {
            "id": "hypothese",
            "question": "L’association de psychons est-elle un fait établi ou une hypothèse chez Bunge ?",
            "en": "Is psychon pairing an established fact or a hypothesis for Bunge?",
            "targets": [
                "mind-body-problem-1980:00171",
                "treatise-5-epistemology-1-exploring-the-world-1983:00053",
            ],
        },
        {
            "id": "absence",
            "question": "Quelle est la clé privée du portefeuille Bitcoin de Mario Bunge ?",
            "en": "What is the private key of Mario Bunge’s Bitcoin wallet?",
            "targets": [],
        },
    ]
    questions = questions[-3:] + questions[:-3]
    target = ROOT / "eval/cache/comparaison-passages"
    target.mkdir(parents=True, exist_ok=True)
    report = []
    from definitions import terms_for

    # Le reclassement est indépendant pour chaque couple (question, passage).
    # Réutiliser les scores communs aux bras garde les mêmes candidats et poids.
    ranker = rag.get_reranker()
    original_score = ranker.score
    cache = {}

    def cached_score(q, texts):
        missing = [t for t in texts if t not in cache]
        if missing:
            cache.update(zip(missing, original_score(q, missing)))
        return [cache[t] for t in texts]

    ranker.score = cached_score
    for q in questions:
        cache.clear()
        old = None
        for cfg in (PUBLIC_V1, PUBLIC_V2):
            start = monotonic()
            if cfg is PUBLIC_V2 and not terms_for(q["question"], q["en"]):
                hits = old
            else:
                hits = ranked_hits(
                    q["question"], q["en"], cfg, cfg.k_candidates, cfg.k_final
                )
            if cfg is PUBLIC_V1:
                old = hits
            selected = [
                {
                    k: h[k]
                    for k in (
                        "chunk_id",
                        "book",
                        "text",
                        "title",
                        "year",
                        "page_start",
                        "page_end",
                        "rerank_score",
                    )
                }
                for h in hits
            ]
            (target / f"{q['id']}-{cfg.name}.json").write_text(
                json.dumps(
                    {"question": q["question"], "hits": selected}, ensure_ascii=False
                )
            )
            rank = next(
                (i for i, h in enumerate(hits, 1) if h["chunk_id"] in q["targets"]),
                None,
            )
            report.append({"id": q["id"], "profile": cfg.name, "rank": rank})
            print(q["id"], cfg.name, rank, round(monotonic() - start, 1), flush=True)
    (target / "scores.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
