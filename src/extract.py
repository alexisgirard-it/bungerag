"""Phase 1 - extraction du corpus en pages de texte propre.

Entree  : corpus/ + manifest.csv (colonnes fichier,titre,annee,...,texte,inclus)
Sortie  : extracted/<livre>.jsonl  -> 1 ligne JSON par page : {book, title, year, page, text}
          extracted/<livre>.md     -> apercu lisible (controle a l'oeil)

Le numero de page est celui du PDF (celui que tu vois dans Aperçu/Acrobat),
pas celui imprime sur la page : c'est le seul qui soit verifiable en 1 clic.

Le livre scanne (texte=OCR_REQUIS) est traite a part par ocr_scan.py.
Usage : .venv/bin/python src/extract.py [nom-de-fichier ...]  (sans argument : tout)
"""

import csv
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import pymupdf4llm

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
OUT = ROOT / "extracted"

# ---------------------------------------------------------------- manifest

def load_manifest():
    with open(ROOT / "manifest.csv", newline="") as f:
        return [r for r in csv.DictReader(f) if r["inclus"] == "oui"]

# ------------------------------------------------- nettoyage du "mobilier"
# En-tetes, pieds de page et numeros de page repetes polluent les chunks.
# Heuristique : une ligne (une fois les chiffres retires) qui apparait en
# HAUT ou en BAS de page sur >= 25% des pages d'un livre est du mobilier.

PAGENUM = re.compile(r"^[\s*_#]*(\d{1,4}|[ivxlcdm]{1,7})[\s*_#]*$", re.I)
EDGE = 2  # nombre de lignes inspectees en haut et en bas de chaque page

def normalize(line):
    """Signature d'une ligne : sans chiffres ni decor markdown, en minuscules."""
    line = re.sub(r"[\d#*_|]+", "", line).strip().lower()
    return re.sub(r"\s+", " ", line)

def find_furniture(pages):
    top, bottom = Counter(), Counter()
    for text in pages:
        lines = [l for l in text.splitlines() if l.strip()]
        for l in lines[:EDGE]:
            top[normalize(l)] += 1
        for l in lines[-EDGE:]:
            bottom[normalize(l)] += 1
    threshold = max(3, len(pages) // 4)
    keep = lambda c: {sig for sig, n in c.items() if n >= threshold and sig}
    return keep(top), keep(bottom)

def strip_furniture(text, top_sigs, bottom_sigs):
    lines = text.splitlines()
    n_stripped = [i for i, l in enumerate(lines) if l.strip()]
    drop = set()
    for rank, i in enumerate(n_stripped[:EDGE]):
        if PAGENUM.match(lines[i]) or normalize(lines[i]) in top_sigs:
            drop.add(i)
    for rank, i in enumerate(n_stripped[-EDGE:]):
        if PAGENUM.match(lines[i]) or normalize(lines[i]) in bottom_sigs:
            drop.add(i)
    return "\n".join(l for i, l in enumerate(lines) if i not in drop).strip()

# ------------------------------------------------------------- extracteurs

def extract_pdf(path):
    """Rend la liste des pages en markdown (1 entree par page du PDF)."""
    chunks = pymupdf4llm.to_markdown(str(path), page_chunks=True, show_progress=False)
    return [c["text"] for c in chunks]

def extract_epub(path):
    """EPUB = pas de pages physiques -> on decoupe par chapitre."""
    from bs4 import BeautifulSoup
    from ebooklib import ITEM_DOCUMENT, epub

    book = epub.read_epub(str(path))
    chapters = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text(separator="\n").strip()
        if len(text) < 200:  # pages de garde, tables des matieres...
            continue
        h = soup.find(["h1", "h2", "h3"])
        title = h.get_text(strip=True) if h else item.get_name()
        chapters.append((title, text))
    return chapters

# ------------------------------------------------------------------- main

def process_book(row):
    src = CORPUS / row["fichier"]
    stem = src.stem
    t0 = time.time()

    if src.suffix == ".epub":
        chapters = extract_epub(src)
        records = [
            {"book": stem, "title": row["titre"], "year": row["annee"],
             "page": f"ch{idx:02d} - {title[:60]}", "text": text}
            for idx, (title, text) in enumerate(chapters, 1)
        ]
        removed = 0
    else:
        pages = extract_pdf(src)
        top_sigs, bottom_sigs = find_furniture(pages)
        cleaned = [strip_furniture(p, top_sigs, bottom_sigs) for p in pages]
        removed = sum(len(a.splitlines()) - len(b.splitlines())
                      for a, b in zip(pages, cleaned))
        records = [
            {"book": stem, "title": row["titre"], "year": row["annee"],
             "page": i, "text": text}
            for i, text in enumerate(cleaned, 1) if text
        ]

    OUT.mkdir(exist_ok=True)
    with open(OUT / f"{stem}.jsonl", "w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT / f"{stem}.md", "w") as f:
        for r in records:
            f.write(f"\n\n----- [{r['book']} | p.{r['page']}] -----\n\n{r['text']}")

    chars = sum(len(r["text"]) for r in records)
    print(f"{stem[:52]:54} {len(records):>4} pages  {chars/1e6:5.2f} M car."
          f"  {removed:>4} lignes mobilier  {time.time()-t0:5.1f}s", flush=True)
    return len(records), chars

def main():
    only = set(sys.argv[1:])
    total_p = total_c = 0
    for row in load_manifest():
        if only and row["fichier"] not in only:
            continue
        if row["texte"] == "OCR_REQUIS":
            print(f"{row['fichier'][:52]:54} SAUTE (scan -> ocr_scan.py)", flush=True)
            continue
        p, c = process_book(row)
        total_p += p
        total_c += c
    print(f"\nTOTAL : {total_p} pages, {total_c/1e6:.1f} M caracteres")

if __name__ == "__main__":
    main()
