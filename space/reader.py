"""Vues de lecture, de navigation dans le système et de discussion des prémisses."""

import html
import re
from contextlib import closing
from functools import lru_cache
from urllib.parse import quote

import gradio as gr

from atlas_graph import (
    DOMAIN_ORDER,
    MINDMAP_CSS,
    MINDMAP_JS,
    render_mindmap,
    render_symbol_lexicon,
)
from contemporary import fetch_contemporary_fact
from deductive_tree import ROLE_CATEGORIES, render_deductive_tree
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
    read_page_content,
    neighbours,
    node_source,
    on_page,
    question_scope,
    search_library,
    suggested_nodes,
)
from wiki_concepts import (
    CONCEPTS,
    annotate_concepts,
    find_concept_for_query,
    render_concept_wiki,
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
    order_argument_steps,
)

esc = html.escape


def card(source, local):
    actions = []
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
    paragraph = (source.get("paragraph") or "").strip()
    excerpt = (source.get("excerpt") or "").strip()
    para_html = ""
    if paragraph and len(paragraph) > len(excerpt) + 25:
        para_html = (
            f'<details class="expand-para"><summary>Voir le paragraphe complet</summary>'
            f'<p lang="en">{esc(paragraph)}</p></details>'
        )
    if source.get("book") and source.get("page"):
        actions.append(
            f'<button type="button" class="open-reader-btn open-reader-sm" '
            f'data-read-book="{esc(source["book"])}" '
            f'data-read-page="{esc(str(source["page"]))}" '
            f'data-read-excerpt="{esc(excerpt[:100])}">'
            f'Lire la page &amp; le chapitre →</button>'
        )
    if local and source.get("file", "").endswith(".pdf") and str(source.get("page", "")).isdecimal():
        pdf = (local / source["file"]).resolve()
        if pdf.parent == local.resolve() and pdf.is_file():
            actions.append(
                f'<a class="wiki-pdf-link" href="/gradio_api/file={quote(str(pdf))}#page={int(source["page"])}" '
                f'target="_blank" rel="noopener">Ouvrir le PDF ↗</a>'
            )
    action_bar = f'<div class="card-actions">{"".join(actions)}</div>' if actions else ""
    return (
        f'<article class="reading-card"><header><strong>{esc(source["title"])}</strong> '
        f"<small>{esc(str(source['year']))} · {esc(source['authors'])}</small></header>"
        f'{imprint}<p class="folio">{esc(source["pages"])}</p>{attribution}'
        f'<blockquote lang="en">{esc(excerpt)}</blockquote>{para_html}{action_bar}</article>'
    )


