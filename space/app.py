"""BungeRAG — edition critique numerique, demo publique Hugging Face.

La vue publique reste une couche mince autour du noyau : elle n'expose jamais
les contextes integraux, borne les ressources et distingue clairement
abstention intellectuelle, quota applicatif et incident fournisseur.
"""

from __future__ import annotations

import html
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import gradio as gr

from presenter import (
    AnswerView,
    link_citations,
    present_result,
    render_meta,
    render_notice,
    render_sources,
    render_status,
)
from runtime import BoundedLRUCache, QuotaExceeded, QuotaGuard, classify_exception
from theme import build_theme


APP_DIR = Path(__file__).resolve().parent
# En local, app.py vit dans space/. Sur HF, son contenu est publie a la racine.
RUNTIME_ROOT = APP_DIR if (APP_DIR / "src").exists() else APP_DIR.parent
SRC_DIR = RUNTIME_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

os.environ.setdefault("RAG_PROFILE", "public_v1")


def env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


MAX_QUESTION_CHARS = env_int("MAX_QUESTION_CHARS", 800, 80, 2_000)
DAILY_LIMIT = env_int("DAILY_LIMIT", 80, 1, 10_000)
CLIENT_LIMIT = env_int("IP_LIMIT", 10, 1, 1_000)
CACHE_SIZE = env_int("CACHE_SIZE", 96, 4, 1_000)
QUEUE_SIZE = env_int("QUEUE_SIZE", 12, 1, 200)
POLL_SECONDS = 1.5

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
LOGGER = logging.getLogger("bungerag.space")

INDEX = RUNTIME_ROOT / "index" / "lancedb"
if not INDEX.exists():
    from huggingface_hub import snapshot_download

    index_revision = os.environ.get("INDEX_REVISION", "").strip()
    if not index_revision:
        raise RuntimeError("INDEX_REVISION est requis pour télécharger l'index privé")
    LOGGER.info("index_download_start")
    snapshot_download(
        "alexisgirard/bungerag-index",
        repo_type="dataset",
        local_dir=RUNTIME_ROOT / "index",
        token=os.environ["HF_TOKEN"],
        revision=index_revision,
    )
    LOGGER.info("index_download_complete")

from rag import ask_smart  # noqa: E402


# Un seul calcul lourd : deux rerankings simultanes degradent le CPU gratuit.
POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bungerag")
CACHE: BoundedLRUCache[str, AnswerView] = BoundedLRUCache(max_size=CACHE_SIZE)
QUOTAS = QuotaGuard(daily_limit=DAILY_LIMIT, per_client_limit=CLIENT_LIMIT)


MASTHEAD = """
<header id="masthead">
  <div class="masthead-mark"><strong>BUNGERAG</strong><span>Lecture assistée de Mario Bunge</span></div>
  <div class="masthead-status">En ligne</div>
</header>
"""

HERO = """
<section id="hero" aria-labelledby="hero-title">
  <div class="hero-kicker">Une question · une réponse · ses sources</div>
  <h1 id="hero-title">Questionner les textes.<br>Remonter aux sources.</h1>
  <p>Posez votre question en français. BungeRAG répond à partir des textes de Mario Bunge
  et affiche les passages utilisés — ou indique simplement que le corpus ne permet pas de répondre.</p>
</section>
"""

QUESTION_HEADING = """
<div class="panel-title"><span class="panel-index">Votre question</span>
<p>Une notion ou une question précise fonctionne généralement mieux.</p></div>
"""

ANSWER_HEADING = """
<div class="answer-heading"><span class="panel-index">Réponse</span>
<p>Les renvois [n] ouvrent les sources correspondantes.</p></div>
"""

APPARATUS_HEADING = """
<div class="apparatus-heading"><strong>Sources citées</strong>
<p>Ouvrez une source pour lire le court extrait associé.</p></div>
"""

FOOTER = """
<footer id="custom-footer"><p>Lecture assistée, pas imitation. Les œuvres restent la propriété de leurs ayants droit.</p>
<nav aria-label="En savoir plus">
  <a href="https://alexis-girard-ai-portfolio.alexis-girard709451.chatgpt.site/work/bungerag" target="_blank" rel="noopener noreferrer">ÉTUDE DE CAS ↗</a>
  <a href="https://github.com/alexisgirard-it/bungerag" target="_blank" rel="noopener noreferrer">CODE ↗</a>
</nav></footer>
"""

