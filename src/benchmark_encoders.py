"""Compare les encodages sur les mêmes textes et conserve les index hors du dépôt public."""

import argparse
import json
from contextlib import closing
from pathlib import Path
from time import monotonic

import lancedb
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from evaluate_reader import ranks as page_ranks
from library import connect

ROOT = Path(__file__).resolve().parents[1]
MODELS = {
    "gemma": ("google/embeddinggemma-2", "f9972ac22e696a105c482202646979e33e4b5a1e"),
    "granite": (
        "ibm-granite/granite-embedding-311m-multilingual-r2",
        "44399559930365213510b1ee2eb15ded83374f0e",
    ),
    "qwen": ("Qwen/Qwen3-Embedding-0.6B", "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", choices=MODELS)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--reserve", action="store_true", help="Évalue aussi le jeu paginé gelé.")
    args = parser.parse_args()
    if args.reserve and not args.full:
        parser.error("--reserve requiert l’index complet (--full)")
    fixture = json.loads((ROOT / "eval/passages-eval.json").read_text())
    database = lancedb.connect(ROOT / "index/lancedb").open_table("bunge_512")
    columns = ["chunk_id", "text", "vector"]
    if args.reserve:
        columns.extend(["book", "page_start", "page_end"])
    data = database.to_arrow().select(columns).to_pylist()
    pool = set(fixture["pool"])
    rows = sorted(
        (r for r in data if args.full or r["chunk_id"] in pool),
        key=lambda r: r["chunk_id"],
    )
    del data
    ids = [r["chunk_id"] for r in rows]
    model_id, revision = MODELS[args.name]
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    options = {}
    if args.name == "gemma":
        options["config_kwargs"] = {"audio_config": None, "vision_config": None}
    elif args.name == "qwen":
        options["processor_kwargs"] = {"padding_side": "left"}
    model = SentenceTransformer(
        model_id,
        revision=revision,
        device=device,
        model_kwargs={"dtype": torch.float16 if device == "mps" else torch.float32},
        **options,
    )
    model.max_seq_length = 1024
    directory = ROOT / "eval/cache/encoders" / args.name
    directory.mkdir(parents=True, exist_ok=True)
    prefix = "full" if args.full else "pool"
    part = directory / (prefix + ".npy")
    start = monotonic()
    if args.name == "qwen":
        vectors = np.array([r["vector"] for r in rows], dtype=np.float32)
    elif part.exists():
        if json.loads((directory / (prefix + "-ids.json")).read_text()) != ids:
            raise ValueError("L’ordre des passages du cache diffère de celui de l’index")
        vectors = np.load(part)
    else:
        pieces = []
        for i in range(0, len(rows), 128):
            checkpoint = directory / f"{prefix}-{i}.npy"
            if checkpoint.exists():
                batch = np.load(checkpoint)
            else:
                batch = model.encode(
                    [r["text"] for r in rows[i : i + 128]],
                    prompt_name="document",
                    normalize_embeddings=True,
                    batch_size=4,
                    show_progress_bar=False,
                ).astype("float32")
                np.save(checkpoint, batch)
            pieces.append(batch)
            if i % 1024 == 0:
                print("documents", i + len(batch), "/", len(rows), flush=True)
        vectors = np.concatenate(pieces)
        np.save(part, vectors)
    assert len(ids) == len(vectors)
    (directory / (prefix + "-ids.json")).write_text(json.dumps(ids))
    doc_seconds = monotonic() - start
    start = monotonic()
    questions = fixture["questions"]
    queries = model.encode(
        [q["question"] for q in questions],
        prompt_name="query",
        batch_size=4,
        normalize_embeddings=True,
    ).astype("float32")
    scores = queries @ vectors.T
    ranks = [
        next(i for i, j in enumerate(np.argsort(-s), 1) if ids[j] in q["targets"])
        for q, s in zip(questions, scores)
    ]
    result = dict(
        model=model_id,
        revision=revision,
        count=len(rows),
        hit5=sum(i <= 5 for i in ranks),
        mrr=round(sum(1 / i for i in ranks) / len(ranks), 4),
        ranks=ranks,
        query_seconds=round(monotonic() - start, 2),
        doc_seconds=round(doc_seconds, 2),
    )
    (directory / (prefix + "-scores.json")).write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)

    if args.reserve:
        reserve_file = ROOT / "eval/lecture-reservee.jsonl"
        cases = [json.loads(line) for line in reserve_file.read_text().splitlines()]
        cases = [case for case in cases if case["evidence_groups"]]
        with closing(connect()) as db:
            editions = dict(db.execute("SELECT book,edition FROM books"))
        if any(
            editions.get(group["book"]) != group["edition"]
            for case in cases
            for group in case["evidence_groups"]
        ):
            raise ValueError("Le jeu réservé et l’index utilisent des éditions différentes")
        start = monotonic()
        queries = model.encode(
            [case["question"] for case in cases],
            prompt_name="query",
            batch_size=4,
            normalize_embeddings=True,
        ).astype("float32")
        indices = np.argsort(-(queries @ vectors.T), axis=1)
        trials = []
        for case, order in zip(cases, indices):
            positions = page_ranks(case["evidence_groups"], [rows[i] for i in order])
            trials.append(dict(id=case["id"], family=case["family"], ranks=positions))
        first = [
            min((r for r in row["ranks"] if r is not None), default=float("inf"))
            for row in trials
        ]
        report = dict(
            model=model_id,
            revision=revision,
            count=len(rows),
            hit1=sum(r == 1 for r in first),
            hit5=sum(r <= 5 for r in first),
            mrr=round(sum(1 / r for r in first) / len(first), 4),
            query_seconds=round(monotonic() - start, 2),
            trials=trials,
        )
        (directory / "reserve-scores.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        )
        print({k: v for k, v in report.items() if k != "trials"}, flush=True)


if __name__ == "__main__":
    main()
