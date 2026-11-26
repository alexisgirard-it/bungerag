"""Mesure les titres et les pages voisines sur la même série de lectures."""

import argparse
import json
from contextlib import closing
from pathlib import Path

from evaluate_reader import ranks
from library import connect, describe_page, fts, search_library, translate, words

ROOT = Path(__file__).resolve().parents[1]


def top_pages(db, candidates, limit=5):
    ids = list(dict.fromkeys(row["page_id"] for row in candidates))[:limit]
    return [describe_page(db, pid) for pid in ids]


def neighbours(db, pages):
    known = {(p["book"], p["page"]) for p in pages}
    extra = []
    for source in pages[:3]:
        if not source["page"].isdecimal():
            continue
        physical = int(source["page"])
        for adjacent in (physical - 1, physical + 1):
            key = (source["book"], str(adjacent))
            if key in known:
                continue
            row = db.execute(
                "SELECT id FROM pages WHERE book=? AND page=?", key
            ).fetchone()
            if row:
                extra.append(describe_page(db, row["id"]))
                known.add(key)
    return extra


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=ROOT / "eval/cache/contexte-et-titres.json"
    )
    args = parser.parse_args()
    cases = [
        json.loads(row)
        for row in (ROOT / "eval/lecture-reservee.jsonl").read_text().splitlines()
    ]
    measured = json.loads((ROOT / "eval/mesures-v3.json").read_text())
    translations = measured.get("titres_et_voisines", {}).get("translations", {})
    reports = []
    with closing(connect()) as db:
        for case in cases:
            groups = case["evidence_groups"]
            if not groups:
                continue
            cache = ROOT / f"eval/cache/recette-v3/reserve-{case['id']}-v3.json"
            en = translations.get(case["id"])
            if en is None:
                en = (
                    json.loads(cache.read_text())["english"]
                    if cache.exists()
                    else translate(case["question"])
                )
            english_terms = words(en)
            arms = {}
            for title_weight in (0.0, 0.2, 1.5):
                lexical = top_pages(
                    db, fts(db, english_terms, heading_weight=title_weight)
                )
                arms[f"titres-{title_weight}"] = ranks(groups, lexical, reader=True)
            pages = search_library(case["question"], english=en)
            arms["cinq-pages"] = ranks(groups, pages, reader=True)
            arms["voisines-ajoutées"] = ranks(
                groups, pages + neighbours(db, pages), reader=True
            )
            reports.append({"id": case["id"], "family": case["family"], "ranks": arms})
            print(case["id"], arms, flush=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
