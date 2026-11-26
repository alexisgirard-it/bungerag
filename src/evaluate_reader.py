"""Mesure appariée des profils sur les passages historiques et la recette paginée réservée."""

import argparse
import json
from pathlib import Path
from time import monotonic

from config import PUBLIC_V2, PUBLIC_V3
from library import question_scope, search_library, translate
from rag import ranked_hits

ROOT = Path(__file__).resolve().parents[1]


def ranks(groups, hits, reader=False):
    positions = []
    for group in groups:

        def contains(hit):
            if hit["book"] != group["book"]:
                return False
            if reader:
                return hit["edition"] == group["edition"] and str(hit["page"]) in map(
                    str, group["pdf_pages"]
                )
            first, last = str(hit["page_start"]), str(hit["page_end"])
            return (
                first.isdecimal()
                and last.isdecimal()
                and any(int(first) <= p <= int(last) for p in group["pdf_pages"])
            )

        positions.append(next((i for i, h in enumerate(hits, 1) if contains(h)), None))
    return positions


def run(suite, profile, output):
    directory = ROOT / "eval/cache" / output
    directory.mkdir(parents=True, exist_ok=True)
    cases = (
        [
            json.loads(s)
            for s in (ROOT / "eval/lecture-reservee.jsonl").read_text().splitlines()
        ]
        if suite == "reserve"
        else json.loads((ROOT / "eval/passages-eval.json").read_text())["questions"]
    )
    for q in cases:
        path = directory / f"{suite}-{q['id']}-{profile}.json"
        if path.is_file():
            continue
        tic = monotonic()
        disposition = None
        if profile == "lecteur":
            disposition, _ = question_scope(q["question"])
            english = None
            tr = tic
            hits = search_library(q["question"]) if disposition == "localiser" else []
            ids = [f"{h['book']}:{h['page']}" for h in hits]
        else:
            english = q["en"] if suite == "historique" else translate(q["question"])
            tr = monotonic()
            cfg = PUBLIC_V2 if profile == "v2" else PUBLIC_V3
            hits = ranked_hits(
                q["question"], english, cfg, cfg.k_candidates, cfg.k_final
            )
            ids = [h["chunk_id"] for h in hits]
        if suite == "reserve":
            positions = ranks(q["evidence_groups"], hits, profile == "lecteur")
        else:
            positions = [
                next((i for i, k in enumerate(ids, 1) if k in q["targets"]), None)
            ]
        rec = dict(
            id=q["id"],
            profile=profile,
            suite=suite,
            english=english,
            ranking=ids,
            ranks=positions,
            disposition=disposition,
            translation_seconds=round(tr - tic, 3),
            search_seconds=round(monotonic() - tr, 3),
        )
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rec, ensure_ascii=False))
        tmp.replace(path)
        print(q["id"], positions, rec["search_seconds"], flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("suite", choices=["reserve", "historique"])
    p.add_argument("profile", choices=["v2", "v3", "lecteur"])
    p.add_argument("--output", default="recette-v3")
    a = p.parse_args()
    if a.suite == "historique" and a.profile == "lecteur":
        p.error("Le jeu historique utilise des identifiants de chunks.")
    run(a.suite, a.profile, a.output)
