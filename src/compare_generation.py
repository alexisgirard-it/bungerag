"""Essai apparié des rédacteurs avec les mêmes preuves et le même vérificateur."""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import lancedb

import generate
from config import PUBLIC_V2
from evidence import CHECK, answer_with_evidence

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "definition": (
        "Qu’est-ce qu’un psychon selon Bunge ?",
        ["scientific-materialism-1981:00066", "mind-body-problem-1980:00171"],
    ),
    "hypothese": (
        "Bunge présente-t-il l'association de psychons comme un fait établi ou comme une hypothèse ?",
        [
            "mind-body-problem-1980:00171",
            "treatise-5-epistemology-1-exploring-the-world-1983:00053",
        ],
    ),
    "hors-corpus": (
        "Quelle est la clé privée du portefeuille Bitcoin de Mario Bunge ?",
        ["scientific-materialism-1981:00066", "mind-body-problem-1980:00171"],
    ),
}


def fixtures():
    data = json.loads((ROOT / "eval/passages-eval.json").read_text())
    cases = dict(CASES)
    for row in data["questions"]:
        if row["id"] in (13, 15, 17):
            cases[str(row["id"])] = (row["question"], row["targets"][:4])
    db = lancedb.connect(ROOT / "index/lancedb").open_table("bunge_512")
    keys = {i for _, ids in cases.values() for i in ids}
    hits = {
        r["chunk_id"]: {**r, "rerank_score": 1.0}
        for r in db.to_arrow()
        .select(["chunk_id", "book", "title", "year", "text", "page_start", "page_end"])
        .to_pylist()
        if r["chunk_id"] in keys
    }
    return {name: (q, [hits[i] for i in ids]) for name, (q, ids) in cases.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gemini/gemini-3.8-flash", "gemini/gemini-3.1-flash-lite"],
    )
    parser.add_argument("--judge", default="gemini/gemini-3.1-flash-lite")
    parser.add_argument("--cases", nargs="*")
    parser.add_argument("--output", default="comparaison-redaction")
    args = parser.parse_args()
    items = fixtures()
    out = ROOT / "eval/cache" / args.output
    out.mkdir(parents=True, exist_ok=True)

    def run(model):
        for name, (question, hits) in items.items():
            if args.cases and name not in args.cases:
                continue
            path = (
                out
                / f"{name}-{model.replace('/', '_')}-{args.judge.replace('/', '_')}.json"
            )

            def produce(prompt, system, backend, max_tokens):
                return generate.generate_json(
                    prompt,
                    system,
                    args.judge if system == CHECK else backend,
                    max_tokens,
                )

            start = time.monotonic()
            try:
                answer, sources, reason = answer_with_evidence(
                    question,
                    hits,
                    replace(PUBLIC_V2, generation_backend=model),
                    produce,
                )
                record = {"answer": answer, "sources": sources, "reason": reason}
            except Exception as exc:
                record = {
                    "error": type(exc).__name__,
                    "code": getattr(exc, "code", None),
                }
            record.update(
                model=model,
                judge=args.judge,
                id=name,
                input_ids=[h["chunk_id"] for h in hits],
                seconds=round(time.monotonic() - start, 1),
            )
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
            print(
                name,
                model,
                record.get("error") or record.get("reason") or len(record["sources"]),
                record["seconds"],
                flush=True,
            )

    with ThreadPoolExecutor(max_workers=min(2, len(args.models))) as pool:
        list(pool.map(run, args.models))


if __name__ == "__main__":
    main()
