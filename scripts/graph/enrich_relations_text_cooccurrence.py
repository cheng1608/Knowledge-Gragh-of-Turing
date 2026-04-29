from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from itertools import combinations
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

_GRAPH_DIR = Path(__file__).resolve().parent
if str(_GRAPH_DIR) not in sys.path:
    sys.path.insert(0, str(_GRAPH_DIR))
from relation_schema import relation_row_for_write, write_relations_csv

MAC_TUTOR_TURING_URL = "https://mathshistory.st-andrews.ac.uk/Biographies/Turing/"


def read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip()).lower()


def split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def build_name_index(nodes: List[Dict[str, str]], min_name_len: int) -> List[Tuple[str, str, re.Pattern[str]]]:
    entries: List[Tuple[str, str, re.Pattern[str]]] = []
    for row in nodes:
        qid = row.get("id", "").strip()
        name = row.get("name", "").strip()
        if not qid or not name:
            continue
        if len(name) < min_name_len:
            continue
        if name.upper().startswith("Q") and name[1:].isdigit():
            continue
        pat = re.compile(r"\b" + re.escape(name) + r"\b", flags=re.IGNORECASE)
        entries.append((qid, name, pat))
    entries.sort(key=lambda x: len(x[1]), reverse=True)
    return entries


def extract_sentence_qids(
    sentences: List[str],
    name_index: List[Tuple[str, str, re.Pattern[str]]],
) -> List[Set[str]]:
    out: List[Set[str]] = []
    for sent in sentences:
        hit_qids: Set[str] = set()
        for qid, _name, pat in name_index:
            if pat.search(sent):
                hit_qids.add(qid)
        out.append(hit_qids)
    return out


def build_comention_edges(
    sentence_qids: List[Set[str]],
    sentences: List[str],
    min_co_mentions: int,
    max_evidence_len: int = 320,
) -> List[Tuple[str, str, str, str, str]]:
    pair_count: Dict[Tuple[str, str], int] = {}
    pair_evidence: Dict[Tuple[str, str], str] = {}
    for idx, qids in enumerate(sentence_qids):
        if len(qids) < 2:
            continue
        sent = sentences[idx] if idx < len(sentences) else ""
        excerpt = (sent or "")[:max_evidence_len]
        for a, b in combinations(sorted(qids), 2):
            pair_count[(a, b)] = pair_count.get((a, b), 0) + 1
            if (a, b) not in pair_evidence and excerpt:
                pair_evidence[(a, b)] = excerpt

    edges: List[Tuple[str, str, str, str, str]] = []
    for (a, b), c in pair_count.items():
        if c < min_co_mentions:
            continue
        role = f"co_mentions={c}"
        edges.append((a, "CO_MENTIONED", b, role, pair_evidence.get((a, b), "")))
    return edges


def merge_relations(
    existing: List[Dict[str, str]],
    new_edges: Iterable[Tuple[str, str, str, str, str]],
    source: str,
    confidence: str,
    source_url: str,
) -> List[Dict[str, str]]:
    seen: Set[Tuple[str, str, str, str, str]] = set()
    merged: List[Dict[str, str]] = []

    for row in existing:
        s = row.get("start_id", "")
        r = row.get("relation", "")
        e = row.get("end_id", "")
        y = row.get("year", "")
        role = row.get("role", "")
        key = (s, r, e, y, role)
        if key in seen:
            continue
        seen.add(key)
        merged.append(
            relation_row_for_write(
                {
                    "start_id": s,
                    "relation": r,
                    "end_id": e,
                    "year": y,
                    "role": role,
                    "source": row.get("source", ""),
                    "confidence": (row.get("confidence") or "").strip(),
                    "evidence": (row.get("evidence") or "").strip(),
                    "source_url": (row.get("source_url") or "").strip(),
                }
            )
        )

    for s, r, e, role, evidence in new_edges:
        key = (s, r, e, "", role)
        if key in seen:
            continue
        seen.add(key)
        merged.append(
            relation_row_for_write(
                {
                    "start_id": s,
                    "relation": r,
                    "end_id": e,
                    "year": "",
                    "role": role,
                    "source": source,
                    "confidence": confidence,
                    "evidence": evidence,
                    "source_url": source_url,
                }
            )
        )

    return sorted(merged, key=lambda x: (x["start_id"], x["relation"], x["end_id"], x["role"]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggressive text co-mention edge enrichment.")
    parser.add_argument("--nodes", default="data/final/nodes_final.csv", help="nodes_final CSV")
    parser.add_argument("--existing", default="data/final/relations_final.csv", help="existing relations CSV")
    parser.add_argument("--text", default="data/raw/mactutor_turing.txt", help="source text file")
    parser.add_argument("--out", default="data/final/relations_final_text_enriched.csv", help="output CSV")
    parser.add_argument("--min-name-len", type=int, default=4, help="minimum node name length")
    parser.add_argument("--min-co-mentions", type=int, default=1, help="minimum sentence co-mention count")
    parser.add_argument("--confidence", default="0.68", help="confidence assigned to co-mention edges")
    args = parser.parse_args()

    nodes = read_csv(args.nodes)
    existing = read_csv(args.existing) if os.path.isfile(args.existing) else []
    with open(args.text, "r", encoding="utf-8") as f:
        text = f.read()

    sentences = split_sentences(text)
    name_index = build_name_index(nodes, args.min_name_len)
    sentence_qids = extract_sentence_qids(sentences, name_index)
    new_edges = build_comention_edges(sentence_qids, sentences, args.min_co_mentions)

    source = "MacTutor text co-mention"
    merged = merge_relations(
        existing,
        new_edges,
        source=source,
        confidence=args.confidence,
        source_url=MAC_TUTOR_TURING_URL,
    )
    write_relations_csv(args.out, merged)

    print(f"Sentences scanned:   {len(sentences)}")
    print(f"Node names indexed:  {len(name_index)}")
    print(f"New co-mention edges:{len(new_edges)}")
    print(f"Relations written:   {len(merged)} -> {args.out}")


if __name__ == "__main__":
    main()