EXAMPLES = (
    "Qu'est-ce que l'émergence pour Bunge ?",
    "Quelle différence entre causalité et déterminisme ?",
    "Pourquoi Bunge critique-t-il la psychanalyse ?",
    "Que dit Bunge à propos du Bitcoin ?",
)

EMPTY_ANSWER = """> **Aucune réponse ouverte.**

Posez une question ou choisissez un exemple."""


def normalize_question(question: object) -> tuple[str, str]:
    clean = " ".join(str(question or "").split())
    return clean, clean.casefold()


def client_id(request: gr.Request | None) -> str:
    client = getattr(request, "client", None)
    host = getattr(client, "host", "unknown")
    return str(host or "unknown")[:128]


def system_message(kind: str, title: str, message: str) -> str:
    return (
        f'<div class="system-message {html.escape(kind)}" role="alert">'
        f"<strong>{html.escape(title)}</strong><br>{html.escape(message)}</div>"
    )


def processing_payload(elapsed: float) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "status": "processing",
        "answer": "",
        "sources": [],
        "meta": {"elapsed_seconds": round(elapsed, 1), "cached": False},
    }


def error_outputs(kind: str, title: str, message: str, request_id: str = ""):
    public = {
        "schema_version": "1.0",
        "status": f"{kind}_error" if kind != "quota" else "quota_rejected",
        "answer": "",
        "sources": [],
        "meta": {"request_id": request_id} if request_id else {},
    }
    return (
        public,
        render_status("error", detail=message),
        "",
        "",
        '<div class="sources-empty">Aucune source : aucun résultat n’a été produit.</div>',
        system_message(kind, title, message),
    )


def view_outputs(view: AnswerView):
    status_name = "cached" if view.cached else "complete"
    answer = link_citations(view.answer_markdown, len(view.sources))
    return (
        view.public_payload(),
        render_status(status_name, view.elapsed_seconds),
        render_meta(view),
        answer,
        render_sources(view),
        render_notice(view),
    )


def answer_question(question: str, request: gr.Request):
    """Endpoint public generator : progres honnete puis contrat public filtre."""
    request_id = uuid4().hex[:10]
    clean_question, cache_key = normalize_question(question)
    if len(clean_question) < 8:
        yield error_outputs(
            "input",
            "Question trop courte",
            "Formulez une question complète sur la philosophie de Mario Bunge.",
            request_id,
        )
        return
    if len(clean_question) > MAX_QUESTION_CHARS:
        yield error_outputs(
            "input",
            "Question trop longue",
            f"La limite est de {MAX_QUESTION_CHARS} caractères pour cette démonstration.",
            request_id,
        )
        return

    cached_view = CACHE.get(cache_key)
    if cached_view is not None:
        LOGGER.info("cache_hit request_id=%s", request_id)
        yield view_outputs(cached_view.with_cache_hit())
        return

    reservation = None
    try:
        reservation = QUOTAS.reserve(client_id(request))
    except QuotaExceeded as exc:
        if exc.scope == "client":
            title = "Limite par visiteur atteinte"
            message = f"Cette démonstration autorise {CLIENT_LIMIT} questions libres par jour et par visiteur."
        else:
            title = "Quota public du jour atteint"
            message = "Le quota gratuit est partagé entre tous les visiteurs. Revenez demain."
        LOGGER.warning("quota_rejected request_id=%s scope=%s", request_id, exc.scope)
        yield error_outputs("quota", title, message, request_id)
        return

    started = time.monotonic()
    LOGGER.info("request_started request_id=%s chars=%s", request_id, len(clean_question))
    future = POOL.submit(ask_smart, clean_question)
    while not future.done():
        elapsed = time.monotonic() - started
        yield (
            processing_payload(elapsed),
            render_status("working", elapsed),
            '<div class="answer-meta"><span>PIPELINE ACTIF</span><span>CPU PUBLIC</span></div>',
            "",
            '<div class="sources-empty">Les sources apparaîtront avec la réponse complète.</div>',
            "",
        )
        time.sleep(POLL_SECONDS)

    try:
        raw_result = future.result()
        elapsed = time.monotonic() - started
        view = present_result(raw_result, elapsed_seconds=elapsed, cached=False)
        CACHE.put(cache_key, view)
        if not QUOTAS.commit(reservation):
            LOGGER.warning("quota_commit_missed request_id=%s", request_id)
        LOGGER.info(
            "request_complete request_id=%s elapsed=%.1f mode=%s sources=%s citations=%s",
            request_id,
            elapsed,
            view.mode,
            len(view.sources),
            view.citation_status,
        )
        yield view_outputs(view)
    except Exception as exc:  # le detail reste uniquement dans les logs serveur
        QUOTAS.release(reservation)
        kind = classify_exception(exc)
        LOGGER.exception("request_failed request_id=%s kind=%s", request_id, kind)
        if kind == "provider":
            yield error_outputs(
                "provider",
                "Fournisseur momentanément indisponible",
                "La recherche n'a produit aucune réponse. Réessayez plus tard ou choisissez une question déjà en cache.",
                request_id,
            )
        else:
            yield error_outputs(
                "internal",
                "Incident interne enregistré",
                "Aucun résultat n'a été exposé. Vous pouvez réessayer dans quelques instants.",
                request_id,
            )


