"""
Validate nodes_final.csv + relations_final.csv against ontology constraints.

Writes data/compare/validation_report.csv with columns:
severity, code, row_hint, message, suggestion
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NODES = REPO_ROOT / "data/final/nodes_final.csv"
DEFAULT_RELATIONS = REPO_ROOT / "data/final/relations_final.csv"
DEFAULT_REPORT = REPO_ROOT / "data/compare/validation_report.csv"

# Core + enrichment relations from ontology.md
ALLOWED_TRIPLES: Set[Tuple[str, str, str]] = {
    ("Person", "AUTHORED", "Work"),
    ("Person", "AFFILIATED_WITH", "Organization"),
    ("Person", "PROPOSED", "Concept"),
    ("Work", "INTRODUCES", "Concept"),
    ("Person", "PARTICIPATED_IN", "Event"),
    ("Event", "OCCURRED_IN", "Place"),
    ("Organization", "LOCATED_IN", "Place"),
    ("Person", "INFLUENCED", "Person"),
    ("Person", "BORN_IN", "Place"),
    ("Person", "DIED_IN", "Place"),
    ("Person", "RESIDED_IN", "Place"),
    ("Work", "LOCATED_IN", "Place"),
    ("Organization", "LOCATED_IN", "Place"),
    ("Place", "LOCATED_IN", "Place"),
}

WILDCARD_RELATIONS = frozenset({"RELATED_TO", "CO_MENTIONED", "SUGGESTED_RELATED"})


def read_csv(path: Path) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_report(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["severity", "code", "row_hint", "message", "suggestion"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def validate(
    nodes: List[Dict[str, str]],
    relations: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    id_to_label: Dict[str, str] = {}
    for i, row in enumerate(nodes, start=2):
        nid = (row.get("id") or "").strip()
        label = (row.get("label") or "").strip()
        if not nid:
            issues.append(
                {
                    "severity": "error",
                    "code": "NODE_EMPTY_ID",
                    "row_hint": f"nodes row {i}",
                    "message": "节点 id 为空",
                    "suggestion": "drop_or_fix",
                }
            )
            continue
        if nid in id_to_label:
            issues.append(
                {
                    "severity": "error",
                    "code": "NODE_DUP_ID",
                    "row_hint": f"nodes row {i} id={nid}",
                    "message": f"重复节点 id: {nid}",
                    "suggestion": "manual_review",
                }
            )
        id_to_label[nid] = label
        if not label:
            issues.append(
                {
                    "severity": "warn",
                    "code": "NODE_EMPTY_LABEL",
                    "row_hint": f"nodes row {i} id={nid}",
                    "message": "节点 label（类型）为空",
                    "suggestion": "fix",
                }
            )
        name = (row.get("name") or "").strip()
        if not name:
            issues.append(
                {
                    "severity": "warn",
                    "code": "NODE_EMPTY_NAME",
                    "row_hint": f"nodes row {i} id={nid}",
                    "message": "节点 name 为空",
                    "suggestion": "fix",
                }
            )

    node_ids = set(id_to_label.keys())

    for i, row in enumerate(relations, start=2):
        s = (row.get("start_id") or "").strip()
        r = (row.get("relation") or "").strip()
        e = (row.get("end_id") or "").strip()
        y = (row.get("year") or "").strip()
        hint = f"relations row {i} {s}-{r}->{e}"

        if not s or not r or not e:
            issues.append(
                {
                    "severity": "error",
                    "code": "REL_INCOMPLETE",
                    "row_hint": hint,
                    "message": "关系缺少 start_id / relation / end_id",
                    "suggestion": "drop_or_fix",
                }
            )
            continue
        if s not in node_ids:
            issues.append(
                {
                    "severity": "error",
                    "code": "REL_UNKNOWN_START",
                    "row_hint": hint,
                    "message": f"起点不在节点表: {s}",
                    "suggestion": "drop_or_fix",
                }
            )
        if e not in node_ids:
            issues.append(
                {
                    "severity": "error",
                    "code": "REL_UNKNOWN_END",
                    "row_hint": hint,
                    "message": f"终点不在节点表: {e}",
                    "suggestion": "drop_or_fix",
                }
            )
        if y:
            try:
                int(y)
            except ValueError:
                issues.append(
                    {
                        "severity": "warn",
                        "code": "REL_YEAR_UNPARSEABLE",
                        "row_hint": hint,
                        "message": f"year 非整数: {y!r}",
                        "suggestion": "fix",
                    }
                )

        ls = id_to_label.get(s, "")
        le = id_to_label.get(e, "")
        if s in node_ids and e in node_ids:
            if r in WILDCARD_RELATIONS:
                pass
            elif (ls, r, le) not in ALLOWED_TRIPLES:
                issues.append(
                    {
                        "severity": "warn",
                        "code": "REL_TYPE_MISMATCH",
                        "row_hint": hint,
                        "message": f"类型组合不在允许列表: ({ls!r}, {r}, {le!r})",
                        "suggestion": "manual_review",
                    }
                )

        conf = (row.get("confidence") or "").strip()
        if conf:
            try:
                v = float(conf)
                if v < 0 or v > 1:
                    issues.append(
                        {
                            "severity": "warn",
                            "code": "REL_CONFIDENCE_RANGE",
                            "row_hint": hint,
                            "message": f"confidence 建议落在 [0,1]: {conf}",
                            "suggestion": "fix",
                        }
                    )
            except ValueError:
                issues.append(
                    {
                        "severity": "warn",
                        "code": "REL_CONFIDENCE_NAN",
                        "row_hint": hint,
                        "message": f"confidence 非数字: {conf!r}",
                        "suggestion": "fix",
                    }
                )

        if not (row.get("source") or "").strip():
            issues.append(
                {
                    "severity": "info",
                    "code": "REL_MISSING_SOURCE",
                    "row_hint": hint,
                    "message": "source 为空，不利于溯源",
                    "suggestion": "fix",
                }
            )

    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate final graph CSVs.")
    parser.add_argument("--nodes", type=Path, default=DEFAULT_NODES)
    parser.add_argument("--relations", type=Path, default=DEFAULT_RELATIONS)
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    if not args.nodes.is_file():
        print(f"Missing nodes file: {args.nodes}", file=sys.stderr)
        sys.exit(1)
    if not args.relations.is_file():
        print(f"Missing relations file: {args.relations}", file=sys.stderr)
        sys.exit(1)

    nodes = read_csv(args.nodes)
    relations = read_csv(args.relations)
    issues = validate(nodes, relations)
    write_report(args.out, issues)

    err = sum(1 for x in issues if x["severity"] == "error")
    warn = sum(1 for x in issues if x["severity"] == "warn")
    print(f"Nodes: {len(nodes)} | Relations: {len(relations)}")
    print(f"Issues: {len(issues)} (errors={err}, warns={warn}) -> {args.out}")


if __name__ == "__main__":
    main()
