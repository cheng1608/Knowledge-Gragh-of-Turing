"""
Evaluate relations_final against a small hand-labeled gold file.

Gold CSV columns:
  start_id, relation, end_id, label
where label is 1 (should exist in graph) or 0 (should NOT exist / negative example).

Prints per-relation-type counts and micro-averaged precision/recall/F1 for positives.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RELATIONS = REPO_ROOT / "data/final/relations_final.csv"
DEFAULT_GOLD = REPO_ROOT / "data/compare/gold_edges.csv"


def read_csv(path: Path) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def edge_key(row: Dict[str, str]) -> Tuple[str, str, str]:
    return (
        (row.get("start_id") or "").strip(),
        (row.get("relation") or "").strip(),
        (row.get("end_id") or "").strip(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate graph edges against gold CSV.")
    parser.add_argument("--relations", type=Path, default=DEFAULT_RELATIONS)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    args = parser.parse_args()

    if not args.relations.is_file():
        print(f"Missing relations: {args.relations}", file=sys.stderr)
        sys.exit(1)
    if not args.gold.is_file():
        print(f"Missing gold file: {args.gold}", file=sys.stderr)
        print("Add labeled rows to data/compare/gold_edges.csv (see gold_edges.example.csv).", file=sys.stderr)
        sys.exit(2)

    rel_rows = read_csv(args.relations)
    graph_edges: Set[Tuple[str, str, str]] = {edge_key(r) for r in rel_rows}

    gold_rows = read_csv(args.gold)
    pos = [r for r in gold_rows if (r.get("label") or "").strip() == "1"]
    neg = [r for r in gold_rows if (r.get("label") or "").strip() == "0"]

    tp = sum(1 for r in pos if edge_key(r) in graph_edges)
    fn = len(pos) - tp
    fp = sum(1 for r in neg if edge_key(r) in graph_edges)
    tn = len(neg) - fp

    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0

    by_rel: Dict[str, Dict[str, int]] = {}
    for r in pos:
        rel = (r.get("relation") or "").strip() or "(empty)"
        d = by_rel.setdefault(rel, {"tp": 0, "fn": 0})
        if edge_key(r) in graph_edges:
            d["tp"] += 1
        else:
            d["fn"] += 1

    print(f"Graph edges: {len(graph_edges)}")
    print(f"Gold pos: {len(pos)} | neg: {len(neg)}")
    print(f"TP={tp} FP={fp} TN={tn} FN={fn}")
    print(f"Precision={prec:.4f} Recall={rec:.4f} F1={f1:.4f}")
    print("Per relation (positives only):")
    for rel in sorted(by_rel.keys()):
        d = by_rel[rel]
        print(f"  {rel}: tp={d['tp']} fn={d['fn']}")


if __name__ == "__main__":
    main()
