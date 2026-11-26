"""Compare Horizon-Labs multilingual-reranker small vs base à candidats identiques."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from time import monotonic

import torch
from sentence_transformers import CrossEncoder

from definitions import candidates, strength, terms_for
from evaluate_reader import ranks as page_ranks
from search import search

ROOT = Path(__file__).resolve().parents[1]
RERANKERS = {
    "horizon-small": (
        "Horizon-Labs/multilingual-reranker-small",
        "23139fec6f1f448cdf89a5ac2d2c6bf5e8c7b398",
    ),
    "horizon-base": (
        "Horizon-Labs/multilingual-reranker-base",
        "7330f6d0b3f560af0c2b9a63820ea299a45fd91b",
    ),
}


def build_candidates(question: str, english: str, breadth: int = 24):
    rows = search(
        mode="hybrid",
        k=max(40, breadth),
        table="bunge_512",
        dense_query=question,
        text_query=english,
    )[:breadth]
    terms = terms_for(question, english)
    rows, preferred = candidates(question, english, rows, search, "bunge_512")
    return rows, preferred, terms


def rerank_with(model: CrossEncoder, question: str, rows, preferred, terms, keep: int = 5):
    if not rows:
        return [], 0.0
    t0 = monotonic()
    scores = model.predict(
        [(question, r["text"]) for r in rows], batch_size=4, show_progress_bar=False
    )
    elapsed = monotonic() - t0
    paired = sorted(
        zip(rows, map(float, scores)), key=lambda item: item[1], reverse=True
    )
    result = [row for row, _ in paired[:keep]]
    formal = next(
        (
            row
            for row, _ in paired
            if row["chunk_id"] in preferred and strength(row, terms) == 3
        ),
        None,
    )
    if formal and keep > 1 and all(r["chunk_id"] != formal["chunk_id"] for r in result):
        result[-1] = formal
    return result, elapsed


def main():
    hist_cases = json.loads((ROOT / "eval/passages-eval.json").read_text())["questions"]
    res_cases = [
        json.loads(line)
        for line in (ROOT / "eval/lecture-reservee.jsonl").read_text().splitlines()
    ]
    recette_dir = ROOT / "eval/cache/recette-v3"

    # Build identical candidate pools once (exact same English translations as V3).
    hist_pools = []
    for q in hist_cases:
        rows, preferred, terms = build_candidates(q["question"], q["en"])
        hist_pools.append((q, rows, preferred, terms))
    print(f"Prepared {len(hist_pools)} historical pools", flush=True)

    res_pools = []
    for q in res_cases:
        if not q["evidence_groups"]:
            continue
        cached = json.loads((recette_dir / f"reserve-{q['id']}-v3.json").read_text())
        rows, preferred, terms = build_candidates(q["question"], cached["english"])
        res_pools.append((q, rows, preferred, terms))
    print(f"Prepared {len(res_pools)} reserved pools", flush=True)

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    report = {"device": device, "models": {}}

    for name, (repo, rev) in RERANKERS.items():
        print(f"\n=== Evaluating {name} ({repo}@{rev[:8]}) on {device} ===", flush=True)
        model = CrossEncoder(
            repo,
            revision=rev,
            max_length=512,
            device=device,
            model_kwargs={"dtype": torch.float16 if device == "mps" else torch.float32},
        )
        hist_rows = []
        for q, rows, preferred, terms in hist_pools:
            top, sec = rerank_with(model, q["question"], rows, preferred, terms)
            ids = [r["chunk_id"] for r in top]
            rank = next((i for i, cid in enumerate(ids, 1) if cid in q["targets"]), None)
            hist_rows.append(dict(id=q["id"], rank=rank, seconds=round(sec, 3)))

        res_rows = []
        for q, rows, preferred, terms in res_pools:
            top, sec = rerank_with(model, q["question"], rows, preferred, terms)
            pos = page_ranks(q["evidence_groups"], top, reader=False)
            res_rows.append(
                dict(id=q["id"], family=q["family"], ranks=pos, seconds=round(sec, 3))
            )

        # Measure true CPU latency on 5 representative 24-candidate queries (same as HF free CPU Space).
        cpu_model = CrossEncoder(
            repo,
            revision=rev,
            max_length=512,
            device="cpu",
            model_kwargs={"dtype": torch.float32},
        )
        cpu_times = []
        for q, rows, preferred, terms in res_pools[:5]:
            _, sec = rerank_with(cpu_model, q["question"], rows, preferred, terms)
            cpu_times.append(round(sec, 3))
        del cpu_model, model

        hist_hit1 = sum(r["rank"] == 1 for r in hist_rows)
        hist_hit5 = sum(r["rank"] is not None for r in hist_rows)
        hist_mrr = round(
            sum(1 / r["rank"] for r in hist_rows if r["rank"] is not None) / len(hist_rows),
            4,
        )
        res_hit1 = sum(any(p == 1 for p in r["ranks"]) for r in res_rows)
        res_hit5 = sum(any(p is not None for p in r["ranks"]) for r in res_rows)
        res_mrr = round(
            sum(
                1 / min(p for p in r["ranks"] if p is not None)
                for r in res_rows
                if any(p is not None for p in r["ranks"])
            )
            / len(res_rows),
            4,
        )
        arg_full = sum(
            all(p is not None for p in r["ranks"])
            for r in res_rows
            if r["family"] == "argument"
        )
        summary = dict(
            repo=repo,
            revision=rev,
            historique=dict(hit1=hist_hit1, hit5=hist_hit5, total=len(hist_rows), mrr=hist_mrr),
            reserve=dict(
                hit1=res_hit1,
                hit5=res_hit5,
                total=len(res_rows),
                mrr=res_mrr,
                arguments_complets=arg_full,
            ),
            cpu_median_seconds=round(median(cpu_times), 3),
            cpu_times=cpu_times,
            hist_rows=hist_rows,
            res_rows=res_rows,
        )
        report["models"][name] = summary
        print(
            f"  HIST: hit1={hist_hit1}/30 hit5={hist_hit5}/30 mrr={hist_mrr} | "
            f"RES: hit1={res_hit1}/25 hit5={res_hit5}/25 mrr={res_mrr} args={arg_full}/5 | "
            f"CPU med={summary['cpu_median_seconds']}s {cpu_times}",
            flush=True,
        )

    # Question-by-question diff
    small_h = {r["id"]: r["rank"] for r in report["models"]["horizon-small"]["hist_rows"]}
    base_h = {r["id"]: r["rank"] for r in report["models"]["horizon-base"]["hist_rows"]}
    print("\n=== DIFF HISTORIQUE (small -> base) ===")
    for qid in small_h:
        if (small_h[qid] is not None) != (base_h[qid] is not None):
            print(f"  hist {qid}: {small_h[qid]} -> {base_h[qid]}")

    small_r = {r["id"]: r["ranks"] for r in report["models"]["horizon-small"]["res_rows"]}
    base_r = {r["id"]: r["ranks"] for r in report["models"]["horizon-base"]["res_rows"]}
    print("\n=== DIFF RESERVE (small -> base) ===")
    for qid in small_r:
        if small_r[qid] != base_r[qid]:
            print(f"  res  {qid}: {small_r[qid]} -> {base_r[qid]}")

    out = ROOT / "eval/cache/compare-rerankers.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
