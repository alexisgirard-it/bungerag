"""Répertoire des concepts philosophiques/scientifiques, liens bleus et fiches structurées."""

from __future__ import annotations

import html
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import library
from atlas_graph import DOMAIN_COLORS
from deductive_tree import role_category
from library import (
    DATABASE,
    NODES,
    chapter_formal_markers,
    fold,
    neighbours,
    node_source,
    passage_context,
)

esc = html.escape

_CONCEPTS_RAW = json.loads(
    Path(library.__file__).with_name("concepts.json").read_text(encoding="utf-8")
)
CONCEPTS_VERSION: str = _CONCEPTS_RAW["version"]
CONCEPTS: dict[str, dict] = {c["id"]: c for c in _CONCEPTS_RAW["concepts"]}

# Compatibilité descendante pour la résolution d’alias.
CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {
    cid: tuple(c["aliases"]) for cid, c in CONCEPTS.items()
}


@lru_cache(maxsize=1)
def _compiled_glossary() -> tuple[re.Pattern[str], dict[str, str]]:
    """Automate regex sur les 63 concepts philosophiques et scientifiques (termes longs d'abord)."""
    term_to_key: dict[str, str] = {}
    for cid, concept in CONCEPTS.items():
        for alias in concept.get("aliases", ()):
            clean = alias.strip()
            if len(clean) >= 4:
                term_to_key.setdefault(clean.casefold(), cid)
        title = concept["title"].split("(")[0].strip()
        if len(title) >= 4:
            term_to_key.setdefault(title.casefold(), cid)
    ordered = sorted(term_to_key.keys(), key=len, reverse=True)
    if not ordered:
        return re.compile(r"(?!x)x"), {}
    pattern = re.compile(
        r"(?<!\w)(" + "|".join(re.escape(t) for t in ordered) + r")(?!\w)",
        re.IGNORECASE,
    )
    return pattern, term_to_key


_TAG_SPLIT_RE = re.compile(r"(<[^>]+>)")
_SKIP_OPEN = {"a", "code", "pre", "script", "style", "summary", "h1", "h2", "button"}


def annotate_concepts(html_text: str, *, exclude_key: str | None = None) -> str:
    """Souligne en bleu les concepts philosophiques et scientifiques reconnus dans du HTML."""
    if not html_text or not isinstance(html_text, str):
        return html_text or ""
    pattern, lookup = _compiled_glossary()
    if not lookup:
        return html_text

    parts = _TAG_SPLIT_RE.split(html_text)
    skip_depth = 0
    linked_once: set[str] = set()
    out: list[str] = []

    for part in parts:
        if not part:
            continue
        if part.startswith("<") and part.endswith(">"):
            tag_m = re.match(r"<\s*(/?)\s*([a-zA-Z0-9]+)", part)
            if tag_m:
                closing, name = bool(tag_m.group(1)), tag_m.group(2).lower()
                if name in _SKIP_OPEN and not part.endswith("/>"):
                    skip_depth = max(0, skip_depth - 1) if closing else skip_depth + 1
            out.append(part)
            continue
        if skip_depth > 0:
            out.append(part)
            continue

        def _replace(match: re.Match[str]) -> str:
            text = match.group(1)
            cid = lookup.get(text.casefold())
            if not cid or cid == exclude_key or cid in linked_once or cid not in CONCEPTS:
                return text
            linked_once.add(cid)
            concept = CONCEPTS[cid]
            return (
                f'<a href="#wiki-{esc(cid)}" class="wiki-link" '
                f'data-wiki-concept="{esc(cid)}" '
                f'title="{esc(concept["title"])} ({esc(concept["domain"])})">'
                f"{text}</a>"
            )

        out.append(pattern.sub(_replace, part))
    return "".join(out)


def find_concept_for_query(question: str) -> str | None:
    """Identifie le concept le plus pertinent pour une question utilisateur."""
    qf = fold(question or "")
    if not qf:
        return None
    best: tuple[int, str] | None = None
    for cid, concept in CONCEPTS.items():
        for alias in (concept["title"], *concept.get("aliases", ())):
            af = fold(alias)
            if len(af) >= 4 and af in qf:
                cand = (len(af), cid)
                if best is None or cand[0] > best[0]:
                    best = cand
    return best[1] if best else None


