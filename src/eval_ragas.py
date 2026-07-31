"""Harnais d'évaluation fingerprinté de BungeRAG.

Chaque exécution vit dans ``eval/cache/runs/<run_id>/`` avec sa configuration,
le hash du jeu de questions, du prompt et du code du pipeline. Un cache créé
par une autre configuration ne peut donc plus être réutilisé silencieusement.

Usage :
  .venv/bin/python src/eval_ragas.py --answers
  .venv/bin/python src/eval_ragas.py --judge
  .venv/bin/python src/eval_ragas.py --report
  .venv/bin/python src/eval_ragas.py --status

Le profil évalué est ``public_v1`` par défaut. Une expérience doit annoncer
explicitement ``EVAL_PROFILE=research_40x6`` ou un autre profil versionné.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "eval" / "cache"
QUESTIONS_PATH = ROOT / "eval" / "questions-eval.jsonl"
sys.path.insert(0, str(ROOT / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from config import get_config  # noqa: E402
from eval_run import is_strict_abstention, prepare_run  # noqa: E402
from rag import SYSTEM  # noqa: E402


QUESTIONS = [json.loads(line) for line in QUESTIONS_PATH.open()]
CONFIG = get_config(os.environ.get("EVAL_PROFILE", "public_v1"))


def backend_identity(backend: str) -> dict:
    if backend == "gemini":
        from generate import GEMINI_MODELS

        return {"backend": backend, "models": list(GEMINI_MODELS)}
    if backend == "ollama":
        return {
            "backend": backend,
            "model": os.environ.get("OLLAMA_MODEL", "qwen3.5:9b"),
        }
    if backend == "cerebras":
        return {
            "backend": backend,
            "model": os.environ.get("CEREBRAS_MODEL", "gpt-oss-120b"),
        }
    return {"backend": backend, "model": "unknown"}


RUNTIME_IDENTITY = {
    "pipeline_entrypoint": "ask_smart",
    "generation": backend_identity(CONFIG.generation_backend),
    "translation": backend_identity(CONFIG.translator_backend),
    "routing": backend_identity(CONFIG.router_backend),
    "judge": {
        "provider": "cerebras",
        "model": os.environ.get("CEREBRAS_MODEL", "gpt-oss-120b"),
        "max_tokens": 16000,
    },
    "evaluation": {
        "ragas_version": importlib.metadata.version("ragas"),
        "metrics": ["faithfulness", "context_precision", "context_recall"],
    },
}
RUN_DIR, RUN_METADATA = prepare_run(
    root=ROOT,
    cache_root=CACHE,
    config=CONFIG,
    questions_path=QUESTIONS_PATH,
    system_prompt=SYSTEM,
    index_manifest_path=ROOT / "index" / f"manifest-{CONFIG.table}.json",
    runtime_identity=RUNTIME_IDENTITY,
)


def load(name):
    path = RUN_DIR / name
    return json.loads(path.read_text()) if path.exists() else {}


def save(name, value):
    path = RUN_DIR / name
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False))
    temporary.replace(path)


def generation_model():
    import generate

    if CONFIG.generation_backend == "gemini":
        return generate.GEMINI_LAST_MODEL
    if CONFIG.generation_backend == "ollama":
        return os.environ.get("OLLAMA_MODEL", "qwen3.5:9b")
    if CONFIG.generation_backend == "cerebras":
        return os.environ.get("CEREBRAS_MODEL", "gpt-oss-120b")
    return None


def run_answers():
    from rag import ask_smart

    answers = load("answers.json")
    started = time.time()
    for question in QUESTIONS:
        key = str(question["id"])
        if key in answers:
            continue
        result = ask_smart(question["question"], config=CONFIG)
        answers[key] = {
            "answer": result["answer"],
            "contexts": result["contexts"],
            "abstained": result["abstained"],
            "top_score": result["top_score"],
            "question_en": result["question_en"],
            "mode": result["mode"],
            "sous_questions": result["sous_questions"],
            "citation_validation": result["citation_validation"],
            "config_id": result["config_id"],
            "generation_backend": CONFIG.generation_backend,
            "generation_model": generation_model(),
            "timings": result["timings"],
        }
        save("answers.json", answers)
        state = "ABSTENTION" if result["abstained"] else "réponse"
        print(
            f"  q{question['id']:02d} [{question['type']}] "
            f"{state:10} {result['mode']:11} ({time.time() - started:.0f}s)",
            flush=True,
        )
    print(f"étage réponses terminé : {len(answers)}/{len(QUESTIONS)}")


async def run_judge():
    from openai import AsyncOpenAI
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (
        ContextPrecisionWithoutReference,
        ContextRecall,
        Faithfulness,
    )

    client = AsyncOpenAI(
        base_url="https://api.cerebras.ai/v1",
        api_key=os.environ["CEREBRAS_API_KEY"],
        max_retries=10,
        timeout=180,
    )
    llm = llm_factory(
        os.environ.get("CEREBRAS_MODEL", "gpt-oss-120b"),
        provider="openai",
        client=client,
        max_tokens=16000,
    )
    metrics = {
        "faithfulness": Faithfulness(llm=llm),
        "context_precision": ContextPrecisionWithoutReference(llm=llm),
        "context_recall": ContextRecall(llm=llm),
    }
    answers = load("answers.json")
    scores = load("scores.json")
    started = time.time()

    missing_answers = [
        question["id"] for question in QUESTIONS
        if str(question["id"]) not in answers
    ]
    if missing_answers:
        raise RuntimeError(
            "réponses manquantes avant jugement : "
            + ", ".join(f"q{value:02d}" for value in missing_answers)
        )

    for question in QUESTIONS:
        if question["type"] != "contenu":
            continue
        key = str(question["id"])
        answer = answers[key]
        if answer["abstained"]:
            continue
        scores.setdefault(key, {})
        for name, metric in metrics.items():
            if scores[key].get(name) is not None:
                continue
            kwargs = {
                "user_input": question["question"],
                "retrieved_contexts": answer["contexts"],
            }
            if name == "context_recall":
                kwargs["reference"] = question["reference"]
            else:
                kwargs["response"] = answer["answer"]
            for attempt in range(3):
                try:
                    result = await metric.ascore(**kwargs)
                    scores[key][name] = result.value
                    break
                except Exception as exc:
                    if attempt == 2:
                        scores[key][name] = None
                        print(
                            f"  q{question['id']:02d} {name} ÉCHEC : "
                            f"{str(exc)[:80]}",
                            flush=True,
                        )
                    else:
                        await asyncio.sleep(60 * (attempt + 1))
            save("scores.json", scores)
        values = {
            name: (f"{value:.2f}" if value is not None else "err")
            for name, value in scores[key].items()
        }
        print(
            f"  q{question['id']:02d} {values} ({time.time() - started:.0f}s)",
            flush=True,
        )
    current = status()
    if current["notes"] != current["notes_expected"]:
        raise RuntimeError(
            "jugement incomplet : "
            f"{current['notes']}/{current['notes_expected']} notes"
        )
    print("étage jugement terminé et complet")


def status():
    answers = load("answers.json")
    scores = load("scores.json")
    content = [item for item in QUESTIONS if item["type"] == "contenu"]
    judgable = [
        item for item in content
        if str(item["id"]) in answers
        and not answers[str(item["id"])].get("abstained")
    ]
    expected_notes = len(judgable) * 3
    notes = sum(
        score.get(metric) is not None
        for score in scores.values()
        for metric in ("faithfulness", "context_precision", "context_recall")
    )
    payload = {
        "run_id": RUN_METADATA["run_id"],
        "config_id": CONFIG.config_id,
        "profile": CONFIG.name,
        "answers": len(answers),
        "answers_expected": len(QUESTIONS),
        "notes": notes,
        "notes_expected": expected_notes,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return payload


def report():
    answers = load("answers.json")
    scores = load("scores.json")
    content = [question for question in QUESTIONS if question["type"] == "contenu"]
    traps = [question for question in QUESTIONS if question["type"] == "piege"]

    print("=== BungeRAG — harnais d'évaluation fingerprinté ===")
    print(
        f"run {RUN_METADATA['run_id']} · profil {CONFIG.name} · "
        f"config {CONFIG.config_id} · commit {RUN_METADATA['git_commit'][:12]}\n"
    )
    for name in ("faithfulness", "context_precision", "context_recall"):
        values = [
            scores[str(question["id"])][name]
            for question in content
            if str(question["id"]) in scores
            and scores[str(question["id"])].get(name) is not None
        ]
        if values:
            low = sum(value < 0.7 for value in values)
            print(
                f"{name:21} {sum(values) / len(values):.3f} "
                f"(n={len(values)}, {low} sous 0,70)"
            )

    trap_answers = [answers.get(str(question["id"])) for question in traps]
    answered_traps = [item for item in trap_answers if item is not None]
    correct_abstentions = sum(
        is_strict_abstention(item.get("abstained")) for item in answered_traps
    )
    print(
        f"{'abstention pièges':21} {correct_abstentions}/{len(answered_traps)} "
        f"(attendu {len(traps)})"
    )
    content_answers = [
        answers.get(str(question["id"])) for question in content
        if answers.get(str(question["id"])) is not None
    ]
    valid_citations = sum(
        item["citation_validation"]["valid"] for item in content_answers
    )
    print(f"{'citations structurelles':21} {valid_citations}/{len(content_answers)}")
    false_abstentions = [
        question["id"] for question in content
        if is_strict_abstention(
            answers.get(str(question["id"]), {}).get("abstained")
        )
    ]
    if false_abstentions:
        print("abstentions contenu : " + ", ".join(
            f"q{value:02d}" for value in false_abstentions
        ))
    rejected_outputs = [
        question["id"] for question in QUESTIONS
        if answers.get(str(question["id"]), {}).get("abstained")
        and not is_strict_abstention(
            answers[str(question["id"])].get("abstained")
        )
    ]
    if rejected_outputs:
        print("sorties rejetées par garde-fou : " + ", ".join(
            f"q{value:02d}" for value in rejected_outputs
        ))


if __name__ == "__main__":
    if "--answers" in sys.argv:
        run_answers()
    elif "--judge" in sys.argv:
        asyncio.run(run_judge())
    elif "--status" in sys.argv:
        status()
    else:
        report()
