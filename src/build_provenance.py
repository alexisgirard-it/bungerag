"""Construit la concordance privée sans recalculer les vecteurs (PDF et EPUB)."""

import csv
import gzip
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path

import pymupdf

from page_map import build_text

ROOT = Path(__file__).resolve().parents[1]


def native_lines(page):
    words = page.get_text("words", sort=True)
    groups = defaultdict(list)
    for x0, y0, x1, y1, word, block, line, _ in words:
        groups[block, line].append((x0, y0, x1, y1, word))
    lines = []
    for group in groups.values():
        group.sort()
        box = [
            min(w[0] for w in group),
            min(w[1] for w in group),
            max(w[2] for w in group),
            max(w[3] for w in group),
        ]
        lines.append(([round(v, 1) for v in box], " ".join(w[4] for w in group)))
    return sorted(lines, key=lambda row: (round(row[0][1] / 3), row[0][0]))


def scan_lines(page):
    from ocrmac import ocrmac

    pix = page.get_pixmap(dpi=200)
    recognized = ocrmac.OCR(
        pix.pil_image(), recognition_level="accurate", language_preference=["en-US"]
    ).recognize()
    w, h = page.rect.width, page.rect.height
    lines = []
    for text, confidence, (x, y, dx, dy) in recognized:
        if confidence < 0.35:
            continue
        box = [x * w, (1 - y - dy) * h, (x + dx) * w, (1 - y) * h]
        lines.append(([round(v, 1) for v in box], text))
    return sorted(lines, key=lambda row: (round(row[0][1] / 4), row[0][0]))


def folios(pages):
    """Un folio visible doit être corroboré par une séquence ou une étiquette PDF."""
    candidates = {}
    labels = {}
    for n, (label, lines) in pages.items():
        label = label.replace("<FEFF>", "").strip()
        edge = [s.strip() for _, s in lines[:4] + lines[-4:]]
        values = set()
        for s in edge:
            words = s.split()
            for w in words[:1] + words[-1:]:
                if re.fullmatch(r"[0-9]{1,4}|[ivxlcdmIVXLCDM]{1,7}", w):
                    values.add(w.lower())
        candidates[n] = values
        if label and label.lower() in values:
            labels[n] = label
    for n, values in candidates.items():
        if n in labels:
            continue
        consistent = [
            v
            for v in values
            if v.isdecimal()
            and sum(
                str(int(v) + d) in candidates.get(n + d, ()) for d in (-2, -1, 1, 2)
            )
            >= 2
        ]
        if len(consistent) == 1:
            labels[n] = consistent[0]
    # Seulement des séquences encadrées par deux folios observés concordants.
    observed = sorted(labels)
    for left, right in zip(observed, observed[1:]):
        if right - left > 4 or not (
            labels[left].isdecimal() and labels[right].isdecimal()
        ):
            continue
        if int(labels[right]) - int(labels[left]) == right - left:
            for n in range(left + 1, right):
                expected = str(int(labels[left]) + n - left)
                declared = pages[n][0].replace("<FEFF>", "").strip()
                if not declared or declared == expected:
                    labels[n] = expected
    return labels


def build(size="512"):
    chunks = defaultdict(list)
    for row in map(json.loads, (ROOT / "chunks" / f"chunks-{size}.jsonl").open()):
        chunks[row["book"]].append(row)
    out = ROOT / "index" / f"provenance-{size}.sqlite"
    out.parent.mkdir(exist_ok=True)
    fd, name = tempfile.mkstemp(suffix=".tmp", dir=out.parent)
    os.close(fd)
    try:
        with sqlite3.connect(name) as conn:
            conn.executescript("""
                CREATE TABLE pages (book TEXT, page TEXT, folio TEXT, lines BLOB, PRIMARY KEY(book,page));
                CREATE TABLE chunks (id TEXT PRIMARY KEY, digest TEXT, segments TEXT);
                CREATE TABLE books (book TEXT PRIMARY KEY, sha TEXT, file TEXT);
            """)
            for meta in csv.DictReader((ROOT / "manifest.csv").open()):
                if meta["inclus"] != "oui":
                    continue
                path = ROOT / "corpus" / meta["fichier"]
                book = path.stem
                docrows = list(
                    map(json.loads, (ROOT / "extracted" / f"{book}.jsonl").open())
                )
                conn.execute(
                    "INSERT INTO books VALUES(?,?,?)",
                    (book, hashlib.sha256(path.read_bytes()).hexdigest(), path.name),
                )
                pdf = path.suffix == ".pdf"
                if pdf:
                    with pymupdf.open(path) as doc:
                        reader = (
                            scan_lines
                            if meta["texte"] == "OCR_REQUIS"
                            else native_lines
                        )
                        pages = {
                            i: (p.get_label(), reader(p)) for i, p in enumerate(doc, 1)
                        }
                    labels = folios(pages)
                    for n, (_, lines) in pages.items():
                        conn.execute(
                            "INSERT INTO pages VALUES(?,?,?,?)",
                            (
                                book,
                                str(n),
                                labels.get(n),
                                gzip.compress(
                                    json.dumps(lines, ensure_ascii=False).encode(),
                                    compresslevel=1,
                                ),
                            ),
                        )
                    text, bounds = build_text(docrows)
                    starts = [pos for pos, _ in bounds]
                else:
                    chapters = {r["page"]: build_text([r])[0] for r in docrows}
                for c in chunks[book]:
                    a, b = c["char_start"], c["char_end"]
                    if pdf:
                        left = bisect_right(starts, a) - 1
                        right = bisect_right(starts, b - 1)
                        segments = [
                            [max(0, pos - a), str(n), max(0, a - pos)]
                            for pos, n in bounds[left:right]
                        ]
                    else:
                        text = chapters[c["page_start"]]
                        segments = [[0, c["page_start"], a]]
                    if text[a:b] != c["text"]:
                        raise ValueError(f"Position incohérente pour {c['chunk_id']}")
                    conn.execute(
                        "INSERT INTO chunks VALUES(?,?,?)",
                        (
                            c["chunk_id"],
                            hashlib.sha256(c["text"].encode()).hexdigest(),
                            json.dumps(segments),
                        ),
                    )
                print(
                    book,
                    f"{len(labels)}/{len(pages)} folios" if pdf else "EPUB",
                    flush=True,
                )
            conn.commit()
        conn.close()
        os.replace(name, out)
    finally:
        Path(name).unlink(missing_ok=True)


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "512")
