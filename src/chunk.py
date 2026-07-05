"""Phase 2 - decoupage du corpus en chunks de taille calibree.

Entree  : extracted/*.jsonl (1 ligne = 1 page)
Sortie  : chunks/chunks-512.jsonl et chunks/chunks-1024.jsonl
          1 ligne = 1 chunk : {chunk_id, book, title, year, page_start,
                               page_end, n_tokens, text}

Decisions de design (voir la lecon de phase) :
- On recolle les pages d'un livre AVANT de decouper : une frontiere de page
  est typographique, pas semantique — un argument ne s'arrete pas parce que
  la page tourne. Chaque chunk garde sa plage de pages [page_start, page_end].
- On recolle les cesures residuelles ("philoso-\nphy" -> "philosophy"),
  y compris a cheval sur deux pages.
- L'EPUB (anthologie d'essais distincts) est decoupe PAR chapitre : on ne
  melange pas la fin d'un essai avec le debut du suivant.
- Deux tailles (512 et 1024 tokens) : l'eval de la phase 6 tranchera.

Usage : .venv/bin/python src/chunk.py
"""

import glob
import json
import re
from bisect import bisect_right
from pathlib import Path

import tiktoken
from llama_index.core.node_parser import SentenceSplitter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "chunks"
ENC = tiktoken.get_encoding("cl100k_base")
VARIANTS = [(512, 64), (1024, 128)]  # (taille, chevauchement) en tokens

CESURE = re.compile(r"(?<=\w)-\n(?=[a-z])")  # tiret + saut de ligne + minuscule

def build_text(records):
    """Recolle les pages d'un livre en un seul texte.

    Renvoie (texte, bornes) ou bornes = [(offset_debut, page), ...] pour
    savoir a quelle page correspond n'importe quelle position du texte.
    """
    parts, bounds, pos = [], [], 0
    for r in records:
        t = CESURE.sub("", r["text"])
        if parts:
            # cesure a cheval sur deux pages : "explana-" / "tion"
            if re.search(r"\w-$", parts[-1]) and re.match(r"[a-z]", t):
                parts[-1] = parts[-1][:-1]
                pos -= 1
            else:
                parts.append("\n\n")
                pos += 2
        bounds.append((pos, r["page"]))
        parts.append(t)
        pos += len(t)
    return "".join(parts), bounds

def page_at(bounds, offset):
    """Page correspondant a une position dans le texte recolle."""
    i = bisect_right([b[0] for b in bounds], offset) - 1
    return bounds[max(0, i)][1]

def chunk_text(text, bounds, splitter):
    """Decoupe un texte et localise chaque chunk dans ses pages d'origine."""
    chunks, cursor = [], 0
    for ch in splitter.split_text(text):
        # retrouve la position du chunk (le chevauchement impose de chercher
        # un peu en arriere du curseur)
        idx = text.find(ch[:60], max(0, cursor - 4000))
        if idx < 0:
            idx = text.find(ch[:60])
        chunks.append({
            "page_start": page_at(bounds, idx),
            "page_end": page_at(bounds, idx + len(ch) - 1),
            "n_tokens": len(ENC.encode(ch)),
            "text": ch,
        })
        cursor = idx + len(ch)
    return chunks

def process(size, overlap):
    splitter = SentenceSplitter(chunk_size=size, chunk_overlap=overlap)
    OUT.mkdir(exist_ok=True)
    out_path = OUT / f"chunks-{size}.jsonl"
    n_total = tok_total = span = 0

    with open(out_path, "w") as out:
        for jf in sorted(glob.glob(str(ROOT / "extracted" / "*.jsonl"))):
            records = [json.loads(l) for l in open(jf)]
            meta = {k: records[0][k] for k in ("book", "title", "year")}
            is_epub = isinstance(records[0]["page"], str)

            book_chunks = []
            if is_epub:  # 1 record = 1 chapitre, decoupes separement
                for r in records:
                    text, bounds = build_text([r])
                    book_chunks += chunk_text(text, bounds, splitter)
            else:
                text, bounds = build_text(records)
                book_chunks = chunk_text(text, bounds, splitter)

            for i, c in enumerate(book_chunks):
                c = {"chunk_id": f"{meta['book']}:{i:05d}", **meta, **c}
                out.write(json.dumps(c, ensure_ascii=False) + "\n")
                n_total += 1
                tok_total += c["n_tokens"]
                span += c["page_start"] != c["page_end"]

    print(f"chunks-{size} : {n_total} chunks, {tok_total/1e6:.2f} M tokens, "
          f"moyenne {tok_total//n_total} tok/chunk, "
          f"{span/n_total:.0%} a cheval sur 2+ pages -> {out_path.name}")

if __name__ == "__main__":
    for size, overlap in VARIANTS:
        process(size, overlap)
