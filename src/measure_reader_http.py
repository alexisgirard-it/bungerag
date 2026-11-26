"""Chronomètre les recherches directes du jeu réservé dans le parcours Gradio."""

import argparse
import json
import math
import re
from contextlib import closing
from pathlib import Path
from statistics import median
from time import monotonic
from uuid import uuid4

import requests
from bs4 import BeautifulSoup

from library import connect

ROOT = Path(__file__).resolve().parents[1]


def first_pages(http, base, lookup, question):
    started = monotonic()
    session = uuid4().hex
    payload = {
        "data": [question],
        "fn_index": lookup["id"],
        "session_hash": session,
        "trigger_id": lookup["targets"][0][0],
    }
    response = http.post(base + "/gradio_api/queue/join", json=payload, timeout=15)
    response.raise_for_status()
    with http.get(
        base + "/gradio_api/queue/data",
        params={"session_hash": session},
        stream=True,
        timeout=(10, 150),
    ) as stream:
        stream.raise_for_status()
        for line in stream.iter_lines():
            if not line.startswith(b"data:"):
                continue
            event = json.loads(line.removeprefix(b"data:"))
            if event["msg"] not in ("process_generating", "process_completed"):
                continue
            if event.get("success") is False:
                raise RuntimeError(event["msg"] + " sans résultat du lecteur")
            data = event.get("output", {}).get("data", [])
            if len(data) > 2 and isinstance(data[2], str) and data[2]:
                return round(monotonic() - started, 2), data[2]
    raise RuntimeError("Flux terminé avant affichage des pages")


def evaluate(html, editions, groups):
    doc = BeautifulSoup(html, "html.parser")
    pages = []
    for card in doc.select(".reading-card"):
        title = card.select_one("strong").get_text(strip=True)
        folio = card.select(".folio")[-1].get_text()
        if physical := re.search(r"PDF p\. (\d+)", folio):
            pages.append((title, int(physical[1])))
    if not groups:
        return dict(pages=[], message=doc.get_text(strip=True))
    positions = [
        next(
            (
                i
                for i, (title, page) in enumerate(pages, 1)
                if title == editions[group["book"]] and page in group["pdf_pages"]
            ),
            None,
        )
        for group in groups
    ]
    return dict(pages=pages, ranks=positions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Adresse de l’application Gradio")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    base = args.url.rstrip("/")
    cases = [
        json.loads(line)
        for line in (ROOT / "eval/lecture-reservee.jsonl").read_text().splitlines()
    ]
    with closing(connect()) as db:
        editions = dict(db.execute("SELECT book,title FROM books"))
    rows = []
    with requests.Session() as http:
        response = http.get(base + "/config", timeout=15)
        response.raise_for_status()
        cfg = response.json()
        labels = {
            component["id"]: component["props"].get("value")
            for component in cfg["components"]
            if component["type"] == "button"
        }
        lookup = next(
            dep for dep in cfg["dependencies"]
            if any(labels.get(target[0]) == "Rechercher les passages" for target in dep["targets"])
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        for case in cases:
            if case["family"] == "argument":
                continue
            delay, html = first_pages(http, base, lookup, case["question"])
            row = dict(
                id=case["id"], family=case["family"], seconds=delay,
                **evaluate(html, editions, case["evidence_groups"]),
            )
            rows.append(row)
            print(row, flush=True)
            delay_sorted = sorted(r["seconds"] for r in rows if "ranks" in r)
            if delay_sorted:
                summary = dict(
                    n=len(delay_sorted), p50=round(median(delay_sorted), 3),
                    p95=delay_sorted[math.ceil(len(delay_sorted) * 0.95) - 1],
                )
                args.out.write_text(
                    json.dumps(dict(rows=rows, summary=summary), ensure_ascii=False, indent=2) + "\n"
                )


if __name__ == "__main__":
    main()
