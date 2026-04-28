"""Shared CSV schema and defaults for relations_final-style tables."""

from __future__ import annotations

from typing import Dict, List

RELATION_FIELDNAMES: List[str] = [
    "start_id",
    "relation",
    "end_id",
    "year",
    "role",
    "source",
    "confidence",
    "evidence",
    "source_url",
]


def default_confidence_for_source(source: str) -> str:
    """Heuristic default when a row has no explicit confidence."""
    s = (source or "").strip()
    low = s.lower()
    if "co-mention" in low or "mactutor text" in low:
        return "0.68"
    if "isolated-node enrich aggressive" in s:
        return "0.83"
    if "isolated-node enrich" in s:
        return "0.84"
    if "entity subgraph" in s:
        return "0.82"
    if "wikidata.org" in low or "wikidata" in low:
        return "0.80"
    return "0.80"


def relation_row_for_write(row: Dict[str, str]) -> Dict[str, str]:
    """Normalize a relation dict to RELATION_FIELDNAMES; fill confidence if missing."""
    out: Dict[str, str] = {k: (row.get(k) or "").strip() for k in RELATION_FIELDNAMES}
    if not out["confidence"]:
        out["confidence"] = default_confidence_for_source(out["source"])
    if not out["source_url"] and out["start_id"].startswith("Q") and "wikidata" in out["source"].lower():
        out["source_url"] = f"https://www.wikidata.org/wiki/{out['start_id']}"
    return out


def write_relations_csv(path: str, rows: List[Dict[str, str]]) -> None:
    import csv
    import os

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    normalized = [relation_row_for_write(r) for r in rows]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RELATION_FIELDNAMES)
        w.writeheader()
        for r in normalized:
            w.writerow(r)