def render_book_reader(page_data: dict | None, highlight: str = "", local=None) -> str:
    """Rend une page complète dans la liseuse interactive avec contexte de chapitre."""
    if not page_data:
        return ""
    chapter = page_data.get("chapter") or "Section sans titre de chapitre"
    pos = f"Page {page_data.get('chapter_index', 1)} / {page_data.get('chapter_total', 1)} du chapitre"
    pdf_link = ""
    if local and page_data.get("file", "").endswith(".pdf") and str(page_data.get("page", "")).isdecimal():
        pdf = (local / page_data["file"]).resolve()
        if pdf.parent == local.resolve() and pdf.is_file():
            href = f"/gradio_api/file={quote(str(pdf))}#page={int(page_data['page'])}"
            pdf_link = (
                f'<a class="wiki-pdf-link" href="{esc(href)}" target="_blank" rel="noopener">'
                f'Ouvrir le PDF local (p. {int(page_data["page"])}) ↗</a>'
            )

    needle = " ".join((highlight or "").split())[:90]
    needle_re = re.compile(re.escape(needle), re.IGNORECASE) if len(needle) >= 12 else None

    para_blocks = []
    for raw_p in page_data.get("paragraphs") or ():
        safe_p = esc(raw_p)
        if needle_re:
            safe_p = needle_re.sub(
                lambda m: f'<mark class="reader-highlight">{m.group(0)}</mark>',
                safe_p,
                count=1,
            )
        para_blocks.append(f'<p class="reader-para" lang="en">{safe_p}</p>')
    if not para_blocks:
        para_blocks.append('<p class="reader-para">Aucun texte paginé disponible pour cette page.</p>')

    markers_html = ""
    if page_data.get("markers"):
        pills = "".join(
            f'<span class="reader-marker-pill">{esc(m["kind"])} {esc(m["number"])}</span>'
            for m in page_data["markers"]
        )
        markers_html = f'<div class="reader-meta-strip"><strong>Repères sur cette page :</strong> {pills}</div>'

    concepts_html = ""
    if page_data.get("concepts"):
        c_links = "".join(
            f'<a href="#wiki-{esc(k)}" class="wiki-link reader-concept-pill" data-wiki-concept="{esc(k)}">'
            f'{esc(NODES[k]["title"])}</a>'
            for k in page_data["concepts"]
            if k in NODES
        )
        if c_links:
            concepts_html = f'<div class="reader-meta-strip"><strong>Notions de l’Atlas sur cette page :</strong> {c_links}</div>'

    return (
        '<section class="book-reader-card" aria-label="Liseuse de page">'
        '<header class="reader-header">'
        f'<div><span class="reader-kicker">Liseuse · {esc(chapter)} · {esc(pos)}</span>'
        f'<h3>{esc(page_data["title"])}</h3>'
        f'<small>{esc(page_data["authors"])} ({esc(str(page_data["year"]))}) · {esc(page_data["pages"])}'
        + (f' · {esc(page_data["edition_label"])}' if page_data.get("edition_label") else "")
        + f"</small></div>{pdf_link}</header>"
        f"{markers_html}{concepts_html}"
        f'<div class="reader-body">{"".join(para_blocks)}</div>'
        "</section>"
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
                gr.Dropdown(choices=[], value=None, render=False),
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
                render=False,
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
            render=False,
        ),
        compare or "<p>Aucune comparaison éditée pour cette notion.</p>",
    )