def _group_relation_bucket(kind: str) -> str:
    k = fold(kind)
    if any(w in k for w in ("definition", "postulat", "axiome", "principe", "distinction")):
        return "Définitions & fondements"
    if any(w in k for w in ("theoreme", "corollaire", "norme", "regle")):
        return "Théorèmes, corollaires & normes"
    if any(w in k for w in ("exemple", "critique", "auteur", "objection", "comparaison")):
        return "Exemples, critiques & auteurs cités"
    return "Thèses & propositions liées"


def _dossiers_for_nodes(node_ids: set[str]) -> list[tuple[str, str]]:
    from workshop import DOSSIERS

    found: list[tuple[str, str]] = []
    for dkey, builder in DOSSIERS.items():
        d = builder()
        if any(s.get("id") in node_ids for s in d.get("steps", ())):
            found.append((dkey, d["title"]))
    return found


def _format_quote_with_context(src: dict) -> str:
    raw_quote = src["excerpt"]
    full_ctx = passage_context(src) if DATABASE.is_file() else raw_quote
    clean_ctx = " ".join((full_ctx or raw_quote).split())
    if len(clean_ctx) > len(raw_quote) + 25:
        escaped_ctx = esc(clean_ctx)
        q_re = re.compile(re.escape(esc(raw_quote)), re.IGNORECASE)
        ctx_html = q_re.sub(
            lambda m: f'<mark class="reader-highlight">{m.group(0)}</mark>',
            escaped_ctx,
            count=1,
        )
        prefix = "… " if clean_ctx and clean_ctx[0].islower() else ""
        suffix = " …" if clean_ctx and clean_ctx[-1] not in ".!?" else ""
        return f"{prefix}{ctx_html}{suffix}"
    return f"« {esc(raw_quote)} »"


