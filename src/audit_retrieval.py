"""Repérer l'étape où disparaît la référence historique, à index et traductions fixes."""

import json
from pathlib import Path

from definitions import candidates
from search import search

ROOT = Path(__file__).resolve().parents[1]


def first_target(ids, targets):
    return next((rank for rank, item in enumerate(ids, 1) if item in targets), None)


def main():
    dataset = json.loads((ROOT / "eval/passages-eval.json").read_text())
    final_cache = ROOT / "eval/cache/comparaison-passages"
    rows = []
    for question in dataset["questions"]:
        qid = question["id"]
        q, en = question["question"], question["en"]
        targets = set(question["targets"])
        hits = search(mode="hybrid", k=12, table="bunge_512", dense_query=q, text_query=en)
        hits, _ = candidates(q, en, hits, search, "bunge_512")
        ids = [h["chunk_id"] for h in hits]
        final = json.loads((final_cache / f"{qid}-public_v2.json").read_text())
        selected = [h["chunk_id"] for h in final["hits"]]
        if not set(selected).issubset(ids):
            raise ValueError(f"Index ou candidats incompatibles avec le cache V2 pour {qid}")
        init_rank, final_rank = first_target(ids, targets), first_target(selected, targets)
        stage = "retrouvée" if final_rank else "reclassement" if init_rank else "récupération"
        rows.append(dict(id=qid, candidats=ids, top5=selected, rang_initial=init_rank,
                         rang_final=final_rank, étape=stage))
    path = ROOT / "eval/diagnostic-recherche-v2.json"
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    for stage in ("retrouvée", "reclassement", "récupération"):
        print(stage, sum(row["étape"] == stage for row in rows))


if __name__ == "__main__":
    main()
