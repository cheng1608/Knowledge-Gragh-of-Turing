import argparse
import csv
import os
import time
from typing import Dict, List, Optional, Set, Tuple

import requests


SPARQL_URL = "https://query.wikidata.org/sparql"
TURING_QID = "Q7251"


def run_sparql(query: str, retries: int = 3, sleep_sec: int = 2) -> List[dict]:
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "turing-kg-course-project/0.1 (educational use)",
    }
    for i in range(retries):
        try:
            resp = requests.get(
                SPARQL_URL,
                params={"query": query, "format": "json"},
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["results"]["bindings"]
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(sleep_sec)
    return []


def wd_value(row: dict, key: str) -> Optional[str]:
    if key not in row:
        return None
    return row[key].get("value")


def qid_from_uri(uri: Optional[str]) -> Optional[str]:
    if not uri or "/entity/" not in uri:
        return None
    return uri.rsplit("/", 1)[-1]


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def query_people_orgs_works() -> List[dict]:
    query = f"""
    SELECT DISTINCT ?person ?personLabel ?birthYear ?deathYear
                    ?org ?orgLabel ?countryLabel
                    ?work ?workLabel ?workYear
    WHERE {{
      BIND(wd:{TURING_QID} AS ?person)
      OPTIONAL {{
        ?person wdt:P569 ?birth.
        BIND(YEAR(?birth) AS ?birthYear)
      }}
      OPTIONAL {{
        ?person wdt:P570 ?death.
        BIND(YEAR(?death) AS ?deathYear)
      }}

      OPTIONAL {{
        ?person (wdt:P69|wdt:P108) ?org.
        OPTIONAL {{ ?org wdt:P17 ?country. }}
      }}

      OPTIONAL {{
        ?person wdt:P800 ?work.
        OPTIONAL {{
          ?work wdt:P577 ?pubDate.
          BIND(YEAR(?pubDate) AS ?workYear)
        }}
      }}

      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,zh". }}
    }}
    """
    return run_sparql(query)


def query_influenced_people() -> List[dict]:
    query = f"""
    SELECT DISTINCT ?other ?otherLabel
    WHERE {{
      ?other wdt:P737 wd:{TURING_QID}.
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,zh". }}
    }}
    """
    return run_sparql(query)


def query_work_concepts() -> List[dict]:
    query = f"""
    SELECT DISTINCT ?work ?workLabel ?concept ?conceptLabel
    WHERE {{
      wd:{TURING_QID} wdt:P800 ?work.
      OPTIONAL {{ ?work wdt:P921 ?concept. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,zh". }}
    }}
    """
    return run_sparql(query)


def query_places() -> List[dict]:
    query = f"""
    SELECT DISTINCT ?place ?placeLabel ?countryLabel
    WHERE {{
      {{
        wd:{TURING_QID} wdt:P19 ?place.
      }}
      UNION
      {{
        wd:{TURING_QID} wdt:P20 ?place.
      }}
      OPTIONAL {{ ?place wdt:P17 ?country. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,zh". }}
    }}
    """
    return run_sparql(query)


def add_node(nodes: Dict[str, dict], node_id: str, label: str, name: str, **kwargs) -> None:
    if node_id in nodes:
        nodes[node_id].update({k: v for k, v in kwargs.items() if v not in (None, "")})
        return
    row = {
        "id": node_id,
        "label": label,
        "name": name,
        "birthYear": "",
        "deathYear": "",
        "year": "",
        "type": "",
        "country": "",
        "description": "",
        "source": "https://www.wikidata.org/",
    }
    row.update({k: v for k, v in kwargs.items() if v not in (None, "")})
    nodes[node_id] = row


def add_rel(rels: Set[Tuple[str, str, str, str, str, str]], start: str, relation: str, end: str, year: str = "", role: str = "", source: str = "https://www.wikidata.org/") -> None:
    rels.add((start, relation, end, year, role, source))


def build_graph() -> Tuple[List[dict], List[dict]]:
    nodes: Dict[str, dict] = {}
    rels: Set[Tuple[str, str, str, str, str, str]] = set()

    porw = query_people_orgs_works()
    influenced = query_influenced_people()
    work_concepts = query_work_concepts()
    places = query_places()

    add_node(
        nodes,
        TURING_QID,
        "Person",
        "Alan Turing",
    )

    for row in porw:
        person_qid = qid_from_uri(wd_value(row, "person"))
        if person_qid:
            add_node(
                nodes,
                person_qid,
                "Person",
                wd_value(row, "personLabel") or "Alan Turing",
                birthYear=str(int(float(wd_value(row, "birthYear")))) if wd_value(row, "birthYear") else "",
                deathYear=str(int(float(wd_value(row, "deathYear")))) if wd_value(row, "deathYear") else "",
            )

        org_qid = qid_from_uri(wd_value(row, "org"))
        if org_qid:
            add_node(
                nodes,
                org_qid,
                "Organization",
                wd_value(row, "orgLabel") or org_qid,
                country=wd_value(row, "countryLabel") or "",
            )
            add_rel(rels, TURING_QID, "AFFILIATED_WITH", org_qid)

        work_qid = qid_from_uri(wd_value(row, "work"))
        if work_qid:
            work_year = ""
            if wd_value(row, "workYear"):
                work_year = str(int(float(wd_value(row, "workYear"))))
            add_node(
                nodes,
                work_qid,
                "Work",
                wd_value(row, "workLabel") or work_qid,
                year=work_year,
            )
            add_rel(rels, TURING_QID, "AUTHORED", work_qid, year=work_year)

    for row in influenced:
        other_qid = qid_from_uri(wd_value(row, "other"))
        if not other_qid:
            continue
        add_node(nodes, other_qid, "Person", wd_value(row, "otherLabel") or other_qid)
        add_rel(rels, TURING_QID, "INFLUENCED", other_qid)

    for row in work_concepts:
        work_qid = qid_from_uri(wd_value(row, "work"))
        concept_qid = qid_from_uri(wd_value(row, "concept"))
        if not work_qid or not concept_qid:
            continue
        add_node(nodes, work_qid, "Work", wd_value(row, "workLabel") or work_qid)
        add_node(nodes, concept_qid, "Concept", wd_value(row, "conceptLabel") or concept_qid)
        add_rel(rels, work_qid, "INTRODUCES", concept_qid)
        # Heuristic: if Turing's notable work introduces a concept, map as proposed.
        add_rel(rels, TURING_QID, "PROPOSED", concept_qid, source="https://www.wikidata.org/ (heuristic)")

    for row in places:
        place_qid = qid_from_uri(wd_value(row, "place"))
        if not place_qid:
            continue
        add_node(
            nodes,
            place_qid,
            "Place",
            wd_value(row, "placeLabel") or place_qid,
            country=wd_value(row, "countryLabel") or "",
        )

    node_rows = sorted(nodes.values(), key=lambda x: (x["label"], x["name"]))
    rel_rows = [
        {
            "start_id": s,
            "relation": r,
            "end_id": e,
            "year": y,
            "role": role,
            "source": src,
        }
        for (s, r, e, y, role, src) in sorted(rels)
    ]
    return node_rows, rel_rows


def write_csv(path: str, fieldnames: List[str], rows: List[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Turing KG seed data from Wikidata.")
    parser.add_argument("--out", default="data/processed", help="Output folder for CSV files")
    args = parser.parse_args()

    ensure_dir(args.out)

    nodes, rels = build_graph()
    nodes_path = os.path.join(args.out, "nodes.csv")
    rels_path = os.path.join(args.out, "relations.csv")

    write_csv(
        nodes_path,
        ["id", "label", "name", "birthYear", "deathYear", "year", "type", "country", "description", "source"],
        nodes,
    )
    write_csv(
        rels_path,
        ["start_id", "relation", "end_id", "year", "role", "source"],
        rels,
    )

    print(f"Done. Nodes: {len(nodes)} -> {nodes_path}")
    print(f"Done. Relations: {len(rels)} -> {rels_path}")


if __name__ == "__main__":
    main()
