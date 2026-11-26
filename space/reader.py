"""Vues de lecture, de navigation dans le système et de discussion des prémisses."""

import html
import re
from contextlib import closing
from urllib.parse import quote

import gradio as gr

from library import (
    CATALOG,
    NODES,
    chapter_openings,
    chapter_source,
    connect,
    fold,
    formal_markers,
    read_marker,
    neighbours,
    node_source,
    on_page,
    question_scope,
    search_library,
    suggested_nodes,
)
from workshop import (
    DOSSIERS,
    assess,
    choose_dossier,
    formal_happiness,
    formal_rights,
    open_question,
)

esc = html.escape


def card(source, local):
    link = ""
    if local and source["file"].endswith(".pdf") and str(source["page"]).isdecimal():
        pdf = (local / source["file"]).resolve()
        if pdf.parent == local.resolve() and pdf.is_file():
            link = f'<a href="/gradio_api/file={quote(str(pdf))}#page={int(source["page"])}" target="_blank" rel="noopener">Ouvrir cette page ↗</a>'
    return (
        f'<article class="reading-card"><header><strong>{esc(source["title"])}</strong> '
        f"<small>{esc(str(source['year']))} · {esc(source['authors'])}</small></header>"
        f'<p class="folio">{esc(source["pages"])}</p><blockquote lang="en">{esc(source["excerpt"])}</blockquote>{link}</article>'
    )


def coverage(book=""):
    with closing(connect()) as db:
        totals = dict(
            db.execute(
                "SELECT 'ouvrages',count(*) FROM books UNION ALL SELECT 'chapitres',count(*) FROM chapters"
            )
        )
        entries = db.execute(
            "SELECT book,title FROM books ORDER BY year,title"
        ).fetchall()
        if not book:
            book = next(
                r["book"] for r in entries if r["book"].startswith("treatise-1-")
            )
        chapters = db.execute(
            "SELECT page,title FROM chapters WHERE book=? ORDER BY page", (book,)
        ).fetchall()
        pages = db.execute(
            "SELECT count(*) FROM pages WHERE book=?", (book,)
        ).fetchone()[0]
        count = db.execute(
            "SELECT count(*) FROM labels JOIN pages ON pages.id=labels.page_id WHERE book=?",
            (book,),
        ).fetchone()[0]
    sourced = [n for n in NODES.values() if n["source"]["book"] == book]
    rows = []
    for i, row in enumerate(chapters):
        last = chapters[i + 1]["page"] if i + 1 < len(chapters) else float("inf")
        refs = sum(row["page"] <= n["source"]["page"] < last for n in sourced)
        rows.append(
            f"<li>{esc(row['title'])} · PDF p. {row['page']} · {refs} fiche(s) documentée(s)</li>"
        )
    text = (
        f"<p>{totals['ouvrages']} ouvrages indexés · {totals['chapitres']} chapitres du Traité repérés. "
        f"Pour cet ouvrage, {pages} pages ou sections, {len(sourced)} fiches documentées et {count} occurrences de libellés formels détectées.</p>"
    )
    return (
        text + ("<ol>" + "".join(rows) + "</ol>" if rows else ""),
        [(r["title"], r["book"]) for r in entries],
        book,
    )


