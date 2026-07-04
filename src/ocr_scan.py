"""Phase 1 bis - OCR d'un livre du corpus via Apple Vision (gratuit, local).

Sert pour les scans sans couche texte (sociology-philosophy-connection) ET pour
les PDF dont la couche texte est cassee a la source (political-philosophy).
Chaine : PyMuPDF rend chaque page en image 300 dpi -> ocrmac (framework Vision
de macOS) la lit -> memes fichiers de sortie que extract.py (.jsonl + .md).

Usage : .venv/bin/python src/ocr_scan.py [fichier.pdf] [debut] [fin]
        sans argument : tout le livre.
"""

import json
import sys
import time
from pathlib import Path

import csv

import pymupdf
from ocrmac import ocrmac

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "extracted"

BOOK = sys.argv[1] if len(sys.argv) > 1 else "sociology-philosophy-connection-1999.pdf"
SRC = ROOT / "corpus" / BOOK
with open(ROOT / "manifest.csv", newline="") as f:
    row = next(r for r in csv.DictReader(f) if r["fichier"] == BOOK)
META = {"book": SRC.stem, "title": row["titre"], "year": row["annee"]}

def ocr_page(page):
    """Rend la page en image puis la fait lire par Apple Vision."""
    pix = page.get_pixmap(dpi=300)
    img = pix.pil_image()
    result = ocrmac.OCR(img, recognition_level="accurate",
                        language_preference=["en-US"]).recognize()
    # Vision renvoie (texte, confiance, bbox) ; bbox = (x, y, l, h) normalisee,
    # origine en BAS a gauche -> on trie du haut de la page vers le bas.
    result.sort(key=lambda r: -(r[2][1] + r[2][3]))
    return "\n".join(r[0] for r in result).strip()

def main():
    first = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    last = int(sys.argv[3]) if len(sys.argv) > 3 else None
    doc = pymupdf.open(SRC)
    last = last or doc.page_count
    suffix = "" if (first, last) == (1, doc.page_count) else f".p{first}-{last}"

    records, t0 = [], time.time()
    for i in range(first - 1, last):
        text = ocr_page(doc[i])
        if text:
            records.append({**META, "page": i + 1, "text": text})
        if (i + 1) % 25 == 0:
            print(f"  page {i+1}/{last}  ({time.time()-t0:.0f}s)", flush=True)

    OUT.mkdir(exist_ok=True)
    with open(OUT / f"{SRC.stem}{suffix}.jsonl", "w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT / f"{SRC.stem}{suffix}.md", "w") as f:
        for r in records:
            f.write(f"\n\n----- [{r['book']} | p.{r['page']}] -----\n\n{r['text']}")

    chars = sum(len(r["text"]) for r in records)
    print(f"{len(records)} pages OCR, {chars/1e6:.2f} M car., "
          f"{time.time()-t0:.0f}s ({(time.time()-t0)/max(1,last-first+1):.1f}s/page)")

if __name__ == "__main__":
    main()
