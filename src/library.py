"""Accès en lecture seule à la bibliothèque paginée et au référentiel éditorial."""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import unicodedata
from collections import Counter
from contextlib import closing
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "index/lecture.sqlite"
CATALOG = json.loads(Path(__file__).with_name("referentiel.json").read_text())
NODES = CATALOG["nodes"]
LOGGER = logging.getLogger(__name__)
FORMAL_LABELS = {
    "definition": "definition",
    "postulat": "postulate",
    "postulate": "postulate",
    "theoreme": "theorem",
    "theorem": "theorem",
    "corollaire": "corollary",
    "corollary": "corollary",
    "axiome": "axiom",
    "axiom": "axiom",
    "norme": "norm",
    "norm": "norm",
    "hypothese": "hypothesis",
    "hypothesis": "hypothesis",
}
STOP = set(
    """a an and are as at be by can could did do does for from has have how i in into is it its me of on or that the their this to was what when where which who why with would according bunge mario book volume passage page find remember dans de des du en et il je la le les où ou par pour que quel quelle quels quelles qui se sur un une vous est cherche retrouver livre tome""".split()
)


def fold(text):
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in text if not unicodedata.combining(c))


def words(text):
    return [
        w for w in re.findall(r"[^\W_]+", fold(text)) if w not in STOP and len(w) > 1
    ]