def atlas_view(key, local):
    if key not in NODES:
        found = read_marker(key) if key else None
        if not found:
            return (
                "<p>Choisissez une notion ou un repère dans la bibliothèque.</p>",
                gr.Dropdown(choices=[], value=None),
                "",
            )
        title, source, edges = found
        choices = [(label, uid) for label, uid, _ in edges]
        items = "".join(
            f'<details class="reading-edge"><summary>{esc(label)}</summary><p>Renvoi textuel détecté, rôle logique à examiner.</p>{card(witness, local)}</details>'
            for label, _, witness in edges
        )
        return (
            f"<h3>{esc(title)}</h3><p>{esc(source['chapter'])} · repère détecté dans l’édition</p>"
            + card(source, local)
            + items,
            gr.Dropdown(
                choices=choices,
                value=choices[0][1] if choices else None,
                interactive=bool(choices),
            ),
            "",
        )
    node = NODES[key]
    edges = neighbours(key)
    items = []
    choices = []
    for edge in edges:
        outgoing = edge["origin"] == key
        other = edge["target"] if outgoing else edge["origin"]
        choices.append((NODES[other]["title"], other))
        label = f"{NODES[edge['origin']]['title']} → {edge['verb']} → {NODES[edge['target']]['title']}"
        items.append(
            f'<details class="reading-edge"><summary>{esc(label)}</summary><p>{esc(edge["kind"])}</p>'
            + card(node_source(edge["witness"]), local)
            + "</details>"
        )
    notation = node.get("notation")
    formula = (
        (
            f'<p class="formula">{esc(notation["formula"])}</p><p>{esc(notation["gloss"])}</p>'
            f"<small>{esc(notation['status'])}</small>"
        )
        if notation
        else ""
    )
    content = f"<h3>{esc(node['title'])}</h3><small>{esc(node['domain'])} · {esc(node['kind'])}</small><p>{esc(node['text'])}</p>{formula}"
    comparison = [
        e
        for e in edges
        if e["kind"] in ("Comparaison entre ouvrages", "Rapprochement éditorial")
        and NODES[e["origin"]]["source"]["book"] != NODES[e["target"]]["source"]["book"]
    ]
    compare = ""
    for e in comparison:
        keys = sorted((e["origin"], e["target"]), key=lambda k: node_source(k)["year"])
        compare += (
            '<div class="compare-grid">'
            + "".join(card(node_source(k), local) for k in keys)
            + "</div>"
        )
    branches = "".join(
        f'<li><a href="#atlas-rel-{i}">{esc(title)}</a></li>'
        for i, (title, _) in enumerate(choices, 1)
    )
    diagram = (
        (
            f'<nav class="concept-map" aria-label="Carte locale"><strong>{esc(node["title"])}</strong><ul>{branches}</ul></nav>'
        )
        if branches
        else ""
    )
    items = [
        item.replace(
            '<details class="reading-edge"',
            f'<details id="atlas-rel-{i}" class="reading-edge"',
            1,
        )
        for i, item in enumerate(items, 1)
    ]
    return (
        content + diagram + card(node_source(key), local) + "".join(items),
        gr.Dropdown(
            choices=choices,
            value=choices[0][1] if choices else None,
            interactive=bool(choices),
        ),
        compare or "<p>Aucune comparaison éditée pour cette notion.</p>",
    )


def dossier_view(dossier, changes, local):
    if not dossier:
        return ""
    states = assess(dossier["steps"], changes)
    sections = [f"<h3>{esc(dossier['title'])}</h3>"]
    for s in dossier["steps"]:
        state = states[s["id"]]
        sources = "".join(card(r, local) for r in s["sources"])
        for f in s.get("external", []):
            sources += f'<p><a href="{esc(f["url"], quote=True)}" target="_blank" rel="noopener">{esc(f["title"])}</a></p>'
        title_by_id = {r["id"]: r["title"] for r in dossier["steps"]}
        supports = " ou ".join(
            " + ".join(title_by_id[p] for p in group) for group in s["supports"]
        )
        replacement = changes.get(s["id"], "")
        sections.append(
            f'<article class="argument-step"><small>{esc(s["role"])} · {esc(state)}</small><h4>{esc(s["title"])}</h4>'
            f"<p>{esc(s['text'])}</p>"
            + (
                f"<p>Hypothèse du lecteur : {esc(replacement)}</p>"
                if replacement
                else ""
            )
            + (f"<p>Appuis : {esc(supports)}</p>" if supports else "")
            + (
                f"<details><summary>Consulter les sources</summary>{sources}</details>"
                if sources
                else ""
            )
            + "</article>"
        )
    sections.append(
        f"<h4>Objection</h4><p>{esc(dossier['objection'])}</p><h4>Question ouverte</h4><p>{esc(dossier['open'])}</p>"
    )
    formalizations = {
        "restriction": formal_rights,
        "theoreme-bonheur": formal_happiness,
    }
    for identifier in formalizations.keys() & {s["id"] for s in dossier["steps"]}:
        fragment = formalizations[identifier]()
        headers = "".join(
            f"<th scope='col'>{esc(label)}</th>" for label in fragment["headers"]
        )
        rows = "".join(
            "<tr>" + "".join(f"<td>{int(value)}</td>" for value in row) + "</tr>"
            for row in fragment["rows"]
        )
        sections.append(
            f'<details><summary>Vérifier le fragment formel</summary><p class="formula">{esc(fragment["formula"])}</p><p>{esc(fragment["gloss"])}</p>'
            f"<table><thead><tr>{headers}</tr></thead><tbody>"
            + rows
            + "</tbody></table></details>"
        )
    sections.append(
        "<details><summary>Cadre philosophique de cette lecture</summary>"
        + "".join(card(node_source(key), local) for key in CATALOG["core"])
        + "</details>"
    )
    if dossier.get("notice"):
        sections.append('<p role="status">' + esc(dossier["notice"]) + "</p>")
    return "".join(sections)


