"""Construit l'index privé des pages, chapitres et énoncés formels à partir des éditions vérifiées."""

import csv
import gzip
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
LABEL = re.compile(
    r"^[\s#*_]*(definition|theorem|postulate|corollary|axiom|norm|hypothesis|lemma)\s+(\d+(?:\.\d+)*)(?:\.(?!\d)|:|\s|$)",
    re.I,
)


def chapter_titles(pdf):
    starts = {}
    for number, page in enumerate(pdf, 1):
        lines = [line.strip() for line in page.get_text().splitlines() if line.strip()]
        if len(lines) < 2 or not re.fullmatch(
            r"CHAPTER\s*[\dIVXl ]+\.?", lines[0], re.I
        ):
            continue
        title = []
        for line in lines[1:4]:
            if not line.isupper() or len(line) < 2 or line.isdigit():
                break
            title.append(line)
        if title:
            starts[number] = (
                " ".join(title)
                .title()
                .replace("Underst Anding", "Understanding")
                .replace("System A Tizing", "Systematizing")
            )
    for level, title, number in pdf.get_toc():
        match = re.match(r"Chapter [0-9]+\s*[-–]\s*(.+)", title, re.I)
        if match and number > 0:
            starts[number] = match[1]
    return starts


def searchable_text(lines):
    return re.sub(r"(?<=\w)-\s*\n\s*(?=[a-z])", "", "\n".join(lines)).replace(
        "\u00ad", ""
    )


def segments(text):
    words = list(re.finditer(r"\S+", text))
    for start in range(0, len(words), 65):
        stop = min(start + 86, len(words))
        yield (
            words[start].start(),
            " ".join(text[words[start].start() : words[stop - 1].end()].split()),
        )
        if stop == len(words):
            break