def dossier_view(dossier, changes, local):
    if not dossier:
        return ""
    ordered_steps = order_argument_steps(dossier["steps"], dossier.get("title", ""))
    states = assess(ordered_steps, changes)
    sections = [f"<h3>{esc(dossier['title'])}</h3>"]
    title_by_id = {s["id"]: s["title"] for s in ordered_steps}
    for idx, s in enumerate(ordered_steps, 1):
        state = states[s["id"]]
        has_bunge = bool(s.get("sources"))
        has_ext = bool(s.get("external"))
        sources = "".join(card(r, local) for r in s.get("sources") or ())
        for f in s.get("external") or ():
            sources += (
                f'<p class="external-source-item"><strong>Source externe datée (hors Bunge) :</strong> '
                f'<a href="{esc(f["url"], quote=True)}" target="_blank" rel="noopener">{esc(f["title"])}</a></p>'
            )
        if has_bunge and has_ext:
            src_summary = "Voir les sources (Bunge et source externe datée)"
        elif has_ext:
            src_summary = "Voir la source externe datée"
        else:
            src_summary = "Voir la source dans Bunge"
        supports = []
        for group in s["supports"]:
            names = " et ".join(title_by_id[p] for p in group if p in title_by_id)
            unavailable = [title_by_id[p] for p in group if p in states and states[p] != "disponible"]
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
        title_html = (
            f'<a href="#wiki-{esc(s["id"])}" class="wiki-link" data-wiki-concept="{esc(s["id"])}">{esc(s["title"])}</a>'
            if s["id"] in NODES
            else esc(s["title"])
        )
        body_html = annotate_concepts(esc(s["text"]), exclude_key=s["id"])
        sections.append(
            f'<article class="argument-step">'
            f'<div class="step-meta"><span class="step-num">Étape {idx}</span>'
            f'<span class="step-role">{esc(s["role"])}</span>'
            f'<span class="step-pill {pill_cls}">{esc(state)}</span></div>'
            f"<h4>{title_html}</h4>"
            f"<p>{body_html}</p>"
            + (
                f"<p><strong>Votre hypothèse :</strong> {esc(replacement)}</p>"
                if replacement
                else ""
            )
            + ("<p><small>Dépend de :</small></p><ul>" + "".join(supports) + "</ul>" if supports else "")
            + (
                f"<details><summary>{src_summary}</summary>{sources}</details>"
                if sources
                else ""
            )
            + "</article>"
        )
    sections.append(
        f"<h4>Objection</h4><p>{annotate_concepts(esc(dossier['objection']))}</p>"
        f"<h4>Question ouverte</h4><p>{annotate_concepts(esc(dossier['open']))}</p>"
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


def _format_debate_inline(text: str) -> str:
    safe = esc(text)
    safe = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", safe)
    return annotate_concepts(safe)


def _render_debate_body(text: str) -> str:
    """Rend proprement les paragraphes et listes d’une réponse de débat structurée."""
    raw = (text or "").strip()
    if not raw:
        return ""
    blocks = re.split(r"\n{2,}", raw)
    out = []
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        if all(re.match(r"^(?:[-•*]|\d+[.)])\s+", ln) for ln in lines):
            items = "".join(
                f"<li>{_format_debate_inline(re.sub(r'^(?:[-•*]|\d+[.)])\s+', '', ln))}</li>"
                for ln in lines
            )
            out.append(f'<ul class="debate-points">{items}</ul>')
        else:
            joined = " ".join(lines)
            out.append(f"<p>{_format_debate_inline(joined)}</p>")
    return "".join(out)


def render_debate(history, local, notice=""):
    if not history and not notice:
        return (
            '<div class="debate-empty"><p>Aucun échange en cours. '
            "Choisissez une question ci-dessus ou écrivez votre thèse ou objection ci-dessous.</p></div>"
        )
    blocks = ['<div class="debate-thread">']
    for item in history or []:
        src_list = item.get("sources") or []
        src_html = "".join(card(s, local) for s in src_list)
        ext = item.get("external")
        ext_html = (
            f'<p class="debate-external-badge"><strong>Source externe datée (hors Bunge) :</strong> '
            f'<a href="{esc(ext["url"], quote=True)}" target="_blank" rel="noopener">{esc(ext["title"])}</a></p>'
            if ext and ext.get("url")
            else ""
        )
        impact = (
            f'<p class="debate-impact"><strong>Point logique :</strong> {_format_debate_inline(item["impact"])}</p>'
            if item.get("impact")
            else ""
        )
        follow_q = (
            f'<p class="debate-followup"><small>Piste de discussion : {esc(item["next_question"])}</small></p>'
            if item.get("next_question")
            else ""
        )
        blocks.append(
            f'<div class="debate-turn">'
            f'<div class="debate-user-bubble"><span class="debate-role-tag">Vous · Tour {int(item["turn"])}</span>'
            f"<p>{esc(item['user'])}</p>{ext_html}</div>"
            f'<article class="debate-bot-card"><span class="debate-role-tag">BungeRAG · Réponse sourcée</span>'
            f'<div class="debate-answer-body">{_render_debate_body(item["answer"])}</div>{impact}{follow_q}'
            + (
                f"<details class='debate-sources'><summary>Passages de Bunge cités ({len(src_list)})</summary>{src_html}</details>"
                if src_html
                else ""
            )
            + "</article></div>"
        )
    blocks.append("</div>")
    if notice:
        blocks.append(f'<p role="status">{esc(notice)}</p>')
    return "".join(blocks)


def build_reader(legacy, local, create_dossier, max_chars, run_debate=None):
    concept_options = sorted(
        ((c["title"], cid) for cid, c in CONCEPTS.items()), key=lambda x: fold(x[0])
    )
    node_options = sorted(
        ((n["title"], k) for k, n in NODES.items()), key=lambda x: fold(x[0])
    )
    coverage_html, book_options, first_book = coverage()
    initial_wiki_html = render_concept_wiki("systemisme", local)
    initial_tree_html = render_deductive_tree("Tous les domaines", "ALL", "", local)
    research = gr.State([])
    saved_question = gr.State("")
    inline_dossier = gr.State({})
    reader_state = gr.State({"book": "", "page": "", "highlight": ""})
    debate_history = gr.State([])
    sections = (
        ("Rechercher", "search"),
        ("Concepts", "atlas"),
        ("Débat", "work"),
    )
    suggestions = (
        ("L’émergence", "Qu'est-ce que l'émergence pour Bunge ?"),
        ("Causalité vs déterminisme", "Quelle différence entre causalité et déterminisme ?"),
        ("Un LLM peut-il comprendre ?", "Un modèle de langage peut-il comprendre ?"),
        ("Bonheur complet ?", "Peut-on être complètement heureux selon Bunge ?"),
    )
    debate_starters = (
        ("Un LLM peut-il comprendre ?", "Un modèle de langage peut-il comprendre selon le cadre de Bunge ?"),
        ("Holisme vs systémisme", "Le holisme n’est-il pas plus pertinent que le systémisme ?"),
        ("Bonheur complet ?", "Peut-on atteindre un bonheur complet selon Bunge ?"),
        ("Causalité et fatalisme", "La causalité implique-t-elle le fatalisme ?"),
    )
    # Ponts JS → Gradio invisibles pour ouvrir une fiche de concept ou la liseuse depuis n'importe quel lien bleu/bouton.
    wiki_bridge = gr.Textbox(value="", elem_id="wiki-bridge", elem_classes=["sr-bridge"], show_label=False)
    reader_bridge = gr.Textbox(value="", elem_id="reader-bridge", elem_classes=["sr-bridge"], show_label=False)

    with gr.Row(elem_id="reader-quicknav"):
        mobile_navigation = [
            (gr.Button(label, size="sm"), section) for label, section in sections
        ]
    with gr.Tabs(selected="search", elem_id="reader-tabs") as tabs:
        with gr.Tab("Rechercher", id="search"):
            with gr.Column(elem_id="chat-shell"):
                q = gr.Textbox(
                    label="Que dit Mario Bunge à propos de… ?",
                    placeholder="Ex. émergence, causalité, psychanalyse, modèle factuel, ℳ = ⟨D, F, I⟩",
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
                    ai_go = gr.Button("Réponse sourcée (IA)", variant="primary", scale=2)
                    go = gr.Button("Rechercher les passages", variant="secondary", scale=1)
                with gr.Row(elem_classes=["action-bar", "followup-bar"]):
                    expand = gr.Button("Déplier l’argument", visible=False)
                    locate = gr.Button("Fiche du concept", visible=False)
                    discuss = gr.Button("En débattre", visible=False)
                legacy_fn, legacy_outputs = legacy(
                    q,
                    ai_go,
                    triggers=(q.submit,),
                    followup_buttons=(expand, locate, discuss),
                )
                hits = gr.HTML()
                inline = gr.HTML()
            with gr.Column(elem_id="book-reader-panel", elem_classes=["glass-panel", "book-reader-shell"]):
                with gr.Row(elem_classes=["reader-nav-bar"]):
                    reader_prev = gr.Button("← Page précédente", size="sm", visible=False)
                    reader_jump = gr.Dropdown(
                        label="Parcourir le chapitre",
                        choices=[],
                        value=None,
                        visible=False,
                        scale=3,
                    )
                    reader_next = gr.Button("Page suivante →", size="sm", visible=False)
                    reader_close = gr.Button("Fermer la liseuse", size="sm", visible=False)
                reader_view = gr.HTML("")

        with gr.Tab("Concepts", id="atlas"):
            with gr.Column(elem_classes=["glass-panel"]):
                with gr.Row(elem_classes=["inline-submit-row"]):
                    concept = gr.Dropdown(
                        concept_options,
                        value="systemisme",
                        label=f"Sélectionner un concept philosophique ou scientifique ({len(concept_options)} concepts)",
                        scale=3,
                    )
                    to_work = gr.Button("En débattre →", scale=1)
                wiki_view = gr.HTML(initial_wiki_html)
            with gr.Column(elem_classes=["glass-panel"]):
                gr.HTML(
                    '<div class="section-heading"><h3>Arbre déductif du système (113 propositions)</h3>'
                    "<p>Définitions, postulats, thèses, théorèmes et corollaires classés par domaine et par dépendance logique.</p></div>"
                )
                with gr.Row(elem_classes=["tree-filter-row"]):
                    tree_domain = gr.Dropdown(
                        ["Tous les domaines", *DOMAIN_ORDER],
                        value="Tous les domaines",
                        label="Domaine",
                        scale=2,
                    )
                    tree_role = gr.Dropdown(
                        list(ROLE_CATEGORIES),
                        value="ALL",
                        label="Nature",
                        scale=2,
                    )
                    tree_search = gr.Textbox(
                        label="Filtrer l’arbre",
                        placeholder="Ex. postulat 1.5, théorème, bonheur, synonymie",
                        scale=2,
                    )
                tree_view = gr.HTML(initial_tree_html)
            with gr.Accordion("Carte visuelle des relations (6 domaines · 113 propositions)", open=False):
                mindmap = gr.HTML(
                    render_mindmap("systemisme"),
                    css_template=MINDMAP_CSS,
                    js_on_load=MINDMAP_JS,
                )
            with gr.Accordion("Symboles et notations formelles (16)", open=False):
                symbol_filter = gr.Textbox(
                    label="Filtrer par symbole ou mot-clé",
                    placeholder="Ex. ℳ, ⊑, σ, psychon, vérité, bien-être",
                )
                symbol_lexicon = gr.HTML(render_symbol_lexicon())
            with gr.Accordion("Ouvrages indexés et comparaison entre éditions (25 livres)", open=False):
                with gr.Row(elem_classes=["inline-submit-row"]):
                    paired = gr.Dropdown(
                        node_options,
                        label="Comparer avec une autre proposition",
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

        with gr.Tab("Débat", id="work"):
            with gr.Column(elem_classes=["glass-panel"]):
                gr.HTML(
                    '<div class="section-heading"><h3>Débat philosophique sourcé</h3>'
                    "<p>Soumettez une thèse, une objection ou un cas contemporain. Chaque réponse s’appuie sur des passages vérifiés de Mario Bunge et distingue ses textes de vos hypothèses.</p></div>"
                )
                with gr.Row(elem_classes=["suggestion-row"]):
                    debate_starter_buttons = [
                        (gr.Button(short, size="sm"), full)
                        for short, full in debate_starters
                    ]
                debate_view = gr.HTML(render_debate([], local))
                debate_input = gr.Textbox(
                    label="Votre thèse, objection ou réponse",
                    placeholder="Ex. Un modèle de langage manipule des symboles sans cerveau biologique : peut-on parler de compréhension ?",
                    lines=2,
                )
                with gr.Row(elem_classes=["action-bar"]):
                    debate_send = gr.Button("Envoyer", variant="primary", scale=2)
                    debate_clear = gr.Button("Nouveau débat", scale=1)
                with gr.Accordion("Joindre une source externe datée (optionnel, hors Bunge)", open=False):
                    with gr.Row(elem_classes=["inline-submit-row"]):
                        fact_lookup = gr.Textbox(
                            label="URL HTTPS publique ou sujet Wikipédia",
                            placeholder="https://… ou ex. AlphaFold, Llama 3.1",
                            scale=3,
                        )
                        fact_fetch = gr.Button("Pré-remplir", scale=1)
                    fact_status = gr.HTML()
                    supplied_fact = gr.Textbox(label="Fait contemporain", lines=2)
                    with gr.Row():
                        supplied_link = gr.Textbox(label="URL HTTPS de la source")
                        supplied_date = gr.Textbox(
                            label="Date", placeholder="AAAA-MM-JJ"
                        )

    for button, section in mobile_navigation:
        button.click(
            lambda selected=section: gr.Tabs(selected=selected),
            outputs=tabs,
            api_name=False,
            queue=False,
            show_progress="hidden",
        )

    def _mindmap_key(key):
        if key in NODES:
            return key
        if key in CONCEPTS and CONCEPTS[key].get("nodes"):
            first = CONCEPTS[key]["nodes"][0]
            if first in NODES:
                return first
        return "systemisme"

    def atlas_change(key):
        if key in CONCEPTS or key in NODES:
            return render_concept_wiki(key, local), render_mindmap(_mindmap_key(key))
        view_html, _, _ = atlas_view(key, local)
        return view_html, render_mindmap("systemisme")

    concept.change(
        atlas_change,
        concept,
        [wiki_view, mindmap],
        api_name=False,
        show_progress="hidden",
    )

    def update_tree(dom, role_val, query_txt):
        return render_deductive_tree(dom, role_val, query_txt, local)

    for ev in (tree_domain.change, tree_role.change, tree_search.input):
        ev(
            update_tree,
            [tree_domain, tree_role, tree_search],
            tree_view,
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
        if key in CONCEPTS:
            return gr.Dropdown(choices=concept_options, value=key)
        if key in NODES:
            return gr.Dropdown(choices=concept_options + [(NODES[key]["title"], key)], value=key)
        record = read_marker(key)
        if not record:
            return gr.skip()
        return gr.Dropdown(choices=concept_options + [(record[0], key)], value=key)

    open_marker.click(
        select_concept, marker, concept, api_name=False, show_progress="hidden"
    )

    # Navigation au clic sur n'importe quel concept souligné en bleu ou lien vers une proposition
    def open_wiki_from_link(payload):
        raw = (payload or "").split("::", 1)[0].strip()
        if not raw or (raw not in CONCEPTS and raw not in NODES):
            return gr.skip(), gr.skip(), gr.skip(), gr.skip()
        return (
            gr.Tabs(selected="atlas"),
            select_concept(raw),
            render_concept_wiki(raw, local),
            render_mindmap(_mindmap_key(raw)),
        )

    wiki_bridge.change(
        open_wiki_from_link,
        wiki_bridge,
        [tabs, concept, wiki_view, mindmap],
        api_name=False,
        show_progress="hidden",
    )

    # Liseuse interactive de page et de chapitre
    def _render_reader_state(book_id: str, page_str: str, highlight: str = ""):
        data = read_page_content(book_id, page_str)
        if not data:
            return (
                {"book": "", "page": "", "highlight": ""},
                gr.update(visible=False),
                gr.update(visible=False, choices=[], value=None),
                gr.update(visible=False),
                gr.update(visible=False),
                "<p>Page indisponible dans l’index.</p>",
            )
        return (
            {
                "book": data["book"],
                "page": data["page"],
                "prev": data["prev_page"],
                "next": data["next_page"],
                "highlight": highlight,
            },
            gr.update(visible=True, interactive=bool(data["prev_page"])),
            gr.update(
                visible=True,
                choices=data["chapter_pages"],
                value=data["page"],
                label=f"Parcourir · {data['chapter'] or data['title']}",
            ),
            gr.update(visible=True, interactive=bool(data["next_page"])),
            gr.update(visible=True),
            render_book_reader(data, highlight=highlight, local=local),
        )

    reader_outputs = [
        reader_state,
        reader_prev,
        reader_jump,
        reader_next,
        reader_close,
        reader_view,
    ]

    def open_reader_from_bridge(payload):
        parts = (payload or "").split("||")
        if len(parts) < 2 or not parts[0] or not parts[1]:
            return (gr.skip(),) * 7
        book_id, page_str = parts[0].strip(), parts[1].strip()
        highlight = parts[2].strip() if len(parts) >= 3 else ""
        return (gr.Tabs(selected="search"), *_render_reader_state(book_id, page_str, highlight))

    reader_bridge.change(
        open_reader_from_bridge,
        reader_bridge,
        [tabs, *reader_outputs],
        api_name=False,
        show_progress="hidden",
    )

    def reader_step(state, direction):
        if not state or not state.get("book"):
            return (gr.skip(),) * 6
        target = state.get(direction) or ""
        if not target:
            return (gr.skip(),) * 6
        return _render_reader_state(state["book"], target, "")

    reader_prev.click(
        lambda s: reader_step(s, "prev"),
        reader_state,
        reader_outputs,
        api_name=False,
        show_progress="hidden",
    )
    reader_next.click(
        lambda s: reader_step(s, "next"),
        reader_state,
        reader_outputs,
        api_name=False,
        show_progress="hidden",
    )
    reader_jump.input(
        lambda s, p: _render_reader_state(s["book"], p, "") if s and s.get("book") and p else (gr.skip(),) * 6,
        [reader_state, reader_jump],
        reader_outputs,
        api_name=False,
        show_progress="hidden",
    )
    reader_close.click(
        lambda: (
            {"book": "", "page": "", "highlight": ""},
            gr.update(visible=False),
            gr.update(visible=False, choices=[], value=None),
            gr.update(visible=False),
            gr.update(visible=False),
            "",
        ),
        outputs=reader_outputs,
        api_name=False,
        show_progress="hidden",
    )

    def paired_cards(left, right):
        if not left or not right:
            return "<p>Choisissez une seconde proposition à comparer.</p>"
        left_key = _mindmap_key(left) if left in CONCEPTS else left
        sources = [
            node_source(k) if k in NODES else read_marker(k)[1] for k in (left_key, right)
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
        ordered = order_argument_steps(d.get("steps", []), d.get("title", ""))
        d = {**d, "steps": ordered}
        return (
            d,
            {},
            dossier_view(d, {}, local),
            gr.Dropdown(
                choices=[(s["title"], s["id"]) for s in ordered],
                value=(ordered[0]["id"] if ordered else None),
            ),
        )

    def _next_btns(show: bool):
        u = gr.update(visible=show)
        return u, u, u

    def lookup(question, request: gr.Request):
        question = " ".join((question or "").split())
        if not 3 <= len(question) <= max_chars:
            yield (
                [],
                question,
                "<p>Saisissez une recherche entre 3 et "
                + str(max_chars)
                + " caractères.</p>",
                *_next_btns(False),
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
                *_next_btns(False),
                "",
                {},
            )
            return
        yield (
            [],
            question,
            '<div class="bunge-loading-bar" aria-label="Recherche en cours"></div>',
            *_next_btns(False),
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
                *_next_btns(bool(related)),
                dossier_view(dossier_obj, {}, local),
                dossier_obj,
            )
            return
        result = search_library(question)
        rendered = (
            "".join(card(s, local) for s in result) or "<p>Passage non retrouvé.</p>"
        )
        yield result, question, rendered, *_next_btns(bool(result)), "", {}
        if wants_proof:
            d = get_dossier(question, None, result, request)
            yield (
                result,
                question,
                rendered,
                *_next_btns(True),
                dossier_view(d, {}, local),
                d,
            )

    lookup_outputs = [
        research,
        saved_question,
        hits,
        expand,
        locate,
        discuss,
        inline,
        inline_dossier,
    ]
    go.click(
        lookup,
        inputs=q,
        outputs=lookup_outputs,
        api_name=False,
        show_progress="hidden",
        concurrency_id="reader",
        concurrency_limit=1,
    )

    for btn, preset in suggestion_buttons:
        def _run_preset(request: gr.Request, text=preset):
            for step_out in legacy_fn(text, request):
                yield (text, *step_out)

        btn.click(
            _run_preset,
            outputs=[q, *legacy_outputs],
            api_name=False,
            show_progress="hidden",
            concurrency_id="rag",
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
        cid = find_concept_for_query(q_text)
        if cid:
            return gr.Tabs(selected="atlas"), select_concept(cid), *atlas_change(cid)
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
                gr.Dropdown(choices=concept_options, value="systemisme"),
                initial_wiki_html,
                render_mindmap("systemisme"),
            )
        key = nodeids[0]
        return gr.Tabs(selected="atlas"), select_concept(key), *atlas_change(key)

    locate.click(
        focus,
        [q, saved_question, research],
        [tabs, concept, wiki_view, mindmap],
        api_name=False,
        show_progress="hidden",
    )

    def _send_debate_core(hist, text, fact, link, published, request: gr.Request):
        clean_text = " ".join((text or "").split())
        if len(clean_text) < 3:
            yield hist, render_debate(hist, local, "Saisissez une thèse ou une question d’au moins 3 caractères."), text
            return
        try:
            external = contemporary_claim(fact, link, published)
        except ValueError as exc:
            yield hist, render_debate(hist, local, str(exc)), text
            return
        yield (
            hist,
            render_debate(hist, local)
            + '<div class="bunge-loading-bar" aria-label="Recherche dans Bunge"></div>',
            clean_text,
        )
        if run_debate is not None:
            new_hist, notice = run_debate(None, {}, hist, clean_text, request, external=external)
        else:
            new_hist, notice = debate_turn(None, {}, hist, clean_text, external=external)
        yield new_hist, render_debate(new_hist, local, notice), "" if not notice else clean_text

    def from_search_to_debate(q_text, hist, fact, link, published, request: gr.Request):
        prompt_q = (q_text or "").strip() or "Qu’apporte le systémisme de Bunge ?"
        for new_hist, html_out, inp in _send_debate_core(hist, prompt_q, fact, link, published, request):
            yield gr.Tabs(selected="work"), new_hist, html_out, inp

    discuss.click(
        from_search_to_debate,
        [q, debate_history, supplied_fact, supplied_link, supplied_date],
        [tabs, debate_history, debate_view, debate_input],
        api_name=False,
        show_progress="hidden",
        concurrency_id="reader",
        concurrency_limit=1,
    )

    def from_concepts_to_debate(key, hist, fact, link, published, request: gr.Request):
        if key in CONCEPTS:
            topic = f"Que vaut la position de Bunge sur le concept de {CONCEPTS[key]['title']} ?"
        elif key in NODES:
            topic = f"Peut-on contester « {NODES[key]['title']} » chez Bunge ?"
        else:
            topic = "Qu’apporte le systémisme de Bunge ?"
        for new_hist, html_out, inp in _send_debate_core(hist, topic, fact, link, published, request):
            yield gr.Tabs(selected="work"), new_hist, html_out, inp

    to_work.click(
        from_concepts_to_debate,
        [concept, debate_history, supplied_fact, supplied_link, supplied_date],
        [tabs, debate_history, debate_view, debate_input],
        api_name=False,
        show_progress="hidden",
        concurrency_id="reader",
        concurrency_limit=1,
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
            f'<p role="status">Source externe pré-remplie ({esc(item["title"])}) — distincte des textes de Bunge.</p>',
        )

    fact_fetch.click(
        prefill_fact,
        fact_lookup,
        [supplied_fact, supplied_link, supplied_date, fact_status],
        api_name=False,
        show_progress="hidden",
    )

    for event in (debate_send.click, debate_input.submit):
        event(
            _send_debate_core,
            [debate_history, debate_input, supplied_fact, supplied_link, supplied_date],
            [debate_history, debate_view, debate_input],
            api_name=False,
            show_progress="hidden",
            concurrency_id="reader",
            concurrency_limit=1,
        )

    for btn, starter_text in debate_starter_buttons:
        def _run_starter(hist, fact, link, published, request: gr.Request, text=starter_text):
            for step_out in _send_debate_core(hist, text, fact, link, published, request):
                yield step_out

        btn.click(
            _run_starter,
            [debate_history, supplied_fact, supplied_link, supplied_date],
            [debate_history, debate_view, debate_input],
            api_name=False,
            show_progress="hidden",
            concurrency_id="reader",
            concurrency_limit=1,
        )

    debate_clear.click(
        lambda: ([], render_debate([], local), "", "", "", "", ""),
        outputs=[debate_history, debate_view, debate_input, supplied_fact, supplied_link, supplied_date, fact_status],
        api_name=False,
        show_progress="hidden",
    )
    return concept, wiki_view, mindmap, atlas_change
