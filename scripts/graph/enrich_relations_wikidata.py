"""
Add relations between entities that already appear in nodes_final.csv by querying
direct Wikidata statements (P*) whose object is another Q-id in the same node set.

Merges with an existing relations CSV (same columns as relations_final.csv) and
deduplicates on (start_id, relation, end_id, year, role).
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
USER_AGENT = "turing-kg-course-project/0.1 (educational use; relation enrichment)"


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
    """
    Map one Wikidata direct claim to an ontology edge (start, relation, end).
    Returns None if the property is not mapped or types look incompatible.
    """
    pid = pid_from_uri(prop_uri)
    if not pid:
        return None

    ls = label_by_id.get(subject_qid, "")
    lo = label_by_id.get(object_qid, "")

    # P50: author — on work, points to person
    if pid == "P50":
        if ls == "Work" and lo == "Person":
            return (object_qid, "AUTHORED", subject_qid)
        return None

    # P800: notable work — person -> work
    if pid == "P800":
        if ls == "Person" and lo == "Work":
            return (subject_qid, "AUTHORED", object_qid)
        return None

    # Education / employment / membership
    if pid in ("P69", "P108", "P463", "P102", "P1416"):
        if ls == "Person" and lo == "Organization":
            return (subject_qid, "AFFILIATED_WITH", object_qid)
        return None

    # P737: influenced by — subject influenced by object => object INFLUENCED subject
    if pid == "P737":
        if ls == "Person" and lo == "Person":
            return (object_qid, "INFLUENCED", subject_qid)
        return None

    # P921: main subject of work
    if pid == "P921":
        if ls == "Work" and lo in ("Concept", "Work", "Organization", "Person", "Place"):
            return (subject_qid, "INTRODUCES", object_qid)
        return None

    # Country (organization)
    if pid == "P17":
        if ls == "Organization" and lo == "Place":
            return (subject_qid, "LOCATED_IN", object_qid)
        if ls == "Person" and lo == "Place":
            return (subject_qid, "AFFILIATED_WITH", object_qid)
        return None

    # Headquarters, publication location, generic location
    if pid in ("P159", "P937", "P131", "P276"):
        if ls == "Organization" and lo == "Place":
            return (subject_qid, "LOCATED_IN", object_qid)
        if ls == "Work" and lo == "Place":
            return (subject_qid, "LOCATED_IN", object_qid)
        if ls == "Place" and lo == "Place":
            return (subject_qid, "LOCATED_IN", object_qid)
        return None

    # Biographical (not in ontology.md but useful for dense graphs)
    if pid == "P19" and ls == "Person" and lo == "Place":
        return (subject_qid, "BORN_IN", object_qid)
    if pid == "P20" and ls == "Person" and lo == "Place":
        return (subject_qid, "DIED_IN", object_qid)
    if pid == "P551" and ls == "Person" and lo == "Place":
        return (subject_qid, "RESIDED_IN", object_qid)

    return None


def fetch_interconnecting_claims(
    qids: List[str],
    batch_size: int,
    pause_sec: float,
) -> List[Tuple[str, str, str]]:
    """Return list of (subject_qid, full_prop_uri, object_qid) for Q->Q direct claims."""
    out: List[Tuple[str, str, str]] = []
    qid_set = set(qids)
    for i in range(0, len(qids), batch_size):
        batch = qids[i : i + batch_size]
        values = " ".join(f"wd:{q}" for q in batch)
        query = f"""
        SELECT ?s ?p ?o WHERE {{
          VALUES ?s {{ {values} }}
          ?s ?p ?o .
          FILTER(STRSTARTS(STR(?p), "http://www.wikidata.org/prop/direct/"))
          FILTER(STRSTARTS(STR(?o), "http://www.wikidata.org/entity/Q"))
        }}
        """
        rows = run_sparql(query)
        for row in rows:
            sq = qid_from_uri(wd_value(row, "s"))
            pq = wd_value(row, "p")
            oq = qid_from_uri(wd_value(row, "o"))
            if not sq or not pq or not oq:
                continue
            if oq not in qid_set:
                continue
            if sq == oq:
                continue
            out.append((sq, pq, oq))
        if pause_sec > 0 and i + batch_size < len(qids):
            time.sleep(pause_sec)
    return out


def merge_relations(
    existing: List[Dict[str, str]],
    new_edges: Iterable[Tuple[str, str, str, str]],
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

    for s, r, e, source_url in new_edges:
        y, role = "", ""
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
        description="Enrich relations by pulling Wikidata Q-Q claims among nodes in a CSV."
    )
    parser.add_argument("--nodes", default="data/final/nodes_final.csv", help="Nodes CSV with id + label")
    parser.add_argument(
        "--existing",
        default="data/final/relations_final.csv",
        help="Current relations CSV to merge (may be empty file with header only)",
    )
    parser.add_argument(
        "--out",
        default="data/final/relations_final.csv",
        help="Output relations CSV path",
    )
    parser.add_argument("--batch-size", type=int, default=35, help="VALUES ?s batch size for SPARQL")
    parser.add_argument(
        "--pause",
        type=float,
        default=1.0,
        help="Seconds to sleep between SPARQL batches (be polite to Wikidata)",
    )
    parser.add_argument(
        "--confidence",
        default="0.82",
        help="Confidence string for newly added edges",
    )
    args = parser.parse_args()

    nodes = read_csv(args.nodes)
    label_by_id: Dict[str, str] = {r["id"]: r.get("label", "") for r in nodes if r.get("id")}
    qids = sorted(label_by_id.keys())

    existing: List[Dict[str, str]] = []
    if os.path.isfile(args.existing):
        existing = read_csv(args.existing)

    raw = fetch_interconnecting_claims(qids, args.batch_size, args.pause)
    edges: List[Tuple[str, str, str, str]] = []
    for sq, prop_uri, oq in raw:
        edge = claim_to_edge(sq, oq, prop_uri, label_by_id)
        if edge:
            s, r, e = edge
            url = f"https://www.wikidata.org/wiki/{sq}"
            edges.append((s, r, e, url))

    source = "https://www.wikidata.org/ (entity subgraph)"
    merged = merge_relations(existing, edges, source=source, confidence=args.confidence)

    write_relations_csv(args.out, merged)
    print(f"Nodes in scope:     {len(qids)}")
    print(f"Raw Q-Q claims:     {len(raw)}")
    print(f"Mapped new edges:   {len(edges)}")
    print(f"Relations written:  {len(merged)} -> {args.out}")


if __name__ == "__main__":
    main()
