"""Contrôle la traçabilité de la recette et mesure les références ajoutées par les dossiers."""

import argparse
import json
from pathlib import Path

from evidence import canonical, page_image_text
from evaluate_reader import ranks
from library import CATALOG, NODES, node_source, question_scope, search_library
from workshop import DOSSIERS, choose_dossier, open_question

ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = ROOT / "index/provenance-512.sqlite"


def verified(source):
    page = str(source["page"])
    if not page.isdecimal():
        return bool(source["edition"] and source["excerpt"])
    folio, _, text, _ = page_image_text(
        PROVENANCE, PROVENANCE.stat().st_mtime_ns, source["book"], page
    )
    anchor = canonical(source["excerpt"])
    return bool(anchor) and anchor in text and source["folio"] == folio


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", default=ROOT / "eval/cache/audit-lecteur-v3.json", type=Path
    )
    args = parser.parse_args()
    for key, node in NODES.items():
        source = node_source(key)
        assert verified(source) and source["edition"] == node["source"]["edition"], key
    for relation in CATALOG["relations"]:
        assert relation["origin"] in NODES and relation["target"] in NODES
        assert relation["witness"] in NODES
    rows = []
    for line in (ROOT / "eval/lecture-reservee.jsonl").read_text().splitlines():
        case = json.loads(line)
        q = case["question"]
        disposition, _ = question_scope(q)
        pages = search_library(q) if disposition == "localiser" else []
        failed = [f"{s['book']}:{s['page']}" for s in pages if not verified(s)]
        rn = ranks(case["evidence_groups"], pages, reader=True)
        extra = []
        if case["family"] == "argument":
            match = choose_dossier(q)
            report = DOSSIERS[match]() if match else open_question(q, pages)
            extra = [s for step in report["steps"] for s in step["sources"]]
        resolved = ranks(case["evidence_groups"], pages + extra, reader=True)
        rows.append(
            dict(
                id=case["id"],
                loci=[f"{s['book']}:{s['page']}" for s in pages],
                ranks=rn,
                combined_ranks=resolved,
                disposition=disposition,
                bad_anchors=failed,
            )
        )
        print(case["id"], rn, resolved, "ancrages invalides", len(failed), flush=True)
    args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