def build():
    source = ROOT / "index/provenance-512.sqlite"
    destination = ROOT / "index/lecture.sqlite"
    input_db = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
    handle, temporary = tempfile.mkstemp(dir=destination.parent, suffix=".sqlite.tmp")
    os.close(handle)
    conn = sqlite3.connect(temporary)
    try:
        conn.executescript("""
          CREATE TABLE books(book TEXT PRIMARY KEY, title TEXT, year TEXT, authors TEXT, edition TEXT, file TEXT);
          CREATE TABLE chapters(book TEXT, page INTEGER, title TEXT, PRIMARY KEY(book,page));
          CREATE TABLE pages(id INTEGER PRIMARY KEY, book TEXT, page TEXT, folio TEXT, chapter TEXT, UNIQUE(book,page));
          CREATE TABLE spans(page_id INTEGER PRIMARY KEY, first_row INTEGER, last_row INTEGER);
          CREATE TABLE labels(page_id INTEGER, kind TEXT, number TEXT, excerpt TEXT, uid TEXT PRIMARY KEY);
          CREATE TABLE mentions(origin TEXT, target TEXT, excerpt TEXT, PRIMARY KEY(origin,target));
          CREATE INDEX mentions_target ON mentions(target);
          CREATE TEMP TABLE pending(origin TEXT,book TEXT,kind TEXT,number TEXT,excerpt TEXT);
          CREATE INDEX labels_page ON labels(page_id);
          CREATE VIRTUAL TABLE passages USING fts5(text, heading, page_id UNINDEXED, offset UNINDEXED, tokenize='porter unicode61');
          CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
        """)
        manifest = list(csv.DictReader((ROOT / "manifest.csv").open()))
        for row in manifest:
            if row["inclus"] != "oui":
                continue
            file = ROOT / "corpus" / row["fichier"]
            book = file.stem
            (sha,) = input_db.execute(
                "SELECT sha FROM books WHERE book=?", (book,)
            ).fetchone()
            if sha != hashlib.sha256(file.read_bytes()).hexdigest():
                raise ValueError(f"Édition modifiée : {book}")
            conn.execute(
                "INSERT INTO books VALUES(?,?,?,?,?,?)",
                (book, row["titre"], row["annee"], row["auteurs"], sha, file.name),
            )
            titles = {}
            if row["type"] == "treatise":
                with fitz.open(file) as pdf:
                    titles = chapter_titles(pdf)
                if not titles:
                    raise ValueError(f"Chapitres introuvables : {book}")
                conn.executemany(
                    "INSERT INTO chapters VALUES(?,?,?)",
                    [(book, p, t) for p, t in titles.items()],
                )
            if file.suffix == ".pdf":
                pages = (
                    (p, f, [s for _, s in json.loads(gzip.decompress(blob))])
                    for p, f, blob in input_db.execute(
                        "SELECT page,folio,lines FROM pages WHERE book=? ORDER BY CAST(page AS INTEGER)",
                        (book,),
                    )
                )
            else:
                extracted = (
                    (ROOT / "extracted" / (book + ".jsonl")).read_text().splitlines()
                )
                pages = (
                    (str(d["page"]), "", d["text"].splitlines())
                    for d in map(json.loads, extracted)
                )
            chapter = ""
            for page, folio, lines in pages:
                chapter = titles.get(int(page), chapter) if page.isdecimal() else page
                page_id = conn.execute(
                    "INSERT INTO pages(book,page,folio,chapter) VALUES(?,?,?,?)",
                    (book, page, folio, chapter),
                ).lastrowid
                body = searchable_text(lines)
                heading = row["titre"] + " " + chapter
                first = conn.execute(
                    "SELECT coalesce(max(rowid),0)+1 FROM passages"
                ).fetchone()[0]
                conn.executemany(
                    "INSERT INTO passages(text,heading,page_id,offset) VALUES(?,?,?,?)",
                    [(s, heading, page_id, pos) for pos, s in segments(body)],
                )
                last = conn.execute(
                    "SELECT coalesce(max(rowid),0) FROM passages"
                ).fetchone()[0]
                conn.execute("INSERT INTO spans VALUES(?,?,?)", (page_id, first, last))
                marks = [
                    (i, LABEL.match(line))
                    for i, line in enumerate(lines)
                    if LABEL.match(line)
                ]
                for j, (i, match) in enumerate(marks):
                    kind, number = match[1].casefold(), match[2]
                    marker = f"{book}/{page}/{kind}/{number}"
                    finish = marks[j + 1][0] if j + 1 < len(marks) else len(lines)
                    body = searchable_text(lines[i : min(i + 18, finish)])
                    preview = " ".join(body.split()[:16])
                    conn.execute(
                        "INSERT OR IGNORE INTO labels VALUES(?,?,?,?,?)",
                        (page_id, kind, number, preview, marker),
                    )
                    ref_pattern = r"\b(definition|theorem|corollary|axiom|postulate|norm|lemma|hypothesis)\s+(\d+(?:\.\d+)*)\b"
                    for mention in re.finditer(ref_pattern, body, re.I):
                        if (mention[1].casefold(), mention[2]) == (kind, number):
                            continue
                        prefix = body[: mention.start()].split()[-5:]
                        suffix = body[mention.start() :].split()[:9]
                        conn.execute(
                            "INSERT INTO pending VALUES(?,?,?,?,?)",
                            (
                                marker,
                                book,
                                mention[1].casefold(),
                                mention[2],
                                " ".join(prefix + suffix),
                            ),
                        )
            print(book, len(titles), "chapitres", flush=True)
        conn.execute("""INSERT OR IGNORE INTO mentions
                        SELECT p.origin,min(l.uid),p.excerpt FROM pending p JOIN pages pg ON pg.book=p.book
                        JOIN labels l ON l.page_id=pg.id AND l.kind=p.kind AND l.number=p.number
                        GROUP BY p.origin,p.kind,p.number HAVING count(DISTINCT l.uid)=1""")
        conn.execute(
            "INSERT INTO meta VALUES('provenance',?)",
            (hashlib.sha256(source.read_bytes()).hexdigest(),),
        )
        conn.execute("INSERT INTO passages(passages) VALUES('optimize')")
        conn.commit()
        assert conn.execute("PRAGMA quick_check").fetchone() == ("ok",)
        conn.close()
        os.replace(temporary, destination)
    finally:
        conn.close()
        input_db.close()
        Path(temporary).unlink(missing_ok=True)


if __name__ == "__main__":
    build()
