"""Teste la sélection de pages voisines à budget strictement égal (5 pages) sur deux séries."""

from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path

from evaluate_reader import ranks
from library import connect, describe_page, search_library

ROOT = Path(__file__).resolve().parents[1]


def expand_equal_budget(db, pages: list[dict], keep_top: int, budget: int = 5) -> list[dict]:
    selected = list(pages[:keep_top])
    seen = {(p["book"], str(p["page"])) for p in selected}
    for source in list(selected):
        if len(selected) >= budget:
            break
        if not str(source["page"]).isdecimal():
            continue
        phys = int(source["page"])
        for adj in (phys + 1, phys - 1):
            if len(selected) >= budget:
                break
            key = (source["book"], str(adj))
            if key in seen:
                continue
            row = db.execute("SELECT id FROM pages WHERE book=? AND page=?", key).fetchone()
            if row:
                selected.append(describe_page(db, row["id"]))
                seen.add(key)
    for source in pages[keep_top:]:
        if len(selected) >= budget:
            break
        key = (source["book"], str(source["page"]))
        if key not in seen:
            selected.append(source)
            seen.add(key)
    return selected[:budget]


def evaluate_suite(db, cases: list[dict], cached_loci: dict[str, list[str]] | None = None) -> dict:
    modes = ("top5", "top3_voisines_5", "top2_voisines_5")
    rows = []
    for case in cases:
        groups = case["evidence_groups"]
        if not groups:
            continue
        if cached_loci and case["id"] in cached_loci:
            pages = []
            for entry in cached_loci[case["id"]]:
                book, page = entry.rsplit(":", 1)
                row = db.execute("SELECT id FROM pages WHERE book=? AND page=?", (book, page)).fetchone()
                if row:
                    pages.append(describe_page(db, row["id"]))
        else:
            pages = search_library(case["question"])
        arms = {
            "top5": ranks(groups, pages[:5], reader=True),
            "top3_voisines_5": ranks(groups, expand_equal_budget(db, pages, keep_top=3, budget=5), reader=True),
            "top2_voisines_5": ranks(groups, expand_equal_budget(db, pages, keep_top=2, budget=5), reader=True),
        }
        rows.append({"id": case["id"], "family": case["family"], "ranks": arms})

    summary = {}
    for m in modes:
        any_hit = sum(any(r is not None for r in row["ranks"][m]) for row in rows)
        rank1 = sum(any(r == 1 for r in row["ranks"][m]) for row in rows)
        all_hit = sum(all(r is not None for r in row["ranks"][m]) for row in rows)
        arg_rows = [row for row in rows if row["family"] == "argument"]
        arg_full = sum(all(r is not None for r in row["ranks"][m]) for row in arg_rows)
        summary[m] = {
            "total": len(rows),
            "hit1": rank1,
            "any_hit5": any_hit,
            "all_premises": all_hit,
            "arguments_complets": f"{arg_full}/{len(arg_rows)}",
        }
    return {"summary": summary, "rows": rows}


def main():
    measured = json.loads((ROOT / "eval/mesures-v3.json").read_text())
    cached_reserve = {
        row["id"]: row["loci"] for row in measured.get("audit_referentiel_etendu", [])
    }
    cached_nouv = {
        row["id"]: row["pages"]
        for row in measured.get("comparaison_liens", {}).get("nouvelles", [])
    }
    reserve_cases = [
        json.loads(line)
        for line in (ROOT / "eval/lecture-reservee.jsonl").read_text().splitlines()
        if line.strip()
    ]
    nouv_cases = [
        json.loads(line)
        for line in (ROOT / "eval/liaisons-reservees.jsonl").read_text().splitlines()
        if line.strip()
    ]
    with closing(connect()) as db:
        res_report = evaluate_suite(db, reserve_cases, cached_reserve)
        nouv_report = evaluate_suite(db, nouv_cases, cached_nouv)
    out = {"budget_pages": 5, "reserve": res_report, "nouvelles_liaisons": nouv_report}
    dest = ROOT / "eval/cache/compare-neighbors-equal-budget.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print("RESERVE (budget=5):", json.dumps(res_report["summary"], ensure_ascii=False))
    print("NOUVELLES (budget=5):", json.dumps(nouv_report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
