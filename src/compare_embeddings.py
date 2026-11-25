"""Comparaison dense à passages constants sur les références PDF du dépôt."""

import json
from pathlib import Path
import time

import lancedb
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from search import MODEL, MODEL_REVISION

ROOT = Path(__file__).resolve().parents[1]
HARRIER = "microsoft/harrier-oss-v1-0.6b"
REVISION = "f9b9dc8d367d443f2479d27aa5d8d2850c0774ee"


def main():
    data = json.loads((ROOT / "eval/passages-eval.json").read_text())
    table = lancedb.connect(ROOT / "index/lancedb").open_table("bunge_512")
    rows = {
        r["chunk_id"]: r
        for r in table.to_arrow().select(["chunk_id", "text", "vector"]).to_pylist()
        if r["chunk_id"] in data["pool"]
    }
    ids = data["pool"]
    questions = data["questions"]
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    for model_id, revision, prompt in [
        (MODEL, MODEL_REVISION, "query"),
        (HARRIER, REVISION, "web_search_query"),
    ]:
        model = SentenceTransformer(
            model_id,
            revision=revision,
            device=device,
            model_kwargs={
                "torch_dtype": torch.float16 if device == "mps" else torch.float32
            },
            processor_kwargs={"padding_side": "left"},
        )
        model.max_seq_length = 1024
        if model_id == MODEL:
            documents = np.array([rows[i]["vector"] for i in ids])
        else:
            documents = model.encode(
                [rows[i]["text"] for i in ids], batch_size=2, normalize_embeddings=True
            ).astype("float32")
        start = time.monotonic()
        queries = model.encode(
            [q["question"] for q in questions],
            prompt_name=prompt,
            batch_size=2,
            normalize_embeddings=True,
        ).astype("float32")
        scores = queries @ documents.T
        ranks = [
            next(i for i, j in enumerate(np.argsort(-s), 1) if ids[j] in q["targets"])
            for q, s in zip(questions, scores)
        ]
        print(
            json.dumps(
                {
                    "model": model_id,
                    "revision": revision,
                    "pool": len(ids),
                    "n": len(ranks),
                    "hit5": sum(i <= 5 for i in ranks),
                    "mrr": round(sum(1 / i for i in ranks) / len(ranks), 3),
                    "query_seconds": round(time.monotonic() - start, 2),
                    "ranks": ranks,
                }
            ),
            flush=True,
        )
        del model
        if device == "mps":
            torch.mps.empty_cache()


if __name__ == "__main__":
    main()
