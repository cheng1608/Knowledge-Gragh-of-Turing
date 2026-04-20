import argparse
import csv
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# 生成最终的节点和关系表


GENERIC_LOW_VALUE_NAMES = {
    "alan",
    "turing",
    "newman",
    "morcom",
    "princeton",
    "bletchley",
}


def read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: str, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).lower()


def should_keep_linked_row(row: Dict[str, str], min_score: float) -> bool:
    try:
        score = float(row.get("link_score", "0") or 0.0)
    except Exception:
        score = 0.0
    if score < min_score:
        return False

    name_norm = normalize_name(row.get("name", ""))
    if name_norm in GENERIC_LOW_VALUE_NAMES:
        return False
    return True


def merge_nodes(
    base_nodes: List[Dict[str, str]],
    linked_nodes: List[Dict[str, str]],
    min_score: float,
) -> Dict[str, Dict[str, str]]:
    node_map: Dict[str, Dict[str, str]] = {}

    # 1) Base structured nodes from Wikidata seed.
    for row in base_nodes:
        node_id = row["id"]
        node_map[node_id] = {
            "id": node_id,
            "label": row.get("label", ""),
            "name": row.get("name", ""),
            "source": "wikidata_seed",
            "confidence": "0.80",
            "wikidata_description": row.get("description", ""),
        }

    # 2) Text linked nodes, filtered by confidence and noise.
    for row in linked_nodes:
        if not should_keep_linked_row(row, min_score):
            continue
        qid = row.get("wikidata_qid", "")
        if not qid:
            continue

        label = row.get("label", "")
        name = row.get("name", "")
        description = row.get("wikidata_description", "")
        confidence = row.get("link_score", "")

        if qid not in node_map:
            node_map[qid] = {
                "id": qid,
                "label": label,
                "name": name,
                "source": "text_linked",
                "confidence": confidence,
                "wikidata_description": description,
            }
        else:
            # Merge source provenance and prefer a non-empty human-friendly name.
            old_source = node_map[qid].get("source", "")
            if "text_linked" not in old_source:
                node_map[qid]["source"] = old_source + "|text_linked"

            old_name = node_map[qid].get("name", "")
            if (old_name.startswith("Q") and len(old_name) > 1) or not old_name:
                node_map[qid]["name"] = name or old_name

            old_desc = node_map[qid].get("wikidata_description", "")
            if (not old_desc) and description:
                node_map[qid]["wikidata_description"] = description

            # Keep max confidence if both exist.
            try:
                old_conf = float(node_map[qid].get("confidence", "0") or 0.0)
                new_conf = float(confidence or 0.0)
                if new_conf > old_conf:
                    node_map[qid]["confidence"] = f"{new_conf:.3f}"
            except Exception:
                pass

    return node_map


def filter_relations(relations: List[Dict[str, str]], node_ids: Set[str]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str, str, str, str]] = set()
    for row in relations:
        s = row.get("start_id", "")
        r = row.get("relation", "")
        e = row.get("end_id", "")
        y = row.get("year", "")
        role = row.get("role", "")
        src = row.get("source", "")

        if s not in node_ids or e not in node_ids:
            continue
        key = (s, r, e, y, role)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "start_id": s,
                "relation": r,
                "end_id": e,
                "year": y,
                "role": role,
                "source": src,
                "confidence": "0.80",
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build final nodes/relations tables for graph import.")
    parser.add_argument("--linked", default="data/processed/entities/entities_linked.csv", help="Linked entities CSV")
    parser.add_argument("--base_nodes", default="data/processed/kg_seed/nodes.csv", help="Base nodes CSV")
    parser.add_argument("--base_relations", default="data/processed/kg_seed/relations.csv", help="Base relations CSV")
    parser.add_argument("--out", default="data/final", help="Output folder")
    parser.add_argument("--min_score", type=float, default=0.85, help="Minimum link score to keep linked nodes")
    parser.add_argument(
        "--enrich-wikidata",
        action="store_true",
        help="After writing relations_final.csv, add Wikidata Q-Q edges among final nodes (requires network)",
    )
    args = parser.parse_args()

    linked_rows = read_csv(args.linked)
    base_nodes = read_csv(args.base_nodes)
    base_relations = read_csv(args.base_relations)

    node_map = merge_nodes(base_nodes, linked_rows, args.min_score)
    final_nodes = sorted(node_map.values(), key=lambda x: (x["label"], x["name"]))
    node_ids = {r["id"] for r in final_nodes}
    final_relations = filter_relations(base_relations, node_ids)
    final_relations = sorted(final_relations, key=lambda x: (x["start_id"], x["relation"], x["end_id"]))

    nodes_path = os.path.join(args.out, "nodes_final.csv")
    rels_path = os.path.join(args.out, "relations_final.csv")

    write_csv(
        nodes_path,
        ["id", "label", "name", "source", "confidence", "wikidata_description"],
        final_nodes,
    )
    write_csv(
        rels_path,
        ["start_id", "relation", "end_id", "year", "role", "source", "confidence"],
        final_relations,
    )

    rel_count_msg = len(final_relations)
    if args.enrich_wikidata:
        enrich_script = Path(__file__).resolve().parent / "enrich_relations_wikidata.py"
        subprocess.check_call(
            [
                sys.executable,
                str(enrich_script),
                "--nodes",
                nodes_path,
                "--existing",
                rels_path,
                "--out",
                rels_path,
            ]
        )
        rel_count_msg = len(read_csv(rels_path))

    print(f"Linked input rows: {len(linked_rows)}")
    print(f"Final nodes:       {len(final_nodes)} -> {nodes_path}")
    suffix = " (after Wikidata enrich)" if args.enrich_wikidata else ""
    print(f"Final relations:   {rel_count_msg} -> {rels_path}{suffix}")


if __name__ == "__main__":
    main()
