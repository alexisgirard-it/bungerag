"""Ablations lexicales, denses et hybrides, puis reclassement à candidats identiques."""

import json
from pathlib import Path
from time import monotonic

import lancedb
import torch
from sentence_transformers import CrossEncoder

from search import search
from audit_retrieval import first_target

ROOT = Path(__file__).resolve().parents[1]
MODEL = "Horizon-Labs/multilingual-reranker-small"
REVISION = "23139fec6f1f448cdf89a5ac2d2c6bf5e8c7b398"


def main():
    questions = json.loads((ROOT / "eval/passages-eval.json").read_text())["questions"]
    audit = {
        r["id"]: r
        for r in json.loads((ROOT / "eval/diagnostic-recherche-v2.json").read_text())
    }
    table = lancedb.connect(ROOT / "index/lancedb").open_table("bunge_512")
    texts = dict(
        zip(
            table.to_arrow().column("chunk_id").to_pylist(),
            table.to_arrow().column("text").to_pylist(),
        )
    )
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = CrossEncoder(
        MODEL,
        revision=REVISION,
        device=device,
        max_length=512,
        model_kwargs={"dtype": torch.float16 if device == "mps" else torch.float32},
    )
    out = ROOT / "eval/cache/rank-v3"
    out.mkdir(parents=True, exist_ok=True)
    for q in questions:
        path = out / f"{q['id']}.json"
        if path.exists():
            continue
        start = monotonic()
        fr, en, targets = q["question"], q["en"], q["targets"]
        pools = {}
        for mode, dense, lexical, name in [
            ("dense", fr, en, "dense-fr"),
            ("dense", en, en, "dense-en"),
            ("bm25", fr, fr, "lex-fr"),
            ("bm25", fr, en, "lex-en"),
            ("hybrid", fr, en, "hybride"),
            ("hybrid", en, en, "hybride-en"),
        ]:
            pools[name] = [
                r["chunk_id"]
                for r in search(
                    mode=mode,
                    k=40,
                    table="bunge_512",
                    dense_query=dense,
                    text_query=lexical,
                )
            ]
        original = audit[q["id"]]["candidats"]
        total = list(dict.fromkeys(original + pools["hybride"]))
        scores = model.predict(
            [(fr, texts[i]) for i in total], batch_size=4, show_progress_bar=False
        )
        by_id = dict(zip(total, map(float, scores)))
        ranked = {
            name: {"initial": first_target(ids, targets)} for name, ids in pools.items()
        }
        for k in (12, 24, 40):
            ids = pools["hybride"][:k]
            ranked["horizon-" + str(k)] = {
                "final": first_target(sorted(ids, key=by_id.get, reverse=True), targets)
            }
        ranked["horizon-v2"] = {
            "final": first_target(
                sorted(original, key=by_id.get, reverse=True), targets
            )
        }
        path.write_text(
            json.dumps(
                dict(
                    id=q["id"],
                    ranked=ranked,
                    seconds=round(monotonic() - start, 2),
                    pools=pools,
                    horizon=by_id,
                ),
                ensure_ascii=False,
            )
        )
        print(q["id"], ranked["horizon-40"], flush=True)
    results = [json.loads((out / f"{q['id']}.json").read_text()) for q in questions]
    print(
        {
            name: sum(
                (next(iter(r["ranked"][name].values())) or 999) <= 5 for r in results
            )
            for name in results[0]["ranked"]
        }
    )


if __name__ == "__main__":
    main()