def connect():
    db = sqlite3.connect(DATABASE.resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


@lru_cache(maxsize=1)
def translator():
    from transformers import MarianMTModel, MarianTokenizer

    model_id = "Helsinki-NLP/opus-mt-fr-en"
    revision = "c4aed37b318c763fd177aa449b44e3b783cc6c02"
    return (
        MarianTokenizer.from_pretrained(model_id, revision=revision),
        MarianMTModel.from_pretrained(model_id, revision=revision).eval(),
    )


@lru_cache(maxsize=192)
def translate(question):
    import torch

    tokenizer, model = translator()
    batch = tokenizer(question, return_tensors="pt", truncation=True, max_length=256)
    with torch.inference_mode():
        ids = model.generate(**batch, num_beams=1, max_length=100)
    return tokenizer.decode(ids[0], skip_special_tokens=True)


def suggested_nodes(question, limit=6):
    tokens = set(words(question))
    matches = []
    for key, n in NODES.items():
        labels = [n["title"], *n["tags"]]
        overlap = max((len(tokens & set(words(label))) for label in labels), default=0)
        exact = any(fold(label) == fold(question.strip()) for label in labels)
        explicit = lexical_match(question, n["title"])
        quoted = lexical_match(question, n["source"]["quote"])
        if overlap:
            matches.append((not (exact or quoted), not explicit, -overlap, key))
    matches.sort()
    return [key for *_, key in matches[:limit]]


def limited_excerpt(text, terms, phrase="", limit=16):
    if phrase:
        found = literal_span(text, phrase)
        if found is not None:
            left, right = found
            exact = text[left:right]
            return " ".join(exact.split()[:limit])
    tokens = list(re.finditer(r"\S+", text))
    if not tokens:
        return ""
    scores = [sum(term in terms for term in words(m[0])) for m in tokens]
    start = max(range(len(tokens)), key=lambda i: sum(scores[i : i + limit]))
    return text[
        tokens[start].start() : tokens[min(len(tokens), start + limit) - 1].end()
    ]


def fts(db, terms, *, phrase=False, limit=100):
    if not terms:
        return []

    def quote(term):
        return '"' + term.replace('"', '""') + '"'

    expr = (
        quote(" ".join(terms))
        if phrase
        else " OR ".join(quote(t) for t in dict.fromkeys(terms))
    )
    return db.execute(
        """SELECT rowid,page_id,text,bm25(passages,1.0,0.2,0,0) AS rank
                         FROM passages WHERE passages MATCH ? ORDER BY rank LIMIT ?""",
        (expr, limit),
    ).fetchall()


def location(row):
    page = str(row["page"])
    if page.isdecimal():
        return (
            (("p. " + row["folio"] + " du livre · ") if row["folio"] else "")
            + "PDF p. "
            + page
        )
    return page


def describe_page(db, pid):
    return dict(
        db.execute(
            """SELECT p.id,p.book,p.page,p.folio,p.chapter,b.year,b.title,b.authors,b.file,b.edition
                              FROM pages p JOIN books b ON b.book=p.book WHERE p.id=?""",
            (pid,),
        ).fetchone()
    )


def query_phrases(q):
    quoted = re.findall(r'[«“"]([^»”"]{8,220})[»”"]', q)
    if quoted:
        return quoted[:2]
    return [q.rstrip(" ?.")] if 3 <= len(q.split()) <= 22 else []


def form_match(question):
    labels = "|".join(FORMAL_LABELS)
    return re.search(rf"\b({labels})\s+(\d+(?:\.\d+)*)\b", fold(question))


def formal_hits(db, question):
    match = form_match(question)
    if match is None:
        return []
    return db.execute(
        """SELECT l.page_id,l.excerpt AS text,p.book,p.chapter,b.title
           FROM labels l JOIN pages p ON p.id=l.page_id JOIN books b ON b.book=p.book
           WHERE l.kind=? AND l.number=?""",
        (FORMAL_LABELS[match[1]], match[2]),
    ).fetchall()


def lexical_match(text, phrase):
    return literal_span(text, phrase) is not None


def literal_span(text, phrase):
    pattern = r"[^\W_]+"
    wanted = re.findall(pattern, fold(phrase))
    if not wanted:
        return None
    tokens = list(re.finditer(pattern, text))
    normalized = [fold(token[0]) for token in tokens]
    count = len(wanted)
    for start in range(len(tokens) - count + 1):
        if normalized[start : start + count] == wanted:
            return tokens[start].start(), tokens[start + count - 1].end()
    return None


def search_library(question, *, english=None, semantic=True, limit=5):
    question = " ".join(question.split())[:800]
    if len(question) < 3:
        return []
    with closing(connect()) as db:
        exact = []
        phrases = query_phrases(question)
        for phrase in phrases:
            tokens = re.findall(r"[^\W_]+", fold(phrase))[:30]
            if tokens:
                exact.extend(
                    row
                    for row in fts(db, tokens, phrase=True, limit=36)
                    if lexical_match(row["text"], phrase)
                )
        if english is None:
            if exact:
                english = question
            else:
                try:
                    english = translate(question)
                except (OSError, ValueError, ImportError, RuntimeError):
                    english = question
        terms = words(english)
        original = words(question)
        ranked = Counter()
        snippets = {}

        def add(rows, weight):
            seen = set()
            for row in rows:
                pid = row["page_id"]
                if pid not in seen:
                    ranked[pid] += weight / (15 + len(seen))
                    seen.add(pid)
                    snippets.setdefault(pid, row["text"])

        add(exact, 12)
        formal = formal_hits(db, question)
        if formal:
            context = set(terms + original)
            formal.sort(
                key=lambda row: (
                    -len(
                        context
                        & set(words(f"{row['title']} {row['chapter']} {row['text']}"))
                    )
                )
            )
            add(formal, 5 if len(formal) == 1 else 2.5)
        normalized = fold(question).strip(" ?.")
        for key, node in NODES.items():
            notation = node.get("notation", {}).get("formula")
            if notation and normalized == fold(notation):
                source = node_source(key)
                ranked[source["id"]] += 1
                snippets.setdefault(source["id"], source["excerpt"])
        add(fts(db, terms[:28]), 2)
        if original != terms:
            add(fts(db, original[:28]), 0.7)
        if semantic and not exact:
            from search import search

            try:
                hits = search(question, mode="dense", k=18, table="bunge_512")
            except (OSError, ValueError, RuntimeError):
                LOGGER.warning("Recherche vectorielle indisponible", exc_info=True)
                hits = []
            seen = set()
            for i, hit in enumerate(hits):
                start, end = str(hit["page_start"]), str(hit["page_end"])
                pages = (
                    (str(p) for p in range(int(start), int(end) + 1))
                    if start.isdecimal() and end.isdecimal()
                    else (start, end)
                )
                for page in pages:
                    found = db.execute(
                        "SELECT id FROM pages WHERE book=? AND page=?",
                        (hit["book"], page),
                    ).fetchone()
                    if not found or found[0] in seen:
                        continue
                    pid = found[0]
                    seen.add(pid)
                    ranked[pid] += 1.3 / (15 + i)
                    if pid not in snippets:
                        page_segments = db.execute(
                            "SELECT text FROM spans JOIN passages ON passages.rowid BETWEEN spans.first_row AND spans.last_row WHERE spans.page_id=?",
                            (pid,),
                        ).fetchall()
                        if page_segments:
                            snippets[pid] = max(
                                (r[0] for r in page_segments),
                                key=lambda s: len(set(words(s)) & set(terms)),
                            )
        result = []
        for pid, _ in ranked.most_common():
            if pid not in snippets:
                continue
            item = describe_page(db, pid)
            item["pages"] = location(item)
            phrase = next((p for p in phrases if lexical_match(snippets[pid], p)), "")
            item["excerpt"] = limited_excerpt(
                snippets[pid], set(terms + original), phrase
            )
            result.append(item)
            if len(result) == limit:
                break
        return result


def on_page(book, page):
    return [
        key
        for key, n in NODES.items()
        if n["source"]["book"] == book and str(n["source"]["page"]) == str(page)
    ]


def neighbours(key):
    return [r for r in CATALOG["relations"] if key in (r["origin"], r["target"])]


@lru_cache(maxsize=128)
def node_source(key):
    source = NODES[key]["source"]
    with closing(connect()) as db:
        row = db.execute(
            "SELECT p.id FROM pages p JOIN books b ON b.book=p.book WHERE p.book=? AND p.page=? AND b.edition=?",
            (source["book"], str(source["page"]), source["edition"]),
        ).fetchone()
        if row is None:
            raise ValueError("Édition du référentiel incompatible")
        item = describe_page(db, row[0])
    item.update(excerpt=source["quote"], pages=location(item))
    return item


def core_context():
    return "\n".join(
        f"{NODES[key]['title']} · {NODES[key]['text']} ({node_source(key)['title']}, {node_source(key)['pages']})"
        for key in CATALOG["core"]
    )


def question_scope(question):
    """Indique la précision nécessaire pour attribuer une page ou un avis à l'auteur."""
    q = fold(question)
    if re.search(
        r"\bedition\s+(allemande|italienne|russe|francaise|espagnole|portugaise)\b", q
    ):
        return (
            "source indisponible",
            "La pagination disponible est celle des éditions anglaises indexées. Une autre édition demande sa propre concordance.",
        )
    if re.search(r"\b(prochain|futur|demain)\w*\b", q) and re.search(
        r"\b(tirage|meteo|cours boursier|numeros gagnants)\b", q
    ):
        return (
            "source indisponible",
            "Les ouvrages indexés ne permettent pas d’établir ce résultat futur.",
        )
    contemporary = re.search(
        r"\b(?:gpt[- ]?\d|chatgpt|gemini\s+\d|llama\s+\d|claude\s+\d)", q
    )
    if contemporary and re.search(
        r"\b(avis personnel|teste|essaye|utilise|a publie|affirme|aurait pense|pensait)\b",
        q,
    ):
        return (
            "source indisponible",
            "Aucun témoignage de Bunge sur ce modèle dans le corpus. L’Atelier permet d’examiner une transposition conditionnelle.",
        )
    ref = form_match(q)
    if ref:
        vocabulary = (
            set(words(q))
            - set(words(ref[0]))
            - set(
                "cherche recherche trouve ouvrage agit quel ouvrage page numero livre chez situer retrouver donner texte passage".split()
            )
        )
        if not vocabulary or "de quel ouvrage" in q:
            kind = FORMAL_LABELS[ref[1]]
            with closing(connect()) as db:
                books = db.execute(
                    """SELECT DISTINCT b.title FROM labels l JOIN pages p ON p.id=l.page_id JOIN books b ON b.book=p.book
                                    WHERE l.kind=? AND l.number=? ORDER BY b.year""",
                    (kind, ref[2]),
                ).fetchall()
            if len(books) > 1:
                return (
                    "clarifier",
                    "Ce numéro figure dans plusieurs ouvrages. Précisez le titre ou le sujet. Par exemple : "
                    + " ; ".join(r[0] for r in books[:3])
                    + ".",
                )
    return "localiser", ""


def linked_evidence(keys, limit=6):
    """Étend les appuis d'une lecture par des liens sourcés, y compris les restrictions."""
    initial = list(dict.fromkeys(k for k in keys if k in NODES))[:limit]
    selected = dict.fromkeys(initial)
    frontier = initial
    for _ in range(2):
        if len(selected) == limit:
            break
        next_hop = []
        relations = [link for key in frontier for link in neighbours(key)]
        relations.sort(key=lambda link: link["kind"] != "Lien explicite")
        for link in relations:
            for key in (link["witness"], link["origin"], link["target"]):
                if key not in selected and len(selected) < limit:
                    selected[key] = None
                    next_hop.append(key)
        frontier = next_hop
    return list(selected)


def passage_context(source):
    """Donne au vérificateur une courte fenêtre autour de la citation de l’édition."""
    passage = source["excerpt"]
    edition = source.get("edition")
    if not edition or not passage:
        return passage
    with closing(connect()) as db:
        rows = db.execute(
            """SELECT t.text FROM pages p JOIN books b ON b.book=p.book
               JOIN spans a ON a.page_id=p.id JOIN passages t ON t.rowid BETWEEN a.first_row AND a.last_row
               WHERE p.book=? AND p.page=? AND b.edition=?""",
            (source["book"], str(source["page"]), edition),
        ).fetchall()
    return next(
        (row["text"] for row in rows if lexical_match(row["text"], passage)), passage
    )


LABELS_FR = {
    "definition": "Définition",
    "postulate": "Postulat",
    "theorem": "Théorème",
    "axiom": "Axiome",
    "corollary": "Corollaire",
    "norm": "Norme",
    "hypothesis": "Hypothèse",
    "lemma": "Lemme",
}


def formal_markers(book, page=None, *, chapter=None):
    with closing(connect()) as db:
        rows = db.execute(
            """SELECT l.uid,l.kind,l.number,p.page,p.folio FROM labels l JOIN pages p ON p.id=l.page_id
                           WHERE p.book=? AND (? IS NULL OR p.page=?) AND (? IS NULL OR p.chapter=?)
                           ORDER BY CAST(p.page AS INTEGER),l.rowid""",
            (book, page, page, chapter, chapter),
        ).fetchall()
    return [
        (
            f"{LABELS_FR[r['kind']]} {r['number']} · "
            + (f"livre p. {r['folio']}" if r["folio"] else f"PDF {r['page']}"),
            r["uid"],
        )
        for r in rows
    ]


def chapter_openings(book):
    with closing(connect()) as db:
        return [
            (r["title"], r["title"])
            for r in db.execute(
                "SELECT title FROM chapters WHERE book=? ORDER BY page", (book,)
            )
        ]


def chapter_source(book, chapter):
    with closing(connect()) as db:
        row = db.execute(
            """SELECT p.id, t.text FROM chapters c JOIN pages p ON p.book=c.book AND p.page=CAST(c.page AS TEXT)
               JOIN spans a ON a.page_id=p.id JOIN passages t ON t.rowid=a.first_row
               WHERE c.book=? AND c.title=?""",
            (book, chapter),
        ).fetchone()
        if row is None:
            return None
        source = describe_page(db, row["id"])
    source.update(
        excerpt=limited_excerpt(row["text"], set(words(chapter))),
        pages=location(source),
    )
    return source


def read_marker(uid):
    with closing(connect()) as db:
        mark = db.execute("SELECT * FROM labels WHERE uid=?", (uid,)).fetchone()
        if not mark:
            return None
        source = describe_page(db, mark["page_id"])
        source.update(excerpt=mark["excerpt"], pages=location(source))
        title = f"{LABELS_FR[mark['kind']]} {mark['number']}"
        edges = []
        for r in db.execute(
            """SELECT m.origin,m.target,m.excerpt,l.uid,l.kind,l.number,p.page
                               FROM mentions m JOIN labels l ON l.uid=CASE WHEN m.origin=? THEN m.target ELSE m.origin END
                               JOIN pages p ON p.id=l.page_id WHERE m.origin=? OR m.target=? ORDER BY l.rowid""",
            (uid, uid, uid),
        ):
            origin_id = db.execute(
                "SELECT page_id FROM labels WHERE uid=?", (r["origin"],)
            ).fetchone()[0]
            witness = describe_page(db, origin_id)
            witness.update(excerpt=r["excerpt"], pages=location(witness))
            direction = (
                "renvoie à" if uid == r["origin"] else "est cité dans le passage de"
            )
            caption = (
                f"{direction} {LABELS_FR[r['kind']]} {r['number']} · PDF {r['page']}"
            )
            edges.append((caption, r["uid"], witness))
    return title, source, edges