def _render_concept_page(cid: str, local: Path | None = None) -> str:
    """Rend une fiche encyclopédique pour un concept philosophique ou scientifique."""
    c = CONCEPTS[cid]
    color = DOMAIN_COLORS.get(c["domain"], "#2563eb")
    is_bunge = c.get("status") == "bunge"
    status_label = (
        "Défini / thématisé par Mario Bunge"
        if is_bunge
        else "Sens philosophique / scientifique usuel (cohérent avec Bunge)"
    )
    status_cls = "concept-status-bunge" if is_bunge else "concept-status-standard"

    node_keys = [nid for nid in c.get("nodes", ()) if nid in NODES]
    sources = [(nid, node_source(nid)) for nid in node_keys]
    books = list(dict.fromkeys(f"{src['title']} ({src['year']})" for _, src in sources))
    dossiers = _dossiers_for_nodes(set(node_keys))

    # Infobox latérale
    related_chips = "".join(
        f'<a href="#wiki-{esc(rid)}" class="wiki-link wiki-concept-chip" data-wiki-concept="{esc(rid)}">'
        f'{esc(CONCEPTS[rid]["title"])}</a>'
        for rid in c.get("related_concepts", ())
        if rid in CONCEPTS
    )
    info_rows = [
        ("Domaine", f'<span class="wiki-dot" style="background:{color};"></span> {esc(c["domain"])}'),
        ("Statut", esc(status_label)),
        ("Propositions dans le corpus", f"{len(node_keys)} fiche(s) vérifiée(s)"),
    ]
    if books:
        info_rows.append(("Ouvrages cités", esc(" · ".join(books[:3]))))

    primary_action = ""
    if sources:
        _, first_src = sources[0]
        primary_action = (
            f'<div class="wiki-infobox-actions">'
            f'<button type="button" class="open-reader-btn" data-read-book="{esc(first_src["book"])}" '
            f'data-read-page="{esc(str(first_src["page"]))}" data-read-excerpt="{esc(first_src["excerpt"][:120])}">'
            f'Lire le passage principal ({esc(first_src["pages"])}) →</button></div>'
        )

    infobox_html = (
        '<aside class="wiki-infobox" aria-label="Repères conceptuels">'
        f'<div class="wiki-infobox-head" style="border-top-color:{color};">'
        f'<span class="wiki-infobox-kicker">Repères du concept</span>'
        f'<strong>{esc(c["title"])}</strong></div>'
        "<dl>"
        + "".join(f"<div><dt>{label}</dt><dd>{val}</dd></div>" for label, val in info_rows)
        + "</dl>"
        + (
            f'<div class="wiki-infobox-related"><dt>Concepts associés</dt><div class="wiki-concept-chips">{related_chips}</div></div>'
            if related_chips
            else ""
        )
        + primary_action
        + "</aside>"
    )

    # Définition & position de Bunge (soulignement bleu sur tous les concepts connexes !)
    def_html = annotate_concepts(esc(c["definition"]), exclude_key=cid)
    bunge_html = annotate_concepts(esc(c["bunge_view"]), exclude_key=cid)
    lead_html = (
        '<div class="wiki-lead">'
        f'<p class="wiki-summary">{def_html}</p>'
        f'<div class="wiki-bunge-box"><strong>Chez Mario Bunge</strong><p>{bunge_html}</p></div>'
        "</div>"
    )

    # Passages sourcés principaux (jusqu'à 2 passages avec contexte de page surligné)
    passages_html = ""
    if sources:
        blocks = []
        for nid, src in sources[:2]:
            quote_body = _format_quote_with_context(src)
            pdf_btn = ""
            if local and src.get("file", "").endswith(".pdf") and str(src.get("page", "")).isdecimal():
                pdf = (local / src["file"]).resolve()
                if pdf.parent == local.resolve() and pdf.is_file():
                    href = f"/gradio_api/file={quote(str(pdf))}#page={int(src['page'])}"
                    pdf_btn = f'<a class="wiki-pdf-link" href="{esc(href)}" target="_blank" rel="noopener">PDF p. {int(src["page"])} ↗</a>'
            blocks.append(
                f'<blockquote class="wiki-quote" lang="en">{quote_body}'
                f'<footer>— {esc(src["authors"])}, <em>{esc(src["title"])}</em> ({esc(str(src["year"]))}), {esc(src["pages"])}'
                + (f' · {esc(src["edition_label"])}' if src.get("edition_label") else "")
                + f'<div class="source-actions">'
                f'<button type="button" class="open-reader-btn open-reader-sm" '
                f'data-read-book="{esc(src["book"])}" data-read-page="{esc(str(src["page"]))}" '
                f'data-read-excerpt="{esc(src["excerpt"][:100])}">Lire la page &amp; le chapitre →</button>'
                f"{pdf_btn}</div></footer></blockquote>"
            )
        passages_html = f'<section class="wiki-section"><h3>Passages de référence dans le corpus</h3>{"".join(blocks)}</section>'

    # Propositions formelles associées (Définitions, Postulats, Thèses, Théorèmes, Corollaires)
    props_html = ""
    if sources:
        prop_items = []
        for nid, src in sources:
            node = NODES[nid]
            cat = role_category(node["kind"])
            formula_bit = (
                f'<div class="dtree-formula"><code>{esc(node["notation"]["formula"])}</code></div>'
                if node.get("notation")
                else ""
            )
            prop_items.append(
                f'<li class="wiki-rel-item">'
                f'<div class="wiki-rel-head">'
                f'<span class="dtree-role dtree-role-{cat}">{esc(node["kind"])}</span>'
                f'<a href="#wiki-{esc(nid)}" class="wiki-link" data-wiki-concept="{esc(nid)}">{esc(node["title"])}</a>'
                f"</div>"
                f'<p class="wiki-rel-summary">{annotate_concepts(esc(node["text"]), exclude_key=cid)}</p>'
                f"{formula_bit}"
                f'<p class="wiki-rel-desc">{esc(src["title"])} ({esc(str(src["year"]))}) · {esc(src["pages"])}</p>'
                f"</li>"
            )
        props_html = (
            f'<section class="wiki-section">'
            f'<h3>Définitions, postulats, thèses et théorèmes associés ({len(prop_items)})</h3>'
            f'<ul class="wiki-rel-list">{"".join(prop_items)}</ul></section>'
        )

    dossiers_html = ""
    if dossiers:
        d_chips = "".join(f'<span class="wiki-dossier-chip">{esc(title)}</span>' for _, title in dossiers)
        dossiers_html = (
            f'<section class="wiki-section"><h3>Questions associées</h3>'
            f'<div class="wiki-dossier-list">{d_chips}</div></section>'
        )

    return (
        f'<article class="wiki-article" data-concept-key="{esc(cid)}">'
        f'<nav class="wiki-breadcrumb" aria-label="Fil d’Ariane">'
        f'<span>Concepts</span> › <span style="color:{color};font-weight:600;">{esc(c["domain"])}</span> › <span>{esc(c["title"])}</span></nav>'
        f'<header class="wiki-title-bar"><h2>{esc(c["title"])}</h2>'
        f'<span class="concept-status-pill {status_cls}">{esc(status_label)}</span></header>'
        f'<div class="wiki-grid">'
        f'<div class="wiki-main">{lead_html}{passages_html}{props_html}{dossiers_html}</div>'
        f"{infobox_html}"
        f"</div></article>"
    )


