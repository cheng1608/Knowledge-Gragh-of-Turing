import argparse
import csv
import os
import time
from typing import Dict, List, Optional, Tuple

import requests


SEARCH_API = "https://www.wikidata.org/w/api.php"
ENTITY_DATA_API = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
HTTP_HEADERS = {
    "User-Agent": "turing-kg-course-project/0.1 (educational use)",
    "Accept": "application/json",
}

# 只做课程项目所需的粗粒度类型映射。
TYPE_QIDS = {
    "Person": {"Q5"},
    "Organization": {
        "Q43229",   # organization
        "Q2385804", # educational institution
        "Q4830453", # business
        "Q7278",    # political party
        "Q784159",  # association
        "Q15911314" # committee
    },
    "Place": {
        "Q6256",    # country
        "Q515",     # city
        "Q82794",   # geographic region
        "Q17334923",# location
        "Q618123",  # georgraphical object
        "Q486972",  # human settlement
    },
    "Work": {
        "Q13442814", # scholarly article
        "Q571",      # book
        "Q7725634",  # literary work
        "Q47461344", # written work
        "Q17537576", # creative work
    },
    "Concept": {
        "Q151885",   # concept
        "Q17444909", # scientific theory
        "Q24034552", # model
        "Q11862829", # academic discipline
        "Q21198",    # computer science
    },
}

DESC_KEYWORDS = {
    "Person": ["mathematician", "computer scientist", "person", "scientist"],
    "Organization": ["university", "organization", "school", "institute", "laboratory", "society"],
    "Place": ["city", "country", "town", "village", "region", "place"],
    "Work": ["paper", "book", "work", "article"],
    "Concept": ["concept", "theory", "problem", "machine", "test", "idea"],
}


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: str, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def search_candidates(name: str, limit: int = 5) -> List[Dict]:
    params = {
        "action": "wbsearchentities",
        "format": "json",
        "language": "en",
        "search": name,
        "limit": limit,
    }
    resp = safe_get(SEARCH_API, params=params, timeout=30)
    return resp.json().get("search", [])


def get_instance_of_qids(qid: str) -> List[str]:
    url = ENTITY_DATA_API.format(qid=qid)
    resp = safe_get(url, timeout=30)
    data = resp.json().get("entities", {}).get(qid, {})
    claims = data.get("claims", {})
    p31_claims = claims.get("P31", [])
    out: List[str] = []
    for claim in p31_claims:
        try:
            target_qid = (
                claim["mainsnak"]["datavalue"]["value"]["id"]
            )
            if target_qid:
                out.append(target_qid)
        except Exception:
            continue
    return out


def safe_get(url: str, params: Optional[Dict] = None, timeout: int = 30, retries: int = 3) -> requests.Response:
    last_err = None
    for i in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout, headers=HTTP_HEADERS)
            resp.raise_for_status()
            return resp
        except Exception as e:
            # 403 is usually policy/user-agent related; no need to retry repeatedly.
            if "403" in str(e):
                raise
            last_err = e
            if i < retries - 1:
                time.sleep(1.5 * (i + 1))
    raise last_err  # type: ignore[misc]


def score_candidate(
    mention: str,
    expected_label: str,
    candidate: Dict,
    instance_qids: List[str],
    rank_idx: int,
) -> float:
    score = 0.0
    candidate_label = (candidate.get("label") or "").strip().lower()
    candidate_desc = (candidate.get("description") or "").strip().lower()
    mention_norm = mention.strip().lower()

    if candidate_label == mention_norm:
        score += 0.6
    elif mention_norm in candidate_label or candidate_label in mention_norm:
        score += 0.25

    # 类型匹配加分
    expected_qids = TYPE_QIDS.get(expected_label, set())
    if any(q in expected_qids for q in instance_qids):
        score += 0.6

    # 描述关键词加分
    for kw in DESC_KEYWORDS.get(expected_label, []):
        if kw in candidate_desc:
            score += 0.05

    # 搜索结果越靠前，基础分越高
    score += max(0.0, 0.2 - 0.03 * rank_idx)
    return score


def link_entity(row: Dict[str, str], score_threshold: float) -> Tuple[Optional[Dict[str, str]], Optional[Dict[str, str]]]:
    mention = row["name"]
    expected_label = row["label"]
    try:
        candidates = search_candidates(mention, limit=5)
    except Exception as e:
        return None, {
            "id": row["id"],
            "name": mention,
            "label": expected_label,
            "reason": f"network_error_search({str(e)[:80]})",
            "top_qid": "",
            "top_label": "",
        }

    if not candidates:
        return None, {
            "id": row["id"],
            "name": mention,
            "label": expected_label,
            "reason": "no_candidate_found",
        }

    best = None
    best_score = -1.0
    best_instance_qids: List[str] = []

    for idx, c in enumerate(candidates):
        qid = c.get("id")
        if not qid:
            continue
        try:
            instance_qids = get_instance_of_qids(qid)
        except Exception:
            instance_qids = []
        score = score_candidate(mention, expected_label, c, instance_qids, idx)
        if score > best_score:
            best = c
            best_score = score
            best_instance_qids = instance_qids

    if not best:
        return None, {
            "id": row["id"],
            "name": mention,
            "label": expected_label,
            "reason": "candidate_scoring_failed",
        }

    if best_score < score_threshold:
        return None, {
            "id": row["id"],
            "name": mention,
            "label": expected_label,
            "reason": f"low_confidence({best_score:.2f})",
            "top_qid": best.get("id", ""),
            "top_label": best.get("label", ""),
        }

    linked = {
        "id": row["id"],
        "label": expected_label,
        "name": mention,
        "wikidata_qid": best.get("id", ""),
        "wikidata_label": best.get("label", ""),
        "wikidata_description": best.get("description", ""),
        "link_score": f"{best_score:.3f}",
        "instance_of_qids": "|".join(best_instance_qids),
        "source": row.get("source", "MacTutor"),
        "method": "wikidata_entity_linking",
    }
    return linked, None


def main() -> None:
    parser = argparse.ArgumentParser(description="实体消歧并链接到 Wikidata QID。")
    parser.add_argument("--input", default="data/processed/entities_schema_aligned.csv", help="schema 对齐后的实体 CSV")
    parser.add_argument("--out", default="data/processed", help="输出目录")
    parser.add_argument("--threshold", type=float, default=0.75, help="链接分数阈值")
    args = parser.parse_args()

    rows = read_csv(args.input)
    linked_rows: List[Dict[str, str]] = []
    unlinked_rows: List[Dict[str, str]] = []

    for row in rows:
        linked, unlinked = link_entity(row, args.threshold)
        if linked:
            linked_rows.append(linked)
        elif unlinked:
            unlinked_rows.append(unlinked)

    linked_path = os.path.join(args.out, "entities_linked.csv")
    unlinked_path = os.path.join(args.out, "entities_unlinked.csv")

    write_csv(
        linked_path,
        [
            "id",
            "label",
            "name",
            "wikidata_qid",
            "wikidata_label",
            "wikidata_description",
            "link_score",
            "instance_of_qids",
            "source",
            "method",
        ],
        linked_rows,
    )
    write_csv(
        unlinked_path,
        ["id", "name", "label", "reason", "top_qid", "top_label"],
        unlinked_rows,
    )

    print(f"Input rows:     {len(rows)}")
    print(f"Linked rows:    {len(linked_rows)} -> {linked_path}")
    print(f"Unlinked rows:  {len(unlinked_rows)} -> {unlinked_path}")


if __name__ == "__main__":
    main()
