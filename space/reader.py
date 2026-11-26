"""Vues de lecture, de navigation dans le système et de discussion des prémisses."""

import html
import re
from contextlib import closing
from functools import lru_cache
from urllib.parse import quote

import gradio as gr

from atlas_graph import (
    MINDMAP_CSS,
    MINDMAP_JS,
    render_mindmap,
    render_symbol_lexicon,
)
from contemporary import fetch_contemporary_fact
from formal_logic import FOL_VERIFIERS
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
    contemporary_claim,
    debate_turn,
    formal_efficiency,
    formal_happiness,
    formal_rights,
    formal_systemism,
    formal_world,
    open_question,
)

esc = html.escape


def card(source, local):
    link = ""
    attribution = (
        f'<small class="citation-voice">Auteur cité · {esc(source["voice"])}</small>'
        if source.get("voice")
        else ""
    )
    imprint = (
        f'<p class="folio">Édition indexée · {esc(source["edition_label"])}</p>'
        if source.get("edition_label")
        else ""
    )
    if local and source["file"].endswith(".pdf") and str(source["page"]).isdecimal():
        pdf = (local / source["file"]).resolve()
        if pdf.parent == local.resolve() and pdf.is_file():
            link = f'<a href="/gradio_api/file={quote(str(pdf))}#page={int(source["page"])}" target="_blank" rel="noopener">Ouvrir cette page ↗</a>'
    return (
        f'<article class="reading-card"><header><strong>{esc(source["title"])}</strong> '
        f"<small>{esc(str(source['year']))} · {esc(source['authors'])}</small></header>"
        f'{imprint}<p class="folio">{esc(source["pages"])}</p>{attribution}<blockquote lang="en">{esc(source["excerpt"])}</blockquote>{link}</article>'
    )