def render_concept_wiki(key: str, local: Path | None = None) -> str:
    """Rend une fiche de concept (63 concepts) ou une fiche de proposition formelle (113 fiches)."""
    if key in CONCEPTS:
        return _render_concept_page(key, local)
    if key not in NODES:
        return "<p>Sélectionnez un concept ou une proposition dans l’Atlas.</p>"

    node = NODES[key]
    color = DOMAIN_COLORS.get(node["domain"], "#2563eb")
    src = node_source(key)
    edges = neighbours(key)
    notation = node.get("notation")
    voice = src.get("voice") if src.get("voice") not in (None, "Bunge") else ""

    parent_concepts = [
        (cid, c["title"]) for cid, c in CONCEPTS.items() if key in c.get("nodes", ())
    ]
    parent_links = "".join(
        f'<a href="#wiki-{esc(cid)}" class="wiki-link wiki-concept-chip" data-wiki-concept="{esc(cid)}">{esc(title)}</a>'
        for cid, title in parent_concepts
    )

    info_rows = [
        ("Domaine", f'<span class="wiki-dot" style="background:{color};"></span> {esc(node["domain"])}'),
        ("Nature", esc(node["kind"])),
        ("Ouvrage", esc(src["title"])),
        ("Année", esc(str(src["year"]))),
        ("Pagination", esc(src["pages"])),
    ]
    if src.get("chapter"):
        info_rows.append(("Chapitre", esc(src["chapter"])))
    if voice:
        info_rows.append(("Voix citée", esc(voice)))
    if notation:
        info_rows.append(("Notation", f'<code>{esc(notation["formula"])}</code>'))
    info_rows.append(("Liens directs", f"{len(edges)} proposition(s)"))

    infobox_html = (
        '<aside class="wiki-infobox" aria-label="Repères bibliographiques">'
        f'<div class="wiki-infobox-head" style="border-top-color:{color};">'
        f'<span class="wiki-infobox-kicker">Repères bibliographiques</span>'
        f'<strong>{esc(node["title"])}</strong></div>'
        "<dl>"
        + "".join(f"<div><dt>{label}</dt><dd>{val}</dd></div>" for label, val in info_rows)
        + "</dl>"
        + (
            f'<div class="wiki-infobox-related"><dt>Concepts liés</dt><div class="wiki-concept-chips">{parent_links}</div></div>'
            if parent_links
            else ""
        )
        + f'<div class="wiki-infobox-actions">'
        f'<button type="button" class="open-reader-btn" data-read-book="{esc(src["book"])}" '
        f'data-read-page="{esc(str(src["page"]))}" data-read-excerpt="{esc(src["excerpt"][:120])}">'
        f'Lire dans le livre ({esc(src["pages"])}) →</button>'
    )
    if local and src.get("file") and str(src.get("page", "")).isdecimal():
        pdf = (local / src["file"]).resolve()
        if pdf.parent == local.resolve() and pdf.is_file():
            href = f"/gradio_api/file={quote(str(pdf))}#page={int(src['page'])}"
            infobox_html += (
                f'<a class="wiki-pdf-link" href="{esc(href)}" target="_blank" rel="noopener">'
                f'Ouvrir le PDF local (p. {int(src["page"])}) ↗</a>'
            )
    infobox_html += "</div></aside>"

    lead_text = annotate_concepts(esc(node["text"]), exclude_key=key)
    voice_note = (
        f'<p class="wiki-voice-banner"><strong>Voix citée :</strong> {esc(voice)} (exposé par Bunge, non attribué à Bunge).</p>'
        if voice
        else ""
    )
    quote_body = _format_quote_with_context(src)
    lead_html = (
        f'<div class="wiki-lead">'
        f'<p class="wiki-summary">{lead_text}</p>'
        f"{voice_note}"
        f'<blockquote class="wiki-quote" lang="en">{quote_body}'
        f'<footer>— {esc(src["authors"])}, <em>{esc(src["title"])}</em> ({esc(str(src["year"]))}), {esc(src["pages"])}'
        + (f' · {esc(src["edition_label"])}' if src.get("edition_label") else "")
        + "</footer></blockquote></div>"
    )

    notation_html = ""
    if notation:
        notation_html = (
            '<section class="wiki-section"><h3>Notation formelle</h3>'
            f'<div class="symbol-formula-box formula">{esc(notation["formula"])}</div>'
            f'<p>{annotate_concepts(esc(notation["gloss"]), exclude_key=key)}</p>'
            f'<small class="wiki-muted">{esc(notation["status"])}</small></section>'
        )

    buckets: dict[str, list[str]] = {
        "Définitions & fondements": [],
        "Thèses & propositions liées": [],
        "Théorèmes, corollaires & normes": [],
        "Exemples, critiques & auteurs cités": [],
    }
    for edge in edges:
        origin_key, target_key = edge["origin"], edge["target"]
        other_key = target_key if origin_key == key else origin_key
        other = NODES[other_key]
        other_color = DOMAIN_COLORS.get(other["domain"], "#2563eb")
        bucket = _group_relation_bucket(other["kind"])
        witness_src = node_source(edge["witness"])
        other_link = (
            f'<a href="#wiki-{esc(other_key)}" class="wiki-link" data-wiki-concept="{esc(other_key)}">'
            f"{esc(other['title'])}</a>"
        )
        rel_sentence = (
            f"<strong>{esc(NODES[origin_key]['title'])}</strong> "
            f"<em>{esc(edge['verb'])}</em> "
            f"<strong>{esc(NODES[target_key]['title'])}</strong>"
        )
        buckets[bucket].append(
            f'<li class="wiki-rel-item">'
            f'<div class="wiki-rel-head"><span class="wiki-dot" style="background:{other_color};"></span>'
            f'{other_link} <span class="wiki-kind-tag">{esc(other["kind"])}</span></div>'
            f'<p class="wiki-rel-summary">{esc(other["text"])}</p>'
            f'<p class="wiki-rel-desc">{esc(edge["kind"])} · {rel_sentence}.</p>'
            f'<details class="wiki-witness"><summary>Témoin textuel ({esc(witness_src["title"])}, {esc(witness_src["pages"])})</summary>'
            f'<blockquote lang="en">« {esc(witness_src["excerpt"])} »</blockquote></details></li>'
        )

    rel_sections = [
        f'<section class="wiki-section"><h3>{esc(heading)} ({len(items)})</h3><ul class="wiki-rel-list">{"".join(items)}</ul></section>'
        for heading, items in buckets.items()
        if items
    ]

    markers_html = ""
    if src.get("chapter"):
        markers = chapter_formal_markers(src["book"], src["chapter"], limit=10)
        if markers:
            m_items = [
                f'<li class="wiki-marker-item">'
                f'<div><strong>{esc(m["kind"])} {esc(m["number"])}</strong> '
                f'<small>· p. {esc(m["folio"])} (PDF {esc(m["page"])})</small>'
                f'<p class="wiki-marker-excerpt">« {esc(m["excerpt"][:150])} »</p></div>'
                f'<button type="button" class="open-reader-btn open-reader-sm" '
                f'data-read-book="{esc(m["book"])}" data-read-page="{esc(m["page"])}" '
                f'data-read-excerpt="{esc(m["excerpt"][:90])}">Lire p. {esc(m["page"])}</button></li>'
                for m in markers
            ]
            markers_html = (
                f'<details class="wiki-markers-drawer">'
                f'<summary>Repères formels détectés dans le chapitre « {esc(src["chapter"])} » ({len(m_items)})</summary>'
                f'<ul class="wiki-marker-list">{"".join(m_items)}</ul></details>'
            )

    comparisons = [
        e
        for e in edges
        if e["kind"] in ("Comparaison entre ouvrages", "Rapprochement éditorial")
        and NODES[e["origin"]]["source"]["book"] != NODES[e["target"]]["source"]["book"]
    ]
    compare_html = ""
    if comparisons:
        comp_blocks = []
        for e in comparisons:
            pair_keys = sorted((e["origin"], e["target"]), key=lambda k: node_source(k)["year"])
            pair_cards = "".join(
                f'<article class="reading-card"><header><strong>{esc(node_source(k)["title"])}</strong> '
                f'<small>{esc(str(node_source(k)["year"]))} · {esc(node_source(k)["pages"])}</small></header>'
                f'<blockquote lang="en">« {esc(node_source(k)["excerpt"])} »</blockquote></article>'
                for k in pair_keys
            )
            note = f'<p class="wiki-editorial-note"><strong>Lecture éditoriale :</strong> {esc(e["comparison"])}</p>' if e.get("comparison") else ""
            comp_blocks.append(f'<div class="compare-grid">{pair_cards}</div>{note}')
        compare_html = f'<section class="wiki-section"><h3>Évolution entre plusieurs ouvrages</h3>{"".join(comp_blocks)}</section>'

    dossiers_html = ""
    linked_dossiers = _dossiers_for_nodes({key})
    if linked_dossiers:
        d_chips = "".join(f'<span class="wiki-dossier-chip">{esc(title)}</span>' for _, title in linked_dossiers)
        dossiers_html = (
            f'<section class="wiki-section"><h3>Questions associées</h3>'
            f'<div class="wiki-dossier-list">{d_chips}</div></section>'
        )

    return (
        f'<article class="wiki-article" data-concept-key="{esc(key)}">'
        f'<nav class="wiki-breadcrumb" aria-label="Fil d’Ariane">'
        f'<span>Concepts</span> › <span>Arbre déductif</span> › <span style="color:{color};font-weight:600;">{esc(node["domain"])}</span> › <span>{esc(node["title"])}</span></nav>'
        f'<header class="wiki-title-bar"><h2>{esc(node["title"])}</h2>'
        f'<span class="wiki-kind-pill" style="border-color:{color};color:{color};">{esc(node["kind"])}</span></header>'
        f'<div class="wiki-grid">'
        f'<div class="wiki-main">{lead_html}{notation_html}{"".join(rel_sections)}{markers_html}{compare_html}{dossiers_html}</div>'
        f"{infobox_html}"
        f"</div></article>"
    )


