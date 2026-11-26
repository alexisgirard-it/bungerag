"""Liens encyclopédiques façon Wikipédia et pages de concepts structurées."""

from __future__ import annotations

import html
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from atlas_graph import DOMAIN_COLORS
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

# Alias français/anglais naturels vers les fiches majeures du référentiel.
CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {
    "systemisme": ("systémisme", "systemisme", "approche systémique", "système concret", "systèmes concrets"),
    "postulat-emergence": ("émergence", "emergence", "propriétés émergentes", "propriété émergente", "émergentiste"),
    "agregat-et-systeme": ("agrégat", "agrégats", "système et agrégat"),
    "ni-holisme-ni-atomisme": ("holisme", "réductionnisme atomiste", "individualisme atomiste", "atomisme"),
    "materialisme": ("matérialisme", "materialisme", "matérialisme scientifique"),
    "cadre-emergentiste": ("matérialisme émergentiste", "emergentist materialism"),
    "realisme": ("réalisme scientifique", "realisme scientifique", "réalisme"),
    "biosystemisme": ("biosystémisme", "biosystemisme"),
    "psychon": ("psychon", "psychons"),
    "identite": ("identité psychoneurale", "théorie de l’identité"),
    "determinisme-causal": ("déterminisme causal", "causalité", "causalite", "principe de causalité"),
    "fatalisme": ("fatalisme", "fataliste"),
    "mecanisme": ("explication mécanismique", "mécanisme explicatif", "mécanismes"),
    "snell": ("loi de Snell", "réfraction"),
    "bonheur": ("bonheur complet", "bonheur"),
    "bien-etre": ("bien-être", "bien-etre"),
    "besoin": ("besoins primaires", "besoin primaire"),
    "droit": ("droits moraux", "droit moral"),
    "devoir": ("devoir moral", "obligation morale"),
    "existence-conceptuelle": ("existence conceptuelle", "construits", "construit"),
    "modele": ("modèle factuel", "modele factuel", "modèle théorique"),
    "couple-signification": ("couple sens-référence", "signification sémantique"),
    "synonymie": ("synonymie", "synonymes"),
    "intension": ("intension", "sens et référence"),
    "verite": ("vérité partielle", "verite partielle", "vérité factuelle"),
    "verite-efficacite": ("efficacité technique", "règle technologique", "règles technologiques"),
    "monde": ("unicité du monde", "supremum"),
    "espace": ("espace-temps", "théorie relationnelle de l’espace"),
    "changement": ("changement et choses", "espace d’états"),
    "chose": ("chose et propriétés", "propriétés d’une chose"),
    "conjecture": ("conjecture", "hypothèse profonde"),
    "theorie-systeme": ("système hypothético-déductif", "théorie scientifique"),
    "testabilite-reelle": ("vérifiabilité", "mise à l’épreuve"),
    "psychologie": ("psychologie scientifique", "philosophie de l’esprit"),
    "societe": ("système social", "sociétés humaines"),
    "metaethique": ("métaéthique", "metaethique"),
    "axiologie": ("axiologie", "théorie des valeurs"),
    "survie": ("avenir viable", "survie humaine"),
}


@lru_cache(maxsize=1)
def _compiled_glossary() -> tuple[re.Pattern[str], dict[str, str]]:
    """Construit un automate regex insensible à la casse (termes les plus longs en premier)."""
    term_to_key: dict[str, str] = {}
    for key, aliases in CONCEPT_ALIASES.items():
        if key not in NODES:
            continue
        for alias in aliases:
            clean = alias.strip()
            if len(clean) >= 5:
                term_to_key.setdefault(clean.casefold(), key)
    for key, node in NODES.items():
        title = node["title"].strip()
        if 5 <= len(title) <= 44 and "·" not in title:
            term_to_key.setdefault(title.casefold(), key)
    ordered = sorted(term_to_key.keys(), key=len, reverse=True)
    if not ordered:
        return re.compile(r"(?!x)x"), {}
    pattern = re.compile(
        r"(?<!\w)(" + "|".join(re.escape(t) for t in ordered) + r")(?!\w)",
        re.IGNORECASE,
    )
    return pattern, term_to_key


_TAG_SPLIT_RE = re.compile(r"(<[^>]+>)")
_SKIP_OPEN = {"a", "code", "pre", "script", "style", "summary", "h1", "button"}


def annotate_concepts(html_text: str, *, exclude_key: str | None = None) -> str:
    """Souligne en bleu façon Wikipédia les définitions/concepts Bunge reconnus dans du HTML."""
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
            key = lookup.get(text.casefold())
            if not key or key == exclude_key or key in linked_once or key not in NODES:
                return text
            linked_once.add(key)
            title = NODES[key]["title"]
            domain = NODES[key]["domain"]
            return (
                f'<a href="#wiki-{esc(key)}" class="wiki-link" '
                f'data-wiki-concept="{esc(key)}" '
                f'title="Ouvrir la fiche Wikipédia : {esc(title)} ({esc(domain)})">'
                f"{text}</a>"
            )

        out.append(pattern.sub(_replace, part))
    return "".join(out)


def _group_relation_bucket(kind: str) -> str:
    k = fold(kind)
    if any(w in k for w in ("definition", "postulat", "axiome", "principe", "distinction")):
        return "Définitions & fondements"
    if any(w in k for w in ("theoreme", "corollaire", "norme", "regle")):
        return "Théorèmes, corollaires & normes"
    if any(w in k for w in ("exemple", "critique", "auteur", "objection", "comparaison")):
        return "Exemples, critiques & auteurs cités"
    return "Thèses & propositions liées"