@lru_cache(maxsize=1)
def dossiers_by_chapter():
    chapters = {}
    for build in DOSSIERS.values():
        dossier = build()
        for step in dossier["steps"]:
            for source in step["sources"]:
                key = (source["book"], source["chapter"])
                chapters.setdefault(key, set()).add(dossier["title"])
    return chapters


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
        detected = dict(
            db.execute(
                """SELECT p.chapter,count(*) FROM labels l JOIN pages p ON p.id=l.page_id
                   WHERE p.book=? GROUP BY p.chapter""",
                (book,),
            )
        )
    sourced = [n for n in NODES.values() if n["source"]["book"] == book]
    dossiers = dossiers_by_chapter()
    rows = []
    for i, row in enumerate(chapters):
        last = chapters[i + 1]["page"] if i + 1 < len(chapters) else float("inf")
        refs = sum(row["page"] <= int(n["source"]["page"]) < last for n in sourced)
        marked = detected.get(row["title"], 0)
        titles = dossiers.get((book, row["title"]), ())
        workshop = " · ".join(esc(title) for title in sorted(titles))
        rows.append(
            f"<li><strong>{esc(row['title'])}</strong> · PDF p. {row['page']} · "
            f"{refs} fiches · {marked} repères formels détectés"
            + (
                f"<br><small>Dossiers de l’Atelier · {workshop}</small>"
                if workshop
                else "<br><small>Dossier argumenté à établir</small>"
            )
            + "</li>"
        )
    text = (
        f"<p>{totals['ouvrages']} ouvrages indexés · {totals['chapitres']} chapitres du Traité repérés. "
        f"Pour cet ouvrage, {pages} pages ou sections, {len(sourced)} fiches documentées "
        f"et {sum(detected.values())} repères formels détectés.</p>"
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
        if annotation := e.get("comparison"):
            compare += f"<p><strong>Lecture éditoriale</strong> {esc(annotation)}</p>"
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
    title_by_id = {s["id"]: s["title"] for s in dossier["steps"]}
    for s in dossier["steps"]:
        state = states[s["id"]]
        sources = "".join(card(r, local) for r in s["sources"])
        for f in s.get("external", []):
            sources += f'<p><a href="{esc(f["url"], quote=True)}" target="_blank" rel="noopener">{esc(f["title"])}</a></p>'
        supports = []
        for group in s["supports"]:
            names = " et ".join(title_by_id[p] for p in group)
            unavailable = [title_by_id[p] for p in group if states[p] != "disponible"]
            status = (
                ", ".join(unavailable) + " à rétablir"
                if unavailable
                else "Justification disponible"
            )
            supports.append(f"<li>{esc(names)}<br><small>{esc(status)}</small></li>")
        replacement = changes.get(s["id"], "")
        pill_cls = (
            "step-pill-ok"
            if state == "disponible"
            else ("step-pill-alt" if "remplac" in state else "step-pill-warn")
        )
        sections.append(
            f'<article class="argument-step">'
            f'<div class="step-meta"><span class="step-role">{esc(s["role"])}</span>'
            f'<span class="step-pill {pill_cls}">{esc(state)}</span></div>'
            f"<h4>{esc(s['title'])}</h4>"
            f"<p>{esc(s['text'])}</p>"
            + (
                f"<p><strong>Votre hypothèse :</strong> {esc(replacement)}</p>"
                if replacement
                else ""
            )
            + ("<p><small>Dépend de :</small></p><ul>" + "".join(supports) + "</ul>" if supports else "")
            + (
                f"<details><summary>Voir la source dans Bunge</summary>{sources}</details>"
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
        "unique": formal_world,
        "non-reductibilite": formal_systemism,
        "distinction-efficacite": formal_efficiency,
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
            f'<details class="formal-check"><summary>Vérifier le fragment formel (propositionnel)</summary>'
            f'<small>Formalisation éditoriale · Preuve vérifiée par table de vérité</small>'
            f'<p class="formula">{esc(fragment["formula"])}</p><p>{esc(fragment["gloss"])}</p>'
            f'<div class="formal-table"><table><thead><tr>{headers}</tr></thead><tbody>'
            + rows
            + "</tbody></table></div></details>"
        )
    for identifier in FOL_VERIFIERS.keys() & {s["id"] for s in dossier["steps"]}:
        proof = FOL_VERIFIERS[identifier]()
        counter = proof.get("countermodel")
        counter_html = (
            f"<p><strong>Contre-modèle sans « {esc(proof['dropped_axiom'])} » :</strong> "
            f"<code>{esc(str(counter))}</code></p>"
            if counter
            else ""
        )
        sections.append(
            f'<details class="formal-check"><summary>Vérifier la preuve du premier ordre</summary>'
            f'<small>{esc(proof["kind"])} · {esc(proof["source_label"])}</small>'
            f'<p class="formula">{esc(proof["formula"])}</p>'
            f'<p>{esc(proof["gloss"])}</p>'
            f"<p><small>{proof['models_checked']} structures/assignations contrôlées · "
            f"{proof['counterexamples']} contre-exemple(s) sous les axiomes complets.</small></p>"
            f"{counter_html}</details>"
        )
    sections.append(
        "<details><summary>Cadre philosophique de cette lecture</summary>"
        + "".join(card(node_source(key), local) for key in CATALOG["core"])
        + "</details>"
    )
    if dossier.get("notice"):
        sections.append('<p role="status">' + esc(dossier["notice"]) + "</p>")
    return "".join(sections)


def render_debate(history, local, notice=""):
    if not history and not notice:
        return ""
    blocks = []
    for item in history or []:
        mods = item.get("active_changes") or {}
        mod_note = (
            f"<small>Hypothèses actives du lecteur ({len(mods)} prémisse(s) modifiée(s))</small>"
            if mods
            else "<small>Argument initial actif</small>"
        )
        src_html = "".join(card(s, local) for s in item.get("sources") or [])
        impact = f"<p><strong>Effet sur les prémisses :</strong> {esc(item['impact'])}</p>" if item.get("impact") else ""
        follow_q = f"<p><small>Piste de poursuite : {esc(item['next_question'])}</small></p>" if item.get("next_question") else ""
        blocks.append(
            f'<article class="argument-step"><small>Tour {int(item["turn"])} · {esc(item.get("mode", "débat"))}</small>'
            f"<h4>Objection : {esc(item['user'])}</h4>{mod_note}"
            f"<p>{esc(item['answer'])}</p>{impact}{follow_q}"
            + (
                f"<details><summary>Appuis sourcés de ce tour ({len(item['sources'])})</summary>{src_html}</details>"
                if src_html
                else ""
            )
            + "</article>"
        )
    if notice:
        blocks.append(f'<p role="status">{esc(notice)}</p>')
    return "".join(blocks)


def build_reader(legacy, local, create_dossier, max_chars, run_debate=None):
    options = sorted(
        ((n["title"], k) for k, n in NODES.items()), key=lambda x: fold(x[0])
    )
    coverage_html, book_options, first_book = coverage()
    initial_atlas_html, _, initial_compare_html = atlas_view("systemisme", local)
    initial_dossier = DOSSIERS["ia"]()
    initial_steps = [(s["title"], s["id"]) for s in initial_dossier["steps"]]
    research = gr.State([])
    saved_question = gr.State("")
    inline_dossier = gr.State({})
    dossier = gr.State(initial_dossier)
    changes = gr.State({})
    debate_history = gr.State([])
    sections = (
        ("Rechercher", "search"),
        ("Atlas des concepts", "atlas"),
        ("Atelier philosophique", "work"),
    )
    suggestions = (
        ("Qu’est-ce que l’émergence ?", "Qu'est-ce que l'émergence pour Bunge ?"),
        ("Causalité vs déterminisme", "Quelle différence entre causalité et déterminisme ?"),
        ("Un LLM peut-il comprendre ?", "Un modèle de langage peut-il comprendre ?"),
        ("Bonheur complet ?", "Peut-on être complètement heureux selon Bunge ?"),
    )
    dossier_choices = [
        ("IA · Un modèle de langage peut-il comprendre ? (T4)", "ia"),
        ("Éthique · Peut-on être complètement heureux ? (T8)", "bonheur"),
        ("Ontologie · Systémisme et émergence (T4)", "systemisme"),
        ("Ontologie · Pourquoi le monde est-il unique ? (T3)", "monde"),
        ("Épistémologie · Explication et mécanisme (T6)", "mecanisme"),
        ("Causalité · Causalité et fatalisme", "fatalisme"),
        ("Éthique · Besoin et obligation morale (T8)", "devoir"),
        ("Sémantique · Existence des idées et construits (T1)", "existence"),
        ("IA · Grande fenêtre de contexte et compréhension (T6)", "contexte"),
        ("Technologie · Efficacité, vérité et morale (T6–T8)", "efficacite"),
        ("Sémantique · Sens, référence et synonymie (T1–T2)", "signification"),
        ("Épistémologie · Conjecture, inférence et théorie (T5)", "conjecture"),
        ("Sciences · Modèle factuel et physique (T7/I)", "modele_factuel"),
        ("Sémantique · Interprétation et vérité partielle (T1–T2)", "semantique_verite"),
        ("Ontologie · Propriétés, choses et espace-temps (T3)", "ontologie_choses"),
        ("Ontologie · Niveaux chimique, biologique et social (T4)", "niveaux_systemes"),
        ("Épistémologie · Cognition, perception et enquête (T5)", "cognition_enquete"),
        ("Épistémologie · Évaluation et évolution du savoir (T6)", "evolution_savoir"),
        ("Sciences · Psychologie et sciences sociales (T7/II)", "sciences_vie_societe"),
        ("Éthique · Valeurs, cas moraux et mœurs (T8)", "ethique_normes"),
        ("Éthique · Métaéthique, société et survie (T8)", "metaethique_survie"),
    ]
    with gr.Row(elem_id="reader-quicknav"):
        mobile_navigation = [
            (gr.Button(label, size="sm"), section) for label, section in sections
        ]
    with gr.Tabs(selected="search", elem_id="reader-tabs") as tabs:
        with gr.Tab("Rechercher", id="search"):
            with gr.Column(elem_id="chat-shell"):
                q = gr.Textbox(
                    label="Que cherchez-vous dans l’œuvre de Bunge ?",
                    placeholder="Posez une question, collez une citation ou un symbole (ex. émergence, causalité, ℳ)…",
                    lines=2,
                    max_lines=4,
                    elem_id="question-box",
                )
                with gr.Row(elem_classes=["suggestion-row"]):
                    suggestion_buttons = [
                        (gr.Button(short, size="sm"), full)
                        for short, full in suggestions
                    ]
                with gr.Row(elem_classes=["action-bar"]):
                    go = gr.Button("Rechercher les passages", variant="primary", scale=2)
                    ai_go = gr.Button("Synthèse IA sourcée", variant="secondary", scale=1)
                legacy(q, ai_go)
                hits = gr.HTML()
                with gr.Row(visible=False, elem_classes=["action-bar"]) as next_steps:
                    expand = gr.Button("Déplier l’argument")
                    locate = gr.Button("Voir sur la carte")
                    discuss = gr.Button("Tester dans l’Atelier")
                inline = gr.HTML()

        with gr.Tab("Atlas des concepts", id="atlas"):
            with gr.Column(elem_classes=["glass-panel"]):
                with gr.Row(elem_classes=["inline-submit-row"]):
                    concept = gr.Dropdown(
                        options,
                        value="systemisme",
                        label="Aller à une notion (113 fiches)",
                        scale=3,
                    )
                    to_work = gr.Button("Tester cette idée dans l’Atelier →", scale=1)
                mindmap = gr.HTML(
                    render_mindmap("systemisme"),
                    css_template=MINDMAP_CSS,
                    js_on_load=MINDMAP_JS,
                )
            with gr.Accordion("Fiche détaillée et liens de cette notion", open=False):
                atlas = gr.HTML(initial_atlas_html)
            with gr.Accordion("Symboles et formules mathématiques (16)", open=False):
                symbol_filter = gr.Textbox(
                    label="Filtrer par symbole ou mot-clé",
                    placeholder="Ex. ℳ, ⊑, σ, psychon, vérité, bien-être…",
                )
                symbol_lexicon = gr.HTML(render_symbol_lexicon())
            with gr.Accordion("Comparer deux ouvrages · Parcourir les 25 livres", open=False):
                comparison = gr.HTML(initial_compare_html)
                with gr.Row(elem_classes=["inline-submit-row"]):
                    paired = gr.Dropdown(
                        options,
                        label="Comparer avec une autre notion",
                        value=None,
                        scale=3,
                    )
                    compare_button = gr.Button("Comparer", scale=1)
                pair_result = gr.HTML()
                book = gr.Dropdown(book_options, label="Parcourir un ouvrage", value=first_book)
                overview = gr.HTML(coverage_html)
                first_chapters = chapter_openings(first_book)
                chapter = gr.Dropdown(first_chapters, label="Chapitre", value=None)
                opening = gr.HTML()
                first_marks = formal_markers(first_book)
                with gr.Row(elem_classes=["inline-submit-row"]):
                    marker = gr.Dropdown(
                        first_marks,
                        label="Repère formel dans l’ouvrage",
                        value=first_marks[0][1] if first_marks else None,
                        scale=3,
                    )
                    open_marker = gr.Button("Ouvrir ce repère", scale=1)

        with gr.Tab("Atelier philosophique", id="work"):
            with gr.Column(elem_classes=["glass-panel"]):
                shortcuts = gr.Dropdown(
                    dossier_choices,
                    value="ia",
                    label="Choisir un sujet (21 dossiers sur tout le Traité)",
                )
                with gr.Accordion("Poser votre propre thèse ou ajouter un article récent", open=False):
                    with gr.Row(elem_classes=["inline-submit-row"]):
                        work_q = gr.Textbox(
                            label="Votre thèse ou question",
                            placeholder="Ex. Un algorithme prédictif explique-t-il un phénomène ?",
                            scale=3,
                        )
                        work_go = gr.Button("Analyser", variant="primary", scale=1)
                    with gr.Row(elem_classes=["inline-submit-row"]):
                        fact_lookup = gr.Textbox(
                            label="Optionnel · Lier un article HTTPS ou un sujet Wikipédia",
                            placeholder="https://… ou ex. AlphaFold, Llama 3.1",
                            scale=3,
                        )
                        fact_fetch = gr.Button("Pré-remplir", scale=1)
                    fact_status = gr.HTML()
                    supplied_fact = gr.Textbox(label="Fait récent à examiner", lines=2)
                    with gr.Row():
                        supplied_link = gr.Textbox(label="Lien HTTPS de la source")
                        supplied_date = gr.Textbox(
                            label="Date", placeholder="AAAA-MM-JJ"
                        )
            work_text = gr.HTML(dossier_view(initial_dossier, {}, local))
            with gr.Column(elem_classes=["glass-panel"]):
                gr.HTML(
                    '<div class="section-heading"><h3>Tester une hypothèse</h3>'
                    "<p>Écartez ou remplacez une étape de l’argument pour voir immédiatement si la conclusion tient encore.</p></div>"
                )
                with gr.Row():
                    premise = gr.Dropdown(
                        label="Étape à remettre en cause",
                        choices=initial_steps,
                        value=initial_steps[0][1] if initial_steps else None,
                    )
                    action = gr.Radio(
                        [("Écarter", "Suspendre"), ("Remplacer", "Remplacer")],
                        value="Suspendre",
                        label="Action",
                    )
                replacement = gr.Textbox(
                    label="Votre hypothèse de remplacement (si « Remplacer »)",
                    placeholder="Écrivez votre propre prémisse…",
                )
                with gr.Row(elem_classes=["action-bar"]):
                    apply = gr.Button("Voir l’effet sur la conclusion", variant="primary")
                    reset = gr.Button("Réinitialiser l’argument")
            with gr.Column(elem_classes=["glass-panel"]):
                gr.HTML(
                    '<div class="section-heading"><h3>Débattre avec les textes</h3>'
                    "<p>Posez une objection ou une question de suivi : vos hypothèses ci-dessus restent actives et chaque réponse cite Bunge.</p></div>"
                )
                debate_view = gr.HTML(render_debate([], local))
                debate_input = gr.Textbox(
                    label="Votre objection",
                    placeholder="Ex. Si l’on écarte cette prémisse, quel autre passage de Bunge répond ?",
                    lines=2,
                )
                with gr.Row(elem_classes=["action-bar"]):
                    debate_send = gr.Button("Envoyer", variant="primary")
                    debate_clear = gr.Button("Effacer le débat")

    for button, section in mobile_navigation:
        button.click(
            lambda selected=section: gr.Tabs(selected=selected),
            outputs=tabs,
            api_name=False,
            queue=False,
            show_progress="hidden",
        )

    def atlas_change(key):
        view_html, _, compare_html = atlas_view(key, local)
        graph_key = key if key in NODES else "systemisme"
        return view_html, compare_html, render_mindmap(graph_key)

    concept.change(
        atlas_change,
        concept,
        [atlas, comparison, mindmap],
        api_name=False,
        show_progress="hidden",
    )
    symbol_filter.input(
        render_symbol_lexicon,
        symbol_filter,
        symbol_lexicon,
        api_name=False,
        show_progress="hidden",
    )

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

    open_marker.click(
        select_concept, marker, concept, api_name=False, show_progress="hidden"
    )

    def paired_cards(left, right):
        if not left or not right:
            return "<p>Choisissez une seconde notion à comparer.</p>"
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

    compare_button.click(
        paired_cards,
        [concept, paired],
        pair_result,
        api_name=False,
        show_progress="hidden",
    )

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

    book.change(
        show_book,
        book,
        [overview, chapter, marker, opening],
        api_name=False,
        show_progress="hidden",
    )
    chapter.input(
        show_chapter,
        [book, chapter],
        [opening, marker],
        api_name=False,
        show_progress="hidden",
    )

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
                gr.Row(visible=False),
                "",
                {},
            )
            return
        disposition, message = question_scope(question)
        if disposition != "localiser":
            yield (
                [],
                question,
                "<p>" + esc(message) + "</p>",
                gr.Row(visible=False),
                "",
                {},
            )
            return
        yield (
            [],
            question,
            '<div class="bunge-loading-bar" aria-label="Recherche en cours"></div>',
            gr.Row(visible=False),
            "",
            {},
        )
        wants_proof = re.search(
            r"d[eé]montr|justifi|pourquoi|comment .*d[eé]du|preuve|argument",
            question,
            re.I,
        )
        known = choose_dossier(question) if wants_proof else None
        if known:
            dossier_obj = DOSSIERS[known]()
            pages = {}
            for entry in dossier_obj["steps"]:
                for source in entry["sources"]:
                    pages.setdefault((source["book"], source["page"]), source)
            related = list(pages.values())
            yield (
                related,
                question,
                "".join(card(source, local) for source in related),
                gr.Row(visible=bool(related)),
                dossier_view(dossier_obj, {}, local),
                dossier_obj,
            )
            return
        result = search_library(question)
        rendered = (
            "".join(card(s, local) for s in result) or "<p>Passage non retrouvé.</p>"
        )
        yield result, question, rendered, gr.Row(visible=bool(result)), "", {}
        if wants_proof:
            d = get_dossier(question, None, result, request)
            yield (
                result,
                question,
                rendered,
                gr.Row(visible=True),
                dossier_view(d, {}, local),
                d,
            )

    for event in (go.click, q.submit):
        event(
            lookup,
            inputs=q,
            outputs=[research, saved_question, hits, next_steps, inline, inline_dossier],
            api_name=False,
            show_progress="hidden",
            concurrency_id="reader",
            concurrency_limit=1,
        )

    for btn, preset in suggestion_buttons:
        def _run_preset(request: gr.Request, text=preset):
            for step_out in lookup(text, request):
                yield (text, *step_out)

        btn.click(
            _run_preset,
            outputs=[q, research, saved_question, hits, next_steps, inline, inline_dossier],
            api_name=False,
            show_progress="hidden",
            concurrency_id="reader",
            concurrency_limit=1,
        )

    def resolve(q_text, saved, rs):
        if " ".join(q_text.split()) == saved:
            return rs
        return search_library(q_text) if 3 <= len(q_text.strip()) <= max_chars else []

    def expand_argument(q_text, saved, rs, previous, request: gr.Request):
        if not 3 <= len(q_text.strip()) <= max_chars:
            yield {}, "<p>Saisissez une question à examiner.</p>"
            return
        if previous and q_text.strip() == saved:
            yield previous, dossier_view(previous, {}, local)
            return
        yield {}, '<div class="bunge-loading-bar" aria-label="Analyse en cours"></div>'
        d = get_dossier(q_text, None, resolve(q_text, saved, rs), request)
        yield d, dossier_view(d, {}, local)

    expand.click(
        expand_argument,
        [q, saved_question, research, inline_dossier],
        [inline_dossier, inline],
        api_name=False,
        show_progress="hidden",
    )

    def focus(q_text, saved, rs):
        nodeids = suggested_nodes(q_text) or [
            k for p in resolve(q_text, saved, rs) for k in on_page(p["book"], p["page"])
        ]
        if not nodeids:
            for hit in resolve(q_text, saved, rs):
                marks = formal_markers(hit["book"], hit["page"])
                if marks:
                    nodeids = [marks[0][1]]
                    break
        if not nodeids:
            return (
                gr.Tabs(selected="atlas"),
                gr.Dropdown(value="systemisme"),
                initial_atlas_html,
                initial_compare_html,
                render_mindmap("systemisme"),
            )
        key = nodeids[0]
        return gr.Tabs(selected="atlas"), select_concept(key), *atlas_change(key)

    locate.click(
        focus,
        [q, saved_question, research],
        [tabs, concept, atlas, comparison, mindmap],
        api_name=False,
        show_progress="hidden",
    )

    def from_search(q_text, saved, rs, previous, request: gr.Request):
        d = (
            previous
            if previous and q_text.strip() == saved
            else get_dossier(q_text, None, resolve(q_text, saved, rs), request)
        )
        return gr.Tabs(selected="work"), q_text, *ready(d), [], render_debate([], local)

    discuss.click(
        from_search,
        [q, saved_question, research, inline_dossier],
        [tabs, work_q, dossier, changes, work_text, premise, debate_history, debate_view],
        api_name=False,
        show_progress="hidden",
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
                    [],
                    render_debate([], local),
                )
            title, source, _ = record
        d = get_dossier(title, key, [source], request)
        return gr.Tabs(selected="work"), title, *ready(d), [], render_debate([], local)

    to_work.click(
        from_atlas,
        concept,
        [tabs, work_q, dossier, changes, work_text, premise, debate_history, debate_view],
        api_name=False,
        show_progress="hidden",
    )

    def prefill_fact(query_or_url):
        try:
            item = fetch_contemporary_fact(query_or_url)
        except Exception as exc:
            return (
                gr.skip(),
                gr.skip(),
                gr.skip(),
                f'<p role="alert">{esc(str(exc))}</p>',
            )
        return (
            item["text"],
            item["url"],
            item["published"],
            f'<p role="status">Source pré-remplie ({esc(item["title"])}) — relisez avant d’analyser.</p>',
        )

    fact_fetch.click(
        prefill_fact,
        fact_lookup,
        [supplied_fact, supplied_link, supplied_date, fact_status],
        api_name=False,
        show_progress="hidden",
    )

    def example(key):
        if not key or key not in DOSSIERS:
            return gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
        d = DOSSIERS[key]()
        return *ready(d), [], render_debate([], local)

    shortcuts.change(
        example,
        shortcuts,
        [dossier, changes, work_text, premise, debate_history, debate_view],
        api_name=False,
        show_progress="hidden",
    )

    def custom(question, fact, link, published, request: gr.Request):
        question = " ".join((question or "").split())
        if not 3 <= len(question) <= max_chars:
            yield (
                {},
                {},
                "<p>Précisez la thèse à examiner.</p>",
                gr.Dropdown(choices=[], value=None),
                [],
                render_debate([], local),
            )
            return
        try:
            external = contemporary_claim(fact, link, published)
        except ValueError as exc:
            yield (
                {},
                {},
                f'<p role="alert">{esc(str(exc))}</p>',
                gr.Dropdown(choices=[], value=None),
                [],
                render_debate([], local),
            )
            return
        yield (
            gr.skip(),
            {},
            '<div class="bunge-loading-bar" aria-label="Analyse en cours"></div>',
            gr.skip(),
            [],
            render_debate([], local),
        )
        key = choose_dossier(question) if not external else None
        d = (
            DOSSIERS[key]()
            if key
            else create_dossier(question, request, external=external)
        )
        yield *ready(d), [], render_debate([], local)

    for event in (work_go.click, work_q.submit):
        event(
            custom,
            [work_q, supplied_fact, supplied_link, supplied_date],
            [dossier, changes, work_text, premise, debate_history, debate_view],
            api_name=False,
            show_progress="hidden",
            concurrency_id="reader",
            concurrency_limit=1,
        )

    def send_debate(d, ch, hist, text, request: gr.Request):
        yield (
            hist,
            render_debate(hist, local)
            + '<div class="bunge-loading-bar" aria-label="Recherche dans Bunge"></div>',
            text,
        )
        if run_debate is not None:
            new_hist, notice = run_debate(d, ch, hist, text, request)
        else:
            new_hist, notice = debate_turn(d, ch, hist, text)
        yield new_hist, render_debate(new_hist, local, notice), "" if not notice else text

    for event in (debate_send.click, debate_input.submit):
        event(
            send_debate,
            [dossier, changes, debate_history, debate_input],
            [debate_history, debate_view, debate_input],
            api_name=False,
            show_progress="hidden",
            concurrency_id="reader",
            concurrency_limit=1,
        )
    debate_clear.click(
        lambda: ([], render_debate([], local), ""),
        outputs=[debate_history, debate_view, debate_input],
        api_name=False,
        show_progress="hidden",
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
        show_progress="hidden",
    )
    reset.click(
        lambda d: ({}, dossier_view(d, {}, local)),
        dossier,
        [changes, work_text],
        api_name=False,
        show_progress="hidden",
    )
    return concept, atlas, comparison, mindmap, atlas_change
