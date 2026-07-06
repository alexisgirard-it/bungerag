"""LE harnais d'eval BungeRAG - phase 6, le differenciateur du projet.

Deux etages, chacun avec cache disque (resume-safe : relancable apres
crash/quota sans rien perdre) :

  Etage A (--answers) : fait repondre le pipeline complet aux 40 questions
    -> eval/cache/answers.json   (30 contenu + 10 pieges)
  Etage B (--judge)   : fait noter les reponses de contenu par le juge
    Cerebras gpt-oss-120b via RAGAS :
      faithfulness       la reponse colle-t-elle aux extraits ? (anti-hallucination)
      context_precision  les extraits remontes sont-ils pertinents ? (sans reference)
      context_recall     les extraits couvrent-ils la reponse de reference ?
    -> eval/cache/ragas-scores.json
  Rapport (--report) : moyennes, abstention sur pieges, pires questions.

Juge != generateur (Cerebras note, Gemini repond) : pas de biais
d'auto-preference, et le quota Gemini reste intact.

Usage : .venv/bin/python src/eval_ragas.py --answers|--judge|--report
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "eval" / "cache"
sys.path.insert(0, str(ROOT / "src"))

QUESTIONS = [json.loads(l) for l in open(ROOT / "eval" / "questions-eval.jsonl")]

def load(name):
    p = CACHE / name
    return json.loads(p.read_text()) if p.exists() else {}

def save(name, obj):
    CACHE.mkdir(exist_ok=True)
    (CACHE / name).write_text(json.dumps(obj, ensure_ascii=False))

# ---------------------------------------------------------------- etage A

def run_answers():
    from rag import ask
    answers = load("answers.json")
    t0 = time.time()
    for q in QUESTIONS:
        key = str(q["id"])
        if key in answers:
            continue
        r = ask(q["question"])
        import generate as gen
        answers[key] = {"answer": r["answer"], "contexts": r["contexts"],
                        "abstained": r["abstained"], "top_score": r["top_score"],
                        "question_en": r["question_en"], "model": gen.GEMINI_LAST_MODEL}
        save("answers.json", answers)
        print(f"  q{q['id']:02d} [{q['type']}] "
              f"{'ABSTENTION' if r['abstained'] else 'reponse':10} "
              f"({time.time()-t0:.0f}s)", flush=True)
    print(f"etage A termine : {len(answers)}/40")

# ---------------------------------------------------------------- etage B

async def run_judge():
    from openai import AsyncOpenAI
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (ContextPrecisionWithoutReference,
                                           ContextRecall, Faithfulness)
    client = AsyncOpenAI(base_url="https://api.cerebras.ai/v1",
                         api_key=os.environ["CEREBRAS_API_KEY"],
                         max_retries=10, timeout=180)
    # gpt-oss-120b "raisonne" : ses tokens de reflexion comptent dans la
    # sortie -> plafond large, sinon faithfulness (longue liste de verdicts)
    # sort tronquee ("max_tokens length limit")
    llm = llm_factory(os.environ.get("CEREBRAS_MODEL", "gpt-oss-120b"),
                      provider="openai", client=client, max_tokens=16000)
    metrics = {
        "faithfulness": Faithfulness(llm=llm),
        "context_precision": ContextPrecisionWithoutReference(llm=llm),
        "context_recall": ContextRecall(llm=llm),
    }
    answers = load("answers.json")
    scores = load("ragas-scores.json")
    t0 = time.time()
    for q in QUESTIONS:
        if q["type"] != "contenu":
            continue
        key = str(q["id"])
        a = answers[key]
        if a["abstained"]:  # abstention sur question de contenu = echec note a part
            continue
        scores.setdefault(key, {})
        for name, metric in metrics.items():
            if scores[key].get(name) is not None:  # None = echec passe, on retente
                continue
            kwargs = {"user_input": q["question"],
                      "retrieved_contexts": a["contexts"]}
            if name == "context_recall":
                kwargs["reference"] = q["reference"]
            else:
                kwargs["response"] = a["answer"]
            for attempt in range(3):
                try:
                    r = await metric.ascore(**kwargs)
                    scores[key][name] = r.value
                    break
                except Exception as e:
                    if attempt == 2:
                        scores[key][name] = None
                        print(f"  q{q['id']:02d} {name} ECHEC : {str(e)[:80]}", flush=True)
                    else:
                        await asyncio.sleep(60 * (attempt + 1))
            save("ragas-scores.json", scores)
        vals = {k: (f"{v:.2f}" if v is not None else "err")
                for k, v in scores[key].items()}
        print(f"  q{q['id']:02d} {vals} ({time.time()-t0:.0f}s)", flush=True)
    print("etage B termine")

# ---------------------------------------------------------------- rapport

def report():
    answers = load("answers.json")
    scores = load("ragas-scores.json")
    contenu = [q for q in QUESTIONS if q["type"] == "contenu"]
    pieges = [q for q in QUESTIONS if q["type"] == "piege"]

    ok_abst = sum(1 for q in pieges if answers[str(q["id"])]["abstained"])
    faux_abst = [q["id"] for q in contenu if answers[str(q["id"])]["abstained"]]

    print("=== BungeRAG - harnais d'eval (RAGAS 0.4.3, juge Cerebras gpt-oss-120b) ===\n")
    for name in ("faithfulness", "context_precision", "context_recall"):
        vals = [scores[str(q["id"])][name] for q in contenu
                if str(q["id"]) in scores and scores[str(q["id"])].get(name) is not None]
        if vals:
            mean = sum(vals) / len(vals)
            low = sum(1 for v in vals if v < 0.7)
            print(f"{name:18} moyenne {mean:.3f}   (n={len(vals)}, "
                  f"dont {low} question(s) < 0,70)")
    print(f"{'abstention pieges':18} {ok_abst}/{len(pieges)} refus corrects")
    if faux_abst:
        print(f"{'fausses abstentions':18} questions {faux_abst}")

    print("\npires questions (faithfulness) :")
    rows = [(scores[str(q['id'])].get('faithfulness'), q) for q in contenu
            if str(q['id']) in scores and scores[str(q['id'])].get('faithfulness') is not None]
    for v, q in sorted(rows, key=lambda x: x[0])[:3]:
        print(f"  q{q['id']:02d} {v:.2f} «{q['question'][:60]}»")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    if "--answers" in sys.argv:
        run_answers()
    elif "--judge" in sys.argv:
        asyncio.run(run_judge())
    else:
        report()