WIKI_BRIDGE_JS = """
if (!window.__bungeBridgeInstalled) {
  window.__bungeBridgeInstalled = true;
  const dispatchGradioInput = (selector, value) => {
    const input = document.querySelector(selector + ' textarea, ' + selector + ' input');
    if (!input) return false;
    const proto = input.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
    if (setter) setter.call(input, value);
    else input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  };
  document.addEventListener('click', (e) => {
    const wikiLink = e.target.closest('.wiki-link[data-wiki-concept]');
    if (wikiLink) {
      e.preventDefault();
      const key = wikiLink.getAttribute('data-wiki-concept');
      if (key && dispatchGradioInput('#wiki-bridge', key + '::' + Date.now())) {
        window.scrollTo({ top: 180, behavior: 'smooth' });
      }
      return;
    }
    const readBtn = e.target.closest('.open-reader-btn[data-read-book][data-read-page]');
    if (readBtn) {
      e.preventDefault();
      const book = readBtn.getAttribute('data-read-book') || '';
      const page = readBtn.getAttribute('data-read-page') || '';
      const excerpt = (readBtn.getAttribute('data-read-excerpt') || '').slice(0, 120);
      if (book && page && dispatchGradioInput('#reader-bridge', book + '||' + page + '||' + excerpt + '||' + Date.now())) {
        setTimeout(() => {
          document.querySelector('#book-reader-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 120);
      }
      return;
    }
    const aiTrigger = e.target.closest('#submit-button, #chat-shell .suggestion-row button');
    if (aiTrigger) {
      setTimeout(() => {
        const card = document.querySelector('#ai-answer-card');
        if (card) {
          const rect = card.getBoundingClientRect();
          if (rect.height > 0 && rect.top > window.innerHeight - 160) {
            card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }
        }
      }, 320);
    }
  });
}
"""
