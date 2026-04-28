"""
Enrich low-degree (typically isolated) nodes by adding Wikidata-backed edges.

Strategy:
1) Compute node degree from existing relations.
2) Select targets with degree <= min_degree.
3) Query Wikidata direct claims where targets appear as subject or object.
4) Keep only claims whose other endpoint is inside current nodes_final set.
5) Map selected Wikidata properties to project relations and merge/deduplicate.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import requests

_GRAPH_DIR = Path(__file__).resolve().parent
if str(_GRAPH_DIR) not in sys.path:
    sys.path.insert(0, str(_GRAPH_DIR))
from relation_schema import relation_row_for_write, write_relations_csv

SPARQL_URL = "https://query.wikidata.org/sparql"
USER_AGENT = "turing-kg-course-project/0.1 (educational use; isolated-node enrichment)"


def run_sparql(query: str, retries: int = 6, sleep_sec: float = 2.0) -> List[dict]:
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": USER_AGENT,
    }
    last_err: Optional[Exception] = None
    for i in range(retries):
        try:
            resp = requests.get(
                SPARQL_URL,
                params={"query": query, "format": "json"},
                headers=headers,
                timeout=90,
            )
            resp.raise_for_status()
            return resp.json()["results"]["bindings"]
        except (requests.RequestException, ConnectionError, OSError) as e:
            last_err = e
            if i == retries - 1:
                raise last_err
            time.sleep(sleep_sec * (1.6**i))
    raise last_err  # pragma: no cover


def run_sparql_safe(query: str, retries: int = 6, sleep_sec: float = 2.0) -> List[dict]:
    """Best-effort wrapper: return empty rows when one batch fails."""
    try:
        return run_sparql(query, retries=retries, sleep_sec=sleep_sec)
    except Exception as e:
        print(f"[warn] SPARQL batch failed and is skipped: {str(e)[:140]}")
        return []


def wd_value(row: dict, key: str) -> Optional[str]:
    if key not in row:
        return None
    return row[key].get("value")


def qid_from_uri(uri: Optional[str]) -> Optional[str]:
    if not uri or "/entity/" not in uri:
        return None
    return uri.rsplit("/", 1)[-1]


def pid_from_uri(uri: Optional[str]) -> Optional[str]:
    if not uri:
        return None
    if "/prop/direct/" in uri:
        return uri.rsplit("/", 1)[-1]
    return None


def read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def claim_to_edge(
    subject_qid: str,
    object_qid: str,
    prop_uri: str,
    label_by_id: Dict[str, str],
) -> Optional[Tuple[str, str, str]]:
    pid = pid_from_uri(prop_uri)
    if not pid:
        return None

    ls = label_by_id.get(subject_qid, "")
    lo = label_by_id.get(object_qid, "")

    if pid == "P50":
        if ls == "Work" and lo == "Person":
            return (object_qid, "AUTHORED", subject_qid)
        return None

    if pid == "P800":
        if ls == "Person" and lo == "Work":
            return (subject_qid, "AUTHORED", object_qid)
        return None

    if pid in ("P69", "P108", "P463", "P102", "P1416"):
        if ls == "Person" and lo == "Organization":
            return (subject_qid, "AFFILIATED_WITH", object_qid)
        return None

    if pid == "P737":
        if ls == "Person" and lo == "Person":
            return (object_qid, "INFLUENCED", subject_qid)
        return None

    if pid == "P921":
        if ls == "Work" and lo in ("Concept", "Work", "Organization", "Person", "Place"):
            return (subject_qid, "INTRODUCES", object_qid)
        return None

    if pid == "P17":
        if ls == "Organization" and lo == "Place":
            return (subject_qid, "LOCATED_IN", object_qid)
        if ls == "Person" and lo == "Place":
            return (subject_qid, "AFFILIATED_WITH", object_qid)
        return None

    if pid in ("P159", "P937", "P131", "P276"):
        if ls == "Organization" and lo == "Place":
            return (subject_qid, "LOCATED_IN", object_qid)
        if ls == "Work" and lo == "Place":
            return (subject_qid, "LOCATED_IN", object_qid)
        if ls == "Place" and lo == "Place":
            return (subject_qid, "LOCATED_IN", object_qid)
        return None

    if pid == "P19" and ls == "Person" and lo == "Place":
        return (subject_qid, "BORN_IN", object_qid)
    if pid == "P20" and ls == "Person" and lo == "Place":
        return (subject_qid, "DIED_IN", object_qid)
    if pid == "P551" and ls == "Person" and lo == "Place":
        return (subject_qid, "RESIDED_IN", object_qid)

    return None


def claim_to_edge_aggressive(
    subject_qid: str,
    object_qid: str,
    prop_uri: str,
    label_by_id: Dict[str, str],
) -> Tuple[str, str, str, str]:
    """
    Aggressive fallback:
    - First try ontology-mapped edge
    - If no mapping, keep a generic RELATED_TO edge
    - Return (start, relation, end, role)
    """
    mapped = claim_to_edge(subject_qid, object_qid, prop_uri, label_by_id)
    if mapped:
        s, r, e = mapped
        return s, r, e, ""

    pid = pid_from_uri(prop_uri) or ""
    return subject_qid, "RELATED_TO", object_qid, pid


def compute_degree(node_ids: Set[str], relations: List[Dict[str, str]]) -> Dict[str, int]:
    degree = {nid: 0 for nid in node_ids}
    for row in relations:
        s = row.get("start_id", "")
        e = row.get("end_id", "")
        if s in degree:
            degree[s] += 1
        if e in degree:
            degree[e] += 1
    return degree


def batched(items: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def fetch_claims_subject_in_targets(
    target_qids: List[str],
    all_qids: Set[str],
    batch_size: int,
    pause_sec: float,
) -> List[Tuple[str, str, str]]:
    out: List[Tuple[str, str, str]] = []
    for batch in batched(target_qids, batch_size):
        values = " ".join(f"wd:{q}" for q in batch)
        query = f"""
        SELECT ?s ?p ?o WHERE {{
          VALUES ?s {{ {values} }}
          ?s ?p ?o .
          FILTER(STRSTARTS(STR(?p), "http://www.wikidata.org/prop/direct/"))
          FILTER(STRSTARTS(STR(?o), "http://www.wikidata.org/entity/Q"))
        }}
        """
        rows = run_sparql_safe(query)
        for row in rows:
            s = qid_from_uri(wd_value(row, "s"))
            p = wd_value(row, "p")
            o = qid_from_uri(wd_value(row, "o"))
            if not s or not p or not o:
                continue
            if o not in all_qids:
                continue
            if s == o:
                continue
            out.append((s, p, o))
        if pause_sec > 0:
            time.sleep(pause_sec)
    return out


def fetch_claims_object_in_targets(
    target_qids: List[str],
    all_qids: Set[str],
    batch_size: int,
    pause_sec: float,
) -> List[Tuple[str, str, str]]:
    out: List[Tuple[str, str, str]] = []
    all_qids_values = " ".join(f"wd:{q}" for q in sorted(all_qids))
    for batch in batched(target_qids, batch_size):
        values = " ".join(f"wd:{q}" for q in batch)
        query = f"""
        SELECT ?s ?p ?o WHERE {{
          VALUES ?s {{ {all_qids_values} }}
          VALUES ?o {{ {values} }}
          ?s ?p ?o .
          FILTER(STRSTARTS(STR(?p), "http://www.wikidata.org/prop/direct/"))
        }}
        """
        rows = run_sparql_safe(query)
        for row in rows:
            s = qid_from_uri(wd_value(row, "s"))
            p = wd_value(row, "p")
            o = qid_from_uri(wd_value(row, "o"))
            if not s or not p or not o:
                continue
            if s not in all_qids:
                continue
            if s == o:
                continue
            out.append((s, p, o))
        if pause_sec > 0:
            time.sleep(pause_sec)
    return out


def merge_relations(
    existing: List[Dict[str, str]],
    new_edges: Iterable[Tuple[str, str, str, str, str]],
    source: str,
    confidence: str,
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

    for s, r, e, role, source_url in new_edges:
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
                    "evidence": "",
                    "source_url": source_url,
                }
            )
        )

    return sorted(merged, key=lambda x: (x["start_id"], x["relation"], x["end_id"]))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add edges for isolated/low-degree nodes using Wikidata direct claims."
    )
    parser.add_argument("--nodes", default="data/final/nodes_final.csv", help="Nodes CSV with id + label")
    parser.add_argument("--existing", default="data/final/relations_final.csv", help="Existing relations CSV")
    parser.add_argument("--out", default="data/final/relations_final.csv", help="Output relations CSV")
    parser.add_argument(
        "--min-degree",
        type=int,
        default=0,
        help="Select nodes with degree <= this value as enrichment targets",
    )
    parser.add_argument("--batch-size", type=int, default=20, help="SPARQL VALUES batch size")
    parser.add_argument("--pause", type=float, default=1.0, help="Seconds between batches")
    parser.add_argument("--confidence", default="0.84", help="Confidence for new edges")
    parser.add_argument(
        "--aggressive",
        action="store_true",
        help="Use aggressive fallback: unmapped direct claims become RELATED_TO (role=Pxx)",
    )
    args = parser.parse_args()

    nodes = read_csv(args.nodes)
    existing = read_csv(args.existing) if os.path.isfile(args.existing) else []
    label_by_id: Dict[str, str] = {r["id"]: r.get("label", "") for r in nodes if r.get("id")}
    all_qids = set(label_by_id.keys())

    degree = compute_degree(all_qids, existing)
    target_qids = sorted([nid for nid, deg in degree.items() if deg <= args.min_degree])
    if not target_qids:
        print(f"No target nodes with degree <= {args.min_degree}.")
        print(f"Relations unchanged: {len(existing)} -> {args.out}")
        return

    raw_subject = fetch_claims_subject_in_targets(target_qids, all_qids, args.batch_size, args.pause)
    raw_object = fetch_claims_object_in_targets(target_qids, all_qids, args.batch_size, args.pause)

    raw_unique = {(s, p, o) for (s, p, o) in (raw_subject + raw_object)}
    mapped: List[Tuple[str, str, str, str, str]] = []
    for s, p, o in raw_unique:
        url = f"https://www.wikidata.org/wiki/{s}"
        if args.aggressive:
            ms, mr, me, role = claim_to_edge_aggressive(s, o, p, label_by_id)
            mapped.append((ms, mr, me, role, url))
        else:
            edge = claim_to_edge(s, o, p, label_by_id)
            if edge:
                ms, mr, me = edge
                mapped.append((ms, mr, me, "", url))

    source = "https://www.wikidata.org/ (isolated-node enrich aggressive)" if args.aggressive else "https://www.wikidata.org/ (isolated-node enrich)"
    merged = merge_relations(existing, mapped, source=source, confidence=args.confidence)
    write_relations_csv(args.out, merged)

    print(f"Total nodes:        {len(all_qids)}")
    print(f"Target nodes:       {len(target_qids)} (degree <= {args.min_degree})")
    print(f"Raw claims (subj):  {len(raw_subject)}")
    print(f"Raw claims (obj):   {len(raw_object)}")
    print(f"Mapped new edges:   {len(mapped)}")
    print(f"Relations written:  {len(merged)} -> {args.out}")


if __name__ == "__main__":
    main()
