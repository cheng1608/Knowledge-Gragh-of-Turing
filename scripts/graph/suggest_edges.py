"""
Heuristic link suggestion via Adamic-Adar on an undirected projection of relations.

Reads relations_final.csv, writes data/compare/relations_suggested.csv
(not merged into the graph by default).
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RELATIONS = REPO_ROOT / "data/final/relations_final.csv"
DEFAULT_OUT = REPO_ROOT / "data/compare/relations_suggested.csv"

_GRAPH_DIR = Path(__file__).resolve().parent
if str(_GRAPH_DIR) not in sys.path:
    sys.path.insert(0, str(_GRAPH_DIR))
from relation_schema import relation_row_for_write, write_relations_csv


def read_csv(path: Path) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def adamic_adar(
    adj: Dict[str, Set[str]],
    deg: Dict[str, int],
    top_k_per_node: int,
    min_score: float,
) -> List[Tuple[str, str, float]]:
    """Return candidate undirected edges (a,b,score) with a < b lexicographically."""
    candidates: List[Tuple[str, str, float]] = []
    nodes = sorted(adj.keys())
    for u in nodes:
        nu = adj[u]
        if not nu:
            continue
        scores: Dict[str, float] = defaultdict(float)
        for x in nu:
            for v in adj[x]:
                if v == u or v in nu:
                    continue
                dv = deg.get(v, 0)
                if dv <= 1:
                    continue
                scores[v] += 1.0 / math.log(dv)
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:top_k_per_node]
        for v, sc in ranked:
            if sc < min_score:
                continue
            a, b = (u, v) if u < v else (v, u)
            candidates.append((a, b, sc))
    best: Dict[Tuple[str, str], float] = {}
    for a, b, sc in candidates:
        k = (a, b)
        if sc > best.get(k, 0.0):
            best[k] = sc
    return [(a, b, s) for (a, b), s in sorted(best.items(), key=lambda kv: -kv[1])]


def main() -> None:
    parser = argparse.ArgumentParser(description="Suggest new edges via Adamic-Adar.")
    parser.add_argument("--relations", type=Path, default=DEFAULT_RELATIONS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--top-k", type=int, default=5, help="candidates per seed node")
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.15,
        help="lower threshold yields more candidates on small graphs",
    )
    parser.add_argument("--limit", type=int, default=200, help="max suggested rows to write")
    args = parser.parse_args()

    if not args.relations.is_file():
        print(f"Missing {args.relations}", file=sys.stderr)
        sys.exit(1)

    rows = read_csv(args.relations)
    existing_pairs: Set[Tuple[str, str]] = set()
    adj: Dict[str, Set[str]] = defaultdict(set)
    deg: Dict[str, int] = defaultdict(int)

    for r in rows:
        s = (r.get("start_id") or "").strip()
        e = (r.get("end_id") or "").strip()
        if not s or not e or s == e:
            continue
        pair = (s, e) if s < e else (e, s)
        existing_pairs.add(pair)
        adj[s].add(e)
        adj[e].add(s)
        deg[s] += 1
        deg[e] += 1

    triples = adamic_adar(adj, dict(deg), args.top_k, args.min_score)
    out_rows: List[Dict[str, str]] = []
    for a, b, sc in triples:
        if (a, b) in existing_pairs:
            continue
        if len(out_rows) >= args.limit:
            break
        out_rows.append(
            relation_row_for_write(
                {
                    "start_id": a,
                    "relation": "SUGGESTED_RELATED",
                    "end_id": b,
                    "year": "",
                    "role": f"suggestion_score={sc:.4f}",
                    "source": "heuristic_adamic_adar",
                    "confidence": f"{min(0.99, 0.35 + 0.1 * sc):.3f}",
                    "evidence": "",
                    "source_url": "",
                }
            )
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_relations_csv(args.out, out_rows)
    print(f"Wrote {len(out_rows)} suggestions -> {args.out}")


if __name__ == "__main__":
    main()
