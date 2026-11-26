"""Contrôle la traçabilité de la recette et mesure les références ajoutées par les dossiers."""

import argparse
import hashlib
import json
from contextlib import closing
from functools import lru_cache
from pathlib import Path

from evidence import canonical, page_image_text
from library import CATALOG, NODES, connect, node_source, question_scope, search_library

ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = ROOT / "index/provenance-512.sqlite"


@lru_cache(maxsize=4)
def epub_edition(filename):
    from extract import extract_epub

    path = ROOT / "corpus" / Path(filename).name
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    sections = {
        f"ch{index:02d} - {title[:60]}": canonical(text)
        for index, (title, text) in enumerate(extract_epub(path), 1)
    }
    return digest, sections


def verified(source):
    page = str(source["page"])
    anchor = canonical(source["excerpt"])
    if not anchor:
        return False
    if not page.isdecimal():
        digest, sections = epub_edition(source["file"])
        return source["edition"] == digest and anchor in sections.get(page, "")
    folio, _, text, _ = page_image_text(
        PROVENANCE, PROVENANCE.stat().st_mtime_ns, source["book"], page
    )
    return anchor in text and source["folio"] == folio


def verify_catalogue():
    with closing(connect()) as db:
        indexed = dict(db.execute("SELECT book,edition FROM books"))
    notices = CATALOG["editions"]
    if {key: notice["edition"] for key, notice in notices.items()} != indexed:
        raise ValueError("Les éditions du référentiel et de l’index diffèrent")
    if not set(CATALOG["core"]) <= NODES.keys():
        raise ValueError("Le cadre cite une fiche absente")
    for key, node in NODES.items():
        source = node_source(key)
        if source["folio"] != node["source"]["folio"] or not verified(source):
            raise ValueError(f"Ancrage absent ou folio incorrect pour la fiche {key}")
    relations = CATALOG["relations"]
    if len({relation["id"] for relation in relations}) != len(relations):
        raise ValueError("Deux relations ont le même identifiant")
    for link in relations:
        if not {link["origin"], link["target"], link["witness"]} <= NODES.keys():
            raise ValueError(f"Fiche ou preuve absente pour le lien {link['id']}")
        if link.get("attribution_comment"):
            cited = NODES[link["origin"]]["source"]
            reply = NODES[link["witness"]]["source"]
            if (
                cited.get("voice") in (None, "Bunge")
                or reply.get("voice") != "Bunge"
                or cited["edition"] != reply["edition"]
            ):
                raise ValueError(f"Attribution ou réponse ambiguë pour le lien {link['id']}")
    print(f"{len(notices)} éditions, {len(NODES)} citations et {len(relations)} liens contrôlés.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", default=ROOT / "eval/cache/audit-lecteur-v3.json", type=Path
    )
    parser.add_argument("--catalogue-only", action="store_true")
    args = parser.parse_args()
    verify_catalogue()
    if args.catalogue_only:
        return

    from evaluate_reader import ranks
    from workshop import DOSSIERS, choose_dossier, open_question

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
