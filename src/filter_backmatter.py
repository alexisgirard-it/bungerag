"""Filtre anti-annexes : retire de l'index les chunks de bibliographie,
d'index et de pages de garde.

Pourquoi : ces pages sont de la soupe semantique "Bunge + science + philo"
qui matche toutes les questions (decouvert par la mini-eval de phase 4 :
la page 'About the author' de Causality sortait 1re sur la question sur
l'esprit). Le probleme se regle dans les DONNEES, pas dans l'algorithme.

Effet : suppression des lignes fautives dans LanceDB (pas de re-embedding
necessaire) + liste des chunk_id exclus versionnee dans eval/.

Usage : .venv/bin/python src/filter_backmatter.py [512|1024] [--dry-run]
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

YEAR = re.compile(r"\((?:18|19|20)\d\d[a-z]?\)")
BAREYEAR = re.compile(r"\b(?:18|19|20)\d\d[a-z]?\b")
AUTHORLINE = re.compile(r"^\s*[-*\u2022]?\s*[A-Z][\w'\u2019-]+,\s+[A-Z]", re.M)
INDEXLINE = re.compile(r"^.{2,45}[,.]?\s\d{1,4}(?:\s*[-,]\s*\d{1,4})*\s*$")
FRONT = ("library of congress", "isbn", "all rights reserved",
         "no part of this book", "cataloging", "printed in")
BIBLIOMARK = ("pp.", "vol.", " ed.", "eds.", "in:", "journal")
# appareil editorial de l'anthologie EPUB (introduction de Mahner, biblio...) :
# pas la voix de Bunge -> exclu, meme logique que les volumes collectifs
EPUB_EDITORIAL = ("INTRODUCTION", "BIBLIOGRAPHY", "CONTENTS", "ACKNOWLEDG")

def is_backmatter(text, book="", page=""):
    t = text.lower()
    if book.startswith("scientific-realism") and \
            any(m in str(page).upper() for m in EPUB_EDITORIAL):
        return "editorial-epub"
    if any(m in t for m in FRONT):
        return "garde/copyright"
    if len(YEAR.findall(text)) >= 8:  # ~2 refs biblio par ligne
        return "bibliographie"
    # biblios sans parentheses ("- Bunge, Mario. 2003b. ...")
    if len(AUTHORLINE.findall(text)) >= 6 or \
            (len(BAREYEAR.findall(text)) >= 12 and any(m in t for m in BIBLIOMARK)):
        return "bibliographie"
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) >= 15 and sum(bool(INDEXLINE.match(l)) for l in lines) / len(lines) > 0.5:
        return "index"
    return None

def main():
    size = next((a for a in sys.argv[1:] if a in ("512", "1024")), "512")
    dry = "--dry-run" in sys.argv

    chunks = [json.loads(l) for l in open(ROOT / "chunks" / f"chunks-{size}.jsonl")]
    flagged = [(c["chunk_id"], why) for c in chunks
               if (why := is_backmatter(c["text"], c["book"], c["page_start"]))]
    print(f"{len(flagged)}/{len(chunks)} chunks annexes ({Counter(w for _, w in flagged)})")

    out = ROOT / "eval" / f"excluded-chunks-{size}.txt"
    with open(out, "w") as f:
        for cid, why in flagged:
            f.write(f"{cid}\t{why}\n")
    print(f"liste -> {out}")

    if dry:
        return
    import lancedb
    tbl = lancedb.connect(ROOT / "index" / "lancedb").open_table(f"bunge_{size}")
    ids = ", ".join(f"'{cid}'" for cid, _ in flagged)
    tbl.delete(f"chunk_id IN ({ids})")
    print(f"table bunge_{size} : {tbl.count_rows()} lignes restantes")

if __name__ == "__main__":
    main()