def _dossiers_for_node(key: str) -> list[tuple[str, str]]:
    from workshop import DOSSIERS

    found: list[tuple[str, str]] = []
    for dkey, builder in DOSSIERS.items():
        d = builder()
        if any(s.get("id") == key for s in d.get("steps", ())):
            found.append((dkey, d["title"]))
    return found


def render_concept_wiki(key: str, local: Path | None = None) -> str:
    """Rend une véritable page encyclopédique façon Wikipédia pour un concept de Bunge."""
    if key not in NODES:
        return "<p>Choisissez une notion dans l’Atlas pour consulter sa page encyclopédique.</p>"

    node = NODES[key]
    color = DOMAIN_COLORS.get(node["domain"], "#2563eb")
    src = node_source(key)
    edges = neighbours(key)
    notation = node.get("notation")
    voice = src.get("voice") if src.get("voice") not in (None, "Bunge") else ""

    # 1. Infobox Wikipédia (colonne droite)
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
        f'<div class="wiki-infobox-actions">'
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

    # 2. Corps principal : synthèse claire + passage de référence avec son contexte de page
    lead_text = annotate_concepts(esc(node["text"]), exclude_key=key)
    voice_note = (
        f'<p class="wiki-voice-banner"><strong>Voix citée :</strong> {esc(voice)} (exposé par Bunge, non attribué à Bunge).</p>'
        if voice
        else ""
    )
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
        quote_body = f"{prefix}{ctx_html}{suffix}"
    else:
        quote_body = f"« {esc(raw_quote)} »"

    lead_html = (
        f'<div class="wiki-lead">'
        f'<p class="wiki-summary">{lead_text}</p>'
        f"{voice_note}"
        f'<blockquote class="wiki-quote" lang="en">{quote_body}'
        f'<footer>— {esc(src["authors"])}, <em>{esc(src["title"])}</em> ({esc(str(src["year"]))}), {esc(src["pages"])}'
        + (f' · {esc(src["edition_label"])}' if src.get("edition_label") else "")
        + "</footer></blockquote></div>"
    )

    # 3. Section Notation formelle
    notation_html = ""
    if notation:
        notation_html = (
            '<section class="wiki-section"><h3>Notation formelle</h3>'
            f'<div class="symbol-formula-box formula">{esc(notation["formula"])}</div>'
            f'<p>{annotate_concepts(esc(notation["gloss"]), exclude_key=key)}</p>'
            f'<small class="wiki-muted">{esc(notation["status"])}</small></section>'
        )

    # 4. Propositions liées groupées par rôle (sens grammatical origin -> target + résumé de chaque notion liée)
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
        # Phrase toujours lue dans l'ordre grammatical exact (origine -> verbe -> cible).
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

    rel_sections = []
    for heading, items in buckets.items():
        if items:
            rel_sections.append(
                f'<section class="wiki-section"><h3>{esc(heading)} ({len(items)})</h3>'
                f'<ul class="wiki-rel-list">{"".join(items)}</ul></section>'
            )

    # 5. Repères formels détectés dans le même chapitre (repliés pour ne pas encombrer la fiche curatée)
    markers_html = ""
    if src.get("chapter"):
        markers = chapter_formal_markers(src["book"], src["chapter"], limit=10)
        if markers:
            m_items = []
            for m in markers:
                m_items.append(
                    f'<li class="wiki-marker-item">'
                    f'<div><strong>{esc(m["kind"])} {esc(m["number"])}</strong> '
                    f'<small>· p. {esc(m["folio"])} (PDF {esc(m["page"])})</small>'
                    f'<p class="wiki-marker-excerpt">« {esc(m["excerpt"][:150])} »</p></div>'
                    f'<button type="button" class="open-reader-btn open-reader-sm" '
                    f'data-read-book="{esc(m["book"])}" data-read-page="{esc(m["page"])}" '
                    f'data-read-excerpt="{esc(m["excerpt"][:90])}">Lire p. {esc(m["page"])}</button></li>'
                )
            markers_html = (
                f'<details class="wiki-markers-drawer">'
                f'<summary>Repères formels détectés dans le chapitre « {esc(src["chapter"])} » ({len(m_items)})</summary>'
                f'<ul class="wiki-marker-list">{"".join(m_items)}</ul></details>'
            )

    # 6. Comparaisons entre ouvrages
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

    # 7. Dossiers d'Atelier associés
    dossiers_html = ""
    linked_dossiers = _dossiers_for_node(key)
    if linked_dossiers:
        d_chips = "".join(
            f'<span class="wiki-dossier-chip">{esc(title)}</span>'
            for _, title in linked_dossiers
        )
        dossiers_html = (
            f'<section class="wiki-section"><h3>Dossiers d’Atelier associés</h3>'
            f'<div class="wiki-dossier-list">{d_chips}</div></section>'
        )

    return (
        f'<article class="wiki-article" data-concept-key="{esc(key)}">'
        f'<nav class="wiki-breadcrumb" aria-label="Fil d’Ariane">'
        f'<span>Atlas</span> › <span style="color:{color};font-weight:600;">{esc(node["domain"])}</span> › <span>{esc(node["title"])}</span></nav>'
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
    }
  });
}
"""