CSS = (APP_DIR / "styles.css").read_text(encoding="utf-8")
THEME = build_theme()

with gr.Blocks(
    title="BungeRAG — édition critique numérique",
    fill_width=True,
) as demo:
    with gr.Column(elem_id="page-shell"):
        gr.HTML(MASTHEAD)
        gr.HTML(HERO)

        with gr.Column(elem_id="chat-shell"):
            with gr.Column(elem_id="question-panel"):
                gr.HTML(QUESTION_HEADING)
                question = gr.Textbox(
                    label="Question à BungeRAG",
                    placeholder="Par exemple : qu'est-ce que le systémisme ?",
                    lines=3,
                    max_lines=6,
                    elem_id="question-box",
                )
                gr.HTML(
                    f'<p class="input-note">8 à {MAX_QUESTION_CHARS} caractères · '
                    "ne saisissez aucune donnée personnelle.</p>"
                )
                submit_button = gr.Button(
                    "Envoyer la question",
                    variant="primary",
                    elem_id="submit-button",
                )
                gr.HTML('<p class="example-heading">Essayer une question</p>')
                example_buttons = []
                with gr.Row(elem_id="example-buttons"):
                    for example in EXAMPLES:
                        example_buttons.append(
                            gr.Button(example, variant="secondary", elem_classes=["example-chip"])
                        )

            with gr.Column(elem_id="answer-panel"):
                gr.HTML(ANSWER_HEADING)
                status_output = gr.HTML(render_status("ready"), elem_id="status-output")
                meta_output = gr.HTML("", elem_id="meta-output")
                answer_output = gr.Markdown(EMPTY_ANSWER, elem_id="answer-copy")
                notice_output = gr.HTML("", elem_id="notice-output")
                gr.HTML(APPARATUS_HEADING)
                sources_output = gr.HTML(
                    '<div class="sources-empty">Les sources apparaîtront ici.</div>',
                    elem_id="sources-output",
                )
                # Premier output de /answer : contrat JSON public, jamais les contexts.
                api_payload = gr.JSON(value=None, visible=False)

        gr.HTML(FOOTER)

    outputs = [
        api_payload,
        status_output,
        meta_output,
        answer_output,
        sources_output,
        notice_output,
    ]
    click_event = submit_button.click(
        answer_question,
        inputs=question,
        outputs=outputs,
        api_name="answer",
        scroll_to_output=True,
        concurrency_limit=1,
        concurrency_id="rag",
    )
    question.submit(
        answer_question,
        inputs=question,
        outputs=outputs,
        api_name=False,
        scroll_to_output=True,
        concurrency_limit=1,
        concurrency_id="rag",
    )
    for button, example in zip(example_buttons, EXAMPLES):
        button.click(
            lambda value=example: value,
            outputs=question,
            api_name=False,
            queue=False,
        )

demo.queue(max_size=QUEUE_SIZE, default_concurrency_limit=1)

if __name__ == "__main__":
    demo.launch(theme=THEME, css=CSS)
