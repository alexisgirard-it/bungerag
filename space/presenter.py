"""Adaptation sure du resultat RAG vers la vue publique.

Le noyau historique renvoie un dictionnaire et le futur contrat peut utiliser
des objets / sections ``output`` et ``meta``. Ce module accepte les deux sans
jamais recopier les champs prives tels que ``contexts`` ou ``question_en``.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping
from pathlib import Path
from urllib.parse import quote

from citations import normalize_groups


MAX_ANSWER_CHARS = 24_000
MAX_EXCERPT_CHARS = 220
MAX_EXCERPT_WORDS = 20
MAX_SOURCES = 12
CITATION_RE = re.compile(r"\[\s*(-?\d+)\s*\]")


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _first(values: Iterable[Any], default: Any = None) -> Any:
    for value in values:
        if value is not None:
            return value
    return default


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return " ".join(str(value).split())


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class SourceView:
    index: int
    title: str
    pages: str
    excerpt: str
    file: str = ""
    pdf_page: int = 0
    edition: str = ""
    voice: str = ""
    edition_label: str = ""

    def public_payload(self) -> dict[str, object]:
        report = {"index": self.index, "title": self.title, "pages": self.pages, "excerpt": self.excerpt}
        if self.edition:
            report["edition_sha256"] = self.edition
        if self.pdf_page:
            report["pdf_page"] = self.pdf_page
        if self.voice:
            report["quoted_author"] = self.voice
        if self.edition_label:
            report["edition_label"] = self.edition_label
        return report


@dataclass(frozen=True)
class AnswerView:
    answer_markdown: str
    sources: tuple[SourceView, ...]
    mode: str
    elapsed_seconds: float
    cached: bool
    abstained: bool
    partial: bool
    citation_status: str
    citation_message: str
    cited_numbers: tuple[int, ...]

    def with_cache_hit(self) -> "AnswerView":
        return replace(self, cached=True, elapsed_seconds=0.0)

    def public_payload(self) -> dict[str, object]:
        """Contrat public en liste blanche : aucun contexte integral."""
        status = "abstained" if self.abstained else "partial" if self.partial else "ok"
        if self.citation_status == "warning" and not self.sources:
            status = "unverified"
        return {
            "schema_version": "1.0",
            "status": status,
            "answer": self.answer_markdown,
            "sources": [source.public_payload() for source in self.sources],
            "meta": {
                "mode": self.mode,
                "elapsed_seconds": round(self.elapsed_seconds, 1),
                "cached": self.cached,
                "citation_validation": self.citation_status,
                "cited_numbers": list(self.cited_numbers),
            },
        }


def _source_view(raw: Any, index: int) -> SourceView:
    title = _text(
        _first((_get(raw, "title"), _get(raw, "titre"), _get(raw, "book"))),
        "Source sans titre",
    )
    pages = _text(
        _first(
            (
                _get(raw, "pages"),
                _get(raw, "page_label"),
                _get(raw, "page"),
            )
        ),
        "pagination non fournie",
    )
    excerpt = _text(
        _first(
            (
                _get(raw, "excerpt"),
                _get(raw, "extrait"),
                _get(raw, "snippet"),
                _get(raw, "quote"),
            )
        )
    )
    excerpt_words = excerpt.split()
    excerpt = " ".join(excerpt_words[:MAX_EXCERPT_WORDS])[:MAX_EXCERPT_CHARS]
    if len(excerpt_words) > MAX_EXCERPT_WORDS:
        excerpt += "…"
    locator = _get(raw, "locator", {})
    name = _get(locator, "file", "")
    physical = _get(locator, "pdf_page", 0)
    edition = _get(locator,"edition","")
    return SourceView(edition=edition if isinstance(edition,str) and re.fullmatch("[0-9a-f]{64}",edition) else "", index=index, title=title[:240], pages=pages[:220], excerpt=excerpt,
                      file=name if isinstance(name,str) and re.fullmatch(r"[a-z0-9-]+\.pdf",name) else "",
                      pdf_page=physical if type(physical) is int and physical>0 else 0,
                      voice=_text(_get(locator,"voice",""))[:140],
                      edition_label=_text(_get(locator,"edition_label",""))[:220])


def _citation_validation(answer: str, source_count: int, abstained: bool) -> tuple[str, str, tuple[int, ...]]:
    cited = tuple(sorted({int(item) for item in CITATION_RE.findall(answer)}))
    if abstained:
        return "not_applicable", "Abstention : aucune citation requise.", cited
    if not answer.strip():
        return "warning", "Aucune reponse exploitable n'a ete produite.", cited
    if source_count == 0:
        return "warning", "La reponse ne comporte aucune source publique.", cited
    if not cited:
        return "warning", "Aucun renvoi [n] n'apparait dans la reponse.", cited
    invalid = tuple(number for number in cited if not 1 <= number <= source_count)
    if invalid:
        labels = ", ".join(f"[{number}]" for number in invalid)
        return "warning", f"Renvoi(s) sans source correspondante : {labels}.", cited
    return (
        "valid",
        "Les renvois [n] correspondent structurellement aux sources affichees.",
        cited,
    )


def present_result(result: Any, elapsed_seconds: float, cached: bool = False) -> AnswerView:
    """Convertit ancien dictionnaire ou futur objet contractuel en vue sure."""
    output = _first((_get(result, "output"), _get(result, "data")), result)
    meta = _first((_get(result, "meta"), _get(result, "metadata")), {})

    raw_answer = _first(
        (
            _get(output, "answer"),
            _get(output, "response"),
            _get(output, "text"),
            _get(result, "answer"),
        ),
        "",
    )
    # Echappe le HTML brut tout en conservant listes, titres et citations Markdown.
    answer = normalize_groups(str(raw_answer or "")[:MAX_ANSWER_CHARS]).replace("<", "&lt;").replace(">", "&gt;")

    raw_sources = _first(
        (
            _get(output, "sources"),
            _get(output, "citations"),
            _get(output, "evidence"),
            _get(result, "sources"),
        ),
        [],
    )
    if isinstance(raw_sources, (str, bytes)) or not isinstance(raw_sources, Iterable):
        raw_sources = []
    sources = tuple(
        _source_view(source, index)
        for index, source in enumerate(list(raw_sources)[:MAX_SOURCES], 1)
    )

    mode = _text(
        _first((_get(meta, "mode"), _get(output, "mode"), _get(result, "mode"))),
        "direct",
    ).lower()
    if mode not in {"direct", "panoramique"}:
        mode = "direct"

    raw_status = _text(
        _first((_get(output, "status"), _get(result, "status"))),
        "",
    ).lower()
    raw_abstained = _first(
        (_get(output, "abstained"), _get(result, "abstained")),
        False,
    )
    # Une sortie rejetée par le validateur de citations est un défaut de
    # présentation/sourcing, pas une abstention intellectuelle du corpus.
    abstention_reason = _text(raw_abstained).lower()
    abstained = abstention_reason in {"pre-generation", "llm", "true", "1"}
    abstained = abstained or raw_status in {"abstained", "absent"}
    abstained = abstained or answer.strip().lower().startswith("absent du corpus")
    partial = bool(
        _first((_get(output, "partial"), _get(result, "partial")), False)
    ) or raw_status == "partial"

    timing = _first(
        (
            _get(meta, "elapsed_seconds"),
            _get(output, "elapsed_seconds"),
            _get(result, "elapsed_seconds"),
        ),
        elapsed_seconds,
    )
    elapsed = _number(timing, elapsed_seconds)
    citation_status, citation_message, cited = _citation_validation(
        answer, len(sources), abstained
    )
    return AnswerView(
        answer_markdown=answer,
        sources=sources,
        mode=mode,
        elapsed_seconds=elapsed,
        cached=cached,
        abstained=abstained,
        partial=partial,
        citation_status=citation_status,
        citation_message=citation_message,
        cited_numbers=cited,
    )


def link_citations(markdown: str, source_count: int) -> str:
    """Transforme uniquement les renvois valides en ancres vers les sources."""
    def replacement(match: re.Match[str]) -> str:
        number = int(match.group(1))
        if not 1 <= number <= source_count:
            return match.group(0)
        return f"[{number}](#source-{number})"

    return CITATION_RE.sub(replacement, normalize_groups(markdown))


def render_status(state: str, elapsed_seconds: float = 0.0, detail: str = "") -> str:
    labels = {
        "ready": ("Prêt", "Une question libre peut prendre environ une minute sur le serveur de démonstration."),
        "working": ("Traitement en cours", "Recherche des passages et rédaction de la réponse."),
        "complete": ("Réponse produite", "La réponse et ses sources sont disponibles."),
        "cached": ("Réponse en cache", "Cette réponse a été retrouvée sans nouveau calcul."),
        "error": ("Requête interrompue", detail or "Aucun résultat n'a été produit."),
    }
    label, message = labels.get(state, labels["ready"])
    elapsed = f"<span class=\"status-time\">{elapsed_seconds:.0f} s</span>" if elapsed_seconds else ""
    return (
        f'<div class="system-status status-{html.escape(state)}" role="status" aria-live="polite">'
        f'<span class="status-dot" aria-hidden="true"></span>'
        f'<span><strong>{html.escape(label)}</strong><small>{html.escape(message)}</small></span>'
        f"{elapsed}</div>"
    )


def render_meta(view: AnswerView) -> str:
    cache_label = "CACHE" if view.cached else "LIVE"
    mode_label = "PANORAMIQUE" if view.mode == "panoramique" else "DIRECT"
    citation_label = {
        "valid": "CITATIONS STRUCTURELLES VALIDES",
        "warning": "CITATIONS À VÉRIFIER",
        "not_applicable": "ABSTENTION",
    }[view.citation_status]
    citation_class = "meta-ok" if view.citation_status == "valid" else "meta-warn"
    return (
        '<div class="answer-meta" aria-label="Métadonnées de la réponse">'
        f'<span>{mode_label}</span><span>{len(view.sources)} SOURCES</span>'
        f'<span>{view.elapsed_seconds:.1f} S</span><span>{cache_label}</span>'
        f'<span class="{citation_class}">{citation_label}</span></div>'
    )


def render_sources(view: AnswerView, local_books: Path | None = None) -> str:
    if not view.sources:
        return '<div class="sources-empty">Aucune source affichée pour cette réponse.</div>'
    cards = []
    for source in view.sources:
        excerpt = html.escape(source.excerpt) or "Extrait court non disponible."
        reader = ""
        if local_books and source.file and source.pdf_page:
            pdf = (local_books / source.file).resolve()
            if pdf.parent == local_books.resolve() and pdf.is_file():
                href = "/gradio_api/file=" + quote(str(pdf)) + "#page=" + str(source.pdf_page)
                reader = f'<a href="{html.escape(href)}" target="_blank" rel="noopener">Ouvrir la page du PDF</a>'
        expanded = (
            " open"
            if source.pdf_page or source.pages.startswith("ch") or " · section ch" in source.pages
            else ""
        )
        voice = f'<small>Auteur cité · {html.escape(source.voice)}</small>' if source.voice else ""
        imprint = f'<p><small>Édition indexée · {html.escape(source.edition_label)}</small></p>' if source.edition_label else ""
        cards.append(
            f'<details class="source-card" id="source-{source.index}"{expanded}>'
            f'<summary><span class="source-number">[{source.index}]</span>'
            f'<span class="source-heading"><strong>{html.escape(source.title)}</strong>'
            f'<small>{html.escape(source.pages)}</small></span>'
            '<span class="source-toggle" aria-hidden="true">+</span></summary>'
            f'{imprint}{voice}<blockquote>« {excerpt} »</blockquote>{reader}</details>'
        )
    return '<div class="source-list">' + "".join(cards) + "</div>"


def render_notice(view: AnswerView) -> str:
    blocks: list[str] = []
    if view.abstained:
        blocks.append(
            '<div class="notice notice-abstention"><strong>Le corpus ne permet pas de repondre.</strong>'
            "<p>Aucun passage suffisamment pertinent n'a ete identifie. "
            "Essayez de reformuler la question.</p></div>"
        )
    elif view.partial:
        blocks.append(
            '<div class="notice notice-partial"><strong>Couverture partielle.</strong>'
            "<p>La reponse distingue ce que les extraits couvrent de ce qu'ils ne permettent pas d'affirmer.</p></div>"
        )
    if view.citation_status == "warning" and not view.abstained:
        blocks.append(
            '<div class="notice notice-validation"><strong>Verification structurelle.</strong>'
            f"<p>{html.escape(view.citation_message)} Cette verification ne mesure pas la verite de la reponse.</p></div>"
        )
    return "".join(blocks)
