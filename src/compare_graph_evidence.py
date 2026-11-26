"""Compare les appuis du graphe à budget fixe sur deux séries de questions."""

import argparse
import json
from contextlib import closing
from pathlib import Path

from evaluate_reader import ranks
from library import connect, linked_evidence, node_source, on_page, search_library, suggested_nodes

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nouveau", action="store_true")
    args = parser.parse_args()
    archived = {}
    if args.nouveau:
        fixture = "liaisons-reservees.jsonl"
    else:
        fixture = "lecture-reservee.jsonl"
        measured = json.loads((ROOT / "eval/mesures-v3.json").read_text())
        archived = {row["id"]: row["loci"] for row in measured["audit_referentiel_etendu"]}
    cases = (
        json.loads(line)
        for line in (ROOT / "eval" / fixture).read_text().splitlines()
    )
    with closing(connect()) as db:
        editions = dict(db.execute("SELECT book,edition FROM books"))
    results = []
    for case in cases:
        if case["family"] != "argument":
            continue
        groups = case["evidence_groups"]
        if args.nouveau:
            pages = search_library(case["question"])
        else:
            pages = []
            for entry in archived[case["id"]]:
                book, page = entry.rsplit(":", 1)
                pages.append(dict(book=book, page=page, edition=editions[book]))
        roots = suggested_nodes(case["question"], 3) + [
            key for source in pages[:3] for key in on_page(source["book"], source["page"])
        ]
        limit = 6
        modes = {
            "fiches_sans_liens": list(dict.fromkeys(roots))[:limit],
            "graphe_parent": linked_evidence(roots, limit),
            "graphe_racines_3": linked_evidence(roots, limit, seed_limit=3),
            "graphe_racines_2": linked_evidence(roots, limit, seed_limit=2),
            "graphe_racine_1": linked_evidence(roots, limit, seed_limit=1),
        }
        rows = dict(pages=ranks(groups, pages, reader=True))
        for mode, keys in modes.items():
            rows[mode] = dict(
                fiches=keys,
                rangs=ranks(groups, pages + [node_source(key) for key in keys], reader=True),
            )
        results.append(
            dict(
                id=case["id"], classement=rows,
                pages=[f"{source['book']}:{source['page']}" for source in pages],
            )
        )
        print(case["id"], rows["pages"], {k: rows[k]["rangs"] for k in modes}, flush=True)
    suffix = "-nouvelles" if args.nouveau else ""
    output = ROOT / f"eval/cache/comparaison-liens{suffix}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
