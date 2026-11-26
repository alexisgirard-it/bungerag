"""Comparatif qualitatif et de fidélité des LLM gratuits sur passages identiques."""

from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path

from citations import validate_citations
from config import PUBLIC_V3
from evidence import Passage, answer_with_evidence, editorial_passage
from generate import generate_json
from library import node_source

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "index/provenance-512.sqlite"

MODELS = [
    ("gemini-4-hydrogen", "gemini/gemini-4-hydrogen"),
    ("gemini-2.5-flash", "gemini/gemini-2.5-flash"),
    ("gemini-3.1-flash-lite", "gemini/gemini-3.1-flash-lite"),
]

CASES = [
    {
        "id": "attribution-emerson",
        "question": "Qui est l’auteur de la phrase « the book of Nature is the book of Fate » et comment Bunge y répond-il ?",
        "nodes": ["emerson-fatum", "critique-emerson", "fatalisme", "determinisme-causal"],
        "must_mention": ["emerson"],
    },
    {
        "id": "ethique-bonheur",
        "question": "Pourquoi Bunge conclut-il dans le Théorème 2.1 que personne ne peut être complètement heureux, et quelle distinction fait-il avec le bien-être ?",
        "nodes": ["bonheur", "incompatibilite", "theoreme-bonheur", "bonheur-et-bien-etre"],
        "must_mention": ["bien-être", "incompatib"],
    },
    {
        "id": "biais-holisme",
        "question": "Puisque Bunge rejette le réductionnisme atomiste, son systémisme revient donc au holisme qui refuse d’analyser les composants ?",
        "nodes": ["agregat-et-systeme", "postulat-emergence", "ni-holisme-ni-atomisme", "systemisme"],
        "must_mention": ["holisme", "composants"],
    },
    {
        "id": "efficacite-verite",
        "question": "Si une règle technique ou un programme informatique est efficace, cela prouve-t-il sa vérité ou sa rectitude morale chez Bunge ?",
        "nodes": ["verite-efficacite", "testabilite-reelle", "regle-technologique", "agir", "action-valeurs"],
        "must_mention": ["vérité", "efficacité"],
    },
]


def passages_from_nodes(keys: list[str]) -> dict[str, Passage]:
    result = {}
    for idx, key in enumerate(keys, 1):
        src = node_source(key)
        p = editorial_passage(src, key, DB)
        if p is not None:
            result[f"P{idx}"] = p
    return result


def main():
    import evidence as ev_mod

    report = {"date": "2026-11-26", "cases": [c["id"] for c in CASES], "models": {}}
    orig_passages_for = ev_mod.passages_for

    for label, backend in MODELS:
        print(f"\n=== {label} ===", flush=True)
        cfg = replace(PUBLIC_V3, generation_backend=backend, verification_backend=backend)
        rows = []
        for case in CASES:
            fixed = passages_from_nodes(case["nodes"])
            ev_mod.passages_for = lambda _hits, _db, _f=fixed: dict(_f)
            t0 = time.monotonic()
            try:
                answer, sources, reason = answer_with_evidence(
                    case["question"], [], cfg, generate_json
                )
                elapsed = round(time.monotonic() - t0, 2)
                val = validate_citations(
                    answer, len(sources), abstained=(reason == "llm")
                )
                low = answer.lower()
                terms_ok = all(t in low for t in case["must_mention"])
                row = dict(
                    id=case["id"],
                    status="ok" if reason is None else f"abstained:{reason}",
                    seconds=elapsed,
                    sources_count=len(sources),
                    citations_valid=val["valid"],
                    terms_ok=terms_ok,
                    answer=answer,
                )
            except Exception as exc:
                elapsed = round(time.monotonic() - t0, 2)
                row = dict(
                    id=case["id"],
                    status="error",
                    seconds=elapsed,
                    error=str(exc).replace("\n", " ")[:180],
                )
            rows.append(row)
            print(
                f"  {case['id']:22s} -> {row['status']:20s} ({row['seconds']}s) "
                f"src={row.get('sources_count', 0)} terms_ok={row.get('terms_ok')}",
                flush=True,
            )
        report["models"][label] = {
            "ok_count": sum(r["status"] == "ok" for r in rows),
            "terms_ok_count": sum(r.get("terms_ok") is True for r in rows),
            "error_count": sum(r["status"] == "error" for r in rows),
            "rows": rows,
        }

    ev_mod.passages_for = orig_passages_for
    dest = ROOT / "eval/cache/compare-llm-blind.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"\nSaved to {dest}")


if __name__ == "__main__":
    main()
