"""Extension (c) - fenetrage : chercher precis, lire large.

Le retrieval selectionne des chunks de ~512 tokens (precision maximale de
la recherche), mais un argument de Bunge deborde souvent du chunk. Au
moment de la GENERATION seulement, chaque chunk retenu est etendu a ses
voisins immediats dans le livre (radius=1 -> ~1500 tokens de contexte).

Details qui comptent :
- les chunks consecutifs se chevauchent (64 tokens) -> fusion par
  recouvrement suffixe/prefixe, pas de texte duplique ;
- deux fenetres qui se touchent sont fusionnees en une seule (intervalle) ;
- l'EPUB est decoupe par essai : on ne franchit jamais une frontiere
  d'essai (verification par label de chapitre).

L'index n'est PAS touche : zero re-embedding, l'extension est purement
cote generation, activable par RAG_WINDOW=1.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_chunks = None

def _load():
    global _chunks
    if _chunks is None:
        _chunks = {}
        for line in open(ROOT / "chunks" / "chunks-512.jsonl"):
            c = json.loads(line)
            idx = int(c["chunk_id"].split(":")[1])
            _chunks.setdefault(c["book"], {})[idx] = c
    return _chunks

def _merge_overlap(a, b, max_ov=600):
    """Concatene a+b en supprimant le recouvrement suffixe(a)/prefixe(b)."""
    m = min(len(a), len(b), max_ov)
    for L in range(m, 30, -1):
        if a[-L:] == b[:L]:
            return a + b[L:]
    return a + "\n" + b

def expand(hits, radius=1):
    """hits (chunks retenus) -> fenetres fusionnees, format uniforme."""
    chunks = _load()
    by_book = {}
    for h in hits:
        idx = int(h["chunk_id"].split(":")[1])
        by_book.setdefault(h["book"], []).append((idx, h))

    windows = []
    for book, items in by_book.items():
        items.sort(key=lambda t: t[0])
        intervals = []  # [lo, hi, meilleurs_hits]
        for idx, h in items:
            lo, hi = idx - radius, idx + radius
            if intervals and lo <= intervals[-1][1] + 1:
                intervals[-1][1] = max(intervals[-1][1], hi)
                intervals[-1][2].append(h)
            else:
                intervals.append([lo, hi, [h]])
        for lo, hi, hs in intervals:
            ref = hs[0]
            # ATTENTION : LanceDB renvoie les pages en str ("25"), le fichier
            # de chunks en int (25). Seul l'EPUB a des labels non numeriques.
            epub = not str(ref["page_start"]).isdigit()
            text, pages = "", []
            for i in range(lo, hi + 1):
                c = chunks[book].get(i)
                if c is None:
                    continue
                if epub and str(c["page_start"]) != str(ref["page_start"]):
                    continue  # ne pas franchir une frontiere d'essai
                text = _merge_overlap(text, c["text"]) if text else c["text"]
                pages += [c["page_start"], c["page_end"]]
            if not text:  # garde-fou : JAMAIS de fenetre vide en contexte
                text, pages = ref["text"], [ref["page_start"], ref["page_end"]]
            if epub:
                p_lo = p_hi = str(pages[0])
            else:
                nums = [int(p) for p in pages]
                p_lo, p_hi = str(min(nums)), str(max(nums))
            windows.append({
                "book": book, "title": ref["title"],
                "page_start": p_lo, "page_end": p_hi,
                "text": text,
                "rerank_score": max(h["rerank_score"] for h in hs),
            })
    windows.sort(key=lambda w: w["rerank_score"], reverse=True)
    return windows