def build_reader(legacy, local, create_dossier, max_chars):
    options = sorted(
        ((n["title"], k) for k, n in NODES.items()), key=lambda x: fold(x[0])
    )
    coverage_html, book_options, first_book = coverage()
    research = gr.State([])
    saved_question = gr.State("")
    inline_dossier = gr.State({})
    dossier = gr.State({})
    changes = gr.State({})
    domains = sorted({node["domain"] for node in NODES.values()}, key=fold)
    sections = (
        ("Rechercher", "search"),
        ("Atlas des concepts", "atlas"),
        ("Atelier philosophique", "work"),
    )
    with gr.Row(elem_id="reader-quicknav"):
        mobile_navigation = [
            (gr.Button(label, size="sm"), section) for label, section in sections
        ]
    with gr.Tabs(selected="search", elem_id="reader-tabs") as tabs:
        with gr.Tab("Rechercher", id="search"):
            with gr.Column(elem_id="chat-shell"):
                q = gr.Textbox(
                    label="Quel passage ou quelle idée cherchez-vous ?",
                    placeholder="Une citation, une formule ou un souvenir de lecture…",
                    lines=2,
                    max_lines=4,
                    elem_id="question-box",
                )
                go = gr.Button("Rechercher les passages", variant="primary")
                hits = gr.HTML()
                with gr.Row():
                    expand = gr.Button("Déplier l’argument")
                    locate = gr.Button("Situer cette idée dans le système")
                inline = gr.HTML()
                discuss = gr.Button("Contester une prémisse dans l’Atelier")
                legacy(q)
        with gr.Tab("Atlas des concepts", id="atlas"):
            domain = gr.Dropdown(
                ["Tous les domaines", *domains],
                value="Tous les domaines",
                label="Domaine",
            )
            with gr.Row():
                concept = gr.Dropdown(options, value="systemisme", label="Notion")
                linked = gr.Dropdown(label="Suivre un lien", choices=[])
                follow = gr.Button("Ouvrir la notion liée")
            atlas = gr.HTML()
            with gr.Accordion("Comparer dans plusieurs ouvrages", open=False):
                comparison = gr.HTML()
                paired = gr.Dropdown(
                    options, label="Mettre une autre formulation en regard", value=None
                )
                compare_button = gr.Button("Lire les deux formulations")
                pair_result = gr.HTML()
            to_work = gr.Button("Examiner cette idée dans l’Atelier")
            with gr.Accordion("Couverture de la bibliothèque", open=False):
                book = gr.Dropdown(book_options, label="Ouvrage", value=first_book)
                overview = gr.HTML(coverage_html)
                first_chapters = chapter_openings(first_book)
                chapter = gr.Dropdown(first_chapters, label="Chapitre", value=None)
                opening = gr.HTML()
                first_marks = formal_markers(first_book)
                marker = gr.Dropdown(
                    first_marks,
                    label="Repère dans l’ouvrage",
                    value=first_marks[0][1] if first_marks else None,
                )
                open_marker = gr.Button("Examiner ce repère")
            back = gr.Button("Revenir à ma recherche")
        with gr.Tab("Atelier philosophique", id="work"):
            work_q = gr.Textbox(
                label="Quelle thèse voulez-vous examiner ?",
                placeholder="Un modèle de langage peut-il comprendre ?",
            )
            work_go = gr.Button("Ouvrir le dossier", variant="primary")
            shortcuts = gr.Radio(
                [
                    ("Bonheur complet", "bonheur"),
                    ("Besoin et obligation", "devoir"),
                    ("Compréhension et IA", "ia"),
                    ("Unicité du monde", "monde"),
                    ("Existence des construits", "existence"),
                ],
                label="Dossiers de lecture",
            )
            work_text = gr.HTML()
            with gr.Row():
                premise = gr.Dropdown(label="Prémisse à contester", choices=[])
                action = gr.Radio(
                    ["Suspendre", "Remplacer", "Rétablir"],
                    value="Suspendre",
                    label="Modification",
                )
            replacement = gr.Textbox(
                label="Prémisse de remplacement",
                placeholder="Votre hypothèse de travail",
            )
            with gr.Row():
                apply = gr.Button("Voir les conséquences")
                reset = gr.Button("Revenir à l’argument initial")

    for button, section in mobile_navigation:
        button.click(
            lambda selected=section: gr.Tabs(selected=selected),
            outputs=tabs,
            api_name=False,
            queue=False,
        )

    def atlas_change(key):
        return atlas_view(key, local)

    def filter_domain(value):
        matching = [
            (title, key)
            for title, key in options
            if value == "Tous les domaines" or NODES[key]["domain"] == value
        ]
        return gr.Dropdown(choices=matching, value=matching[0][1])

    domain.input(filter_domain, domain, concept, api_name=False)
    concept.change(atlas_change, concept, [atlas, linked, comparison], api_name=False)

    def select_concept(key):
        if not key:
            return gr.skip()
        extras = []
        if key not in NODES:
            record = read_marker(key)
            if not record:
                return gr.skip()
            extras = [(record[0], key)]
        return gr.Dropdown(choices=options + extras, value=key)

    follow.click(select_concept, linked, concept, api_name=False)
    open_marker.click(select_concept, marker, concept, api_name=False)

    def paired_cards(left, right):
        if not left or not right:
            return "<p>Choisissez deux formulations.</p>"
        sources = [
            node_source(k) if k in NODES else read_marker(k)[1] for k in (left, right)
        ]
        return (
            '<div class="compare-grid">'
            + "".join(
                card(src, local) for src in sorted(sources, key=lambda x: x["year"])
            )
            + "</div>"
        )

    compare_button.click(paired_cards, [concept, paired], pair_result, api_name=False)

    def show_book(b):
        text, _, _ = coverage(b)
        marks = formal_markers(b)
        chapters = chapter_openings(b)
        return (
            text,
            gr.Dropdown(choices=chapters, value=None, interactive=bool(chapters)),
            gr.Dropdown(choices=marks, value=marks[0][1] if marks else None),
            "",
        )

    def show_chapter(b, name):
        source = chapter_source(b, name) if name else None
        marks = formal_markers(b, chapter=name)
        return (
            card(source, local) if source else "",
            gr.Dropdown(choices=marks, value=marks[0][1] if marks else None),
        )

    book.change(show_book, book, [overview, chapter, marker, opening], api_name=False)
    chapter.input(show_chapter, [book, chapter], [opening, marker], api_name=False)
    back.click(lambda: gr.Tabs(selected="search"), outputs=tabs, api_name=False)

    def get_dossier(question, node, results, request):
        known = choose_dossier(question, node)
        if known:
            return DOSSIERS[known]()
        return create_dossier(question, request, results)

    def ready(d):
        return (
            d,
            {},
            dossier_view(d, {}, local),
            gr.Dropdown(
                choices=[(s["title"], s["id"]) for s in d["steps"]],
                value=(d["steps"][0]["id"] if d["steps"] else None),
            ),
        )

    def lookup(question, request: gr.Request):
        question = " ".join((question or "").split())
        if not 3 <= len(question) <= max_chars:
            yield (
                [],
                question,
                "<p>Saisissez une recherche entre 3 et "
                + str(max_chars)
                + " caractères.</p>",
                "",
                {},
            )
            return
        disposition, message = question_scope(question)
        if disposition != "localiser":
            yield [], question, "<p>" + esc(message) + "</p>", "", {}
            return
        wants_proof = re.search(
            r"d[eé]montr|justifi|pourquoi|comment .*d[eé]du|preuve|argument",
            question,
            re.I,
        )
        known = choose_dossier(question) if wants_proof else None
        if known:
            dossier = DOSSIERS[known]()
            pages = {}
            for entry in dossier["steps"]:
                for source in entry["sources"]:
                    pages.setdefault((source["book"], source["page"]), source)
            related = list(pages.values())
            yield (
                related,
                question,
                "".join(card(source, local) for source in related),
                dossier_view(dossier, {}, local),
                dossier,
            )
            return
        result = search_library(question)
        rendered = (
            "".join(card(s, local) for s in result) or "<p>Passage non retrouvé.</p>"
        )
        yield result, question, rendered, "", {}
        if wants_proof:
            d = get_dossier(question, None, result, request)
            yield result, question, rendered, dossier_view(d, {}, local), d

    for event in (go.click, q.submit):
        event(
            lookup,
            inputs=q,
            outputs=[research, saved_question, hits, inline, inline_dossier],
            api_name=False,
            concurrency_id="reader",
            concurrency_limit=1,
        )

    def resolve(q, saved, rs):
        if " ".join(q.split()) == saved:
            return rs
        return search_library(q) if 3 <= len(q.strip()) <= max_chars else []

    def expand_argument(q, saved, rs, previous, request: gr.Request):
        if not 3 <= len(q.strip()) <= max_chars:
            return {}, "<p>Saisissez une question à examiner.</p>"
        d = (
            previous
            if previous and q.strip() == saved
            else get_dossier(q, None, resolve(q, saved, rs), request)
        )
        return d, dossier_view(d, {}, local)

    expand.click(
        expand_argument,
        [q, saved_question, research, inline_dossier],
        [inline_dossier, inline],
        api_name=False,
    )

    def focus(q, saved, rs):
        nodeids = suggested_nodes(q) or [
            k for p in resolve(q, saved, rs) for k in on_page(p["book"], p["page"])
        ]
        if not nodeids:
            for hit in resolve(q, saved, rs):
                marks = formal_markers(hit["book"], hit["page"])
                if marks:
                    nodeids = [marks[0][1]]
                    break
        if not nodeids:
            return (
                gr.Tabs(selected="atlas"),
                gr.Dropdown(value=None),
                "<p>Aucune fiche éditée ne correspond à cette recherche. Choisissez une notion dans l’atlas.</p>",
                gr.Dropdown(choices=[], value=None),
                "<p>Aucune comparaison sélectionnée.</p>",
            )
        key = nodeids[0]
        return gr.Tabs(selected="atlas"), select_concept(key), *atlas_change(key)

    locate.click(
        focus,
        [q, saved_question, research],
        [tabs, concept, atlas, linked, comparison],
        api_name=False,
    )

    def from_search(q, saved, rs, previous, request: gr.Request):
        d = (
            previous
            if previous and q.strip() == saved
            else get_dossier(q, None, resolve(q, saved, rs), request)
        )
        return gr.Tabs(selected="work"), q, *ready(d)

    discuss.click(
        from_search,
        [q, saved_question, research, inline_dossier],
        [tabs, work_q, dossier, changes, work_text, premise],
        api_name=False,
    )

    def from_atlas(key, request: gr.Request):
        if key in NODES:
            title, source = NODES[key]["title"], node_source(key)
        else:
            record = read_marker(key)
            if not record:
                return (
                    gr.Tabs(selected="work"),
                    "",
                    *ready(open_question("Choisissez une question.", [])),
                )
            title, source, _ = record
        d = get_dossier(title, key, [source], request)
        return gr.Tabs(selected="work"), title, *ready(d)

    to_work.click(
        from_atlas,
        concept,
        [tabs, work_q, dossier, changes, work_text, premise],
        api_name=False,
    )

    def example(key):
        d = DOSSIERS[key]()
        return d["title"], *ready(d)

    shortcuts.input(
        example,
        shortcuts,
        [work_q, dossier, changes, work_text, premise],
        api_name=False,
    )

    def custom(question, request: gr.Request):
        question = " ".join((question or "").split())
        if not 3 <= len(question) <= max_chars:
            return (
                {},
                {},
                "<p>Précisez la thèse à examiner.</p>",
                gr.Dropdown(choices=[], value=None),
            )
        key = choose_dossier(question)
        d = DOSSIERS[key]() if key else create_dossier(question, request)
        return ready(d)

    for event in (work_go.click, work_q.submit):
        event(
            custom,
            work_q,
            [dossier, changes, work_text, premise],
            api_name=False,
            concurrency_id="reader",
            concurrency_limit=1,
        )

    def change(d, old, key, operation, new):
        updated = dict(old)
        if key not in {s["id"] for s in d.get("steps", [])}:
            return old, dossier_view(d, old, local)
        if operation == "Remplacer" and not new.strip():
            return old, dossier_view(
                d, old, local
            ) + "<p>Indiquez votre hypothèse de remplacement.</p>"
        if operation == "Rétablir":
            updated.pop(key, None)
        else:
            updated[key] = new.strip()[:max_chars] if operation == "Remplacer" else ""
        return updated, dossier_view(d, updated, local)

    apply.click(
        change,
        [dossier, changes, premise, action, replacement],
        [changes, work_text],
        api_name=False,
    )
    reset.click(
        lambda d: ({}, dossier_view(d, {}, local)),
        dossier,
        [changes, work_text],
        api_name=False,
    )
    return concept, atlas, linked, comparison, atlas_change
