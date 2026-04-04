import argparse
import csv
import os
import re
from typing import Dict, List, Tuple


LABEL_TO_SCHEMA = {
    "PERSON": "Person",
    "ORG": "Organization",
    "GPE": "Place",
    "WORK_OF_ART": "Work",
    "CONCEPT": "Concept",
}

SCHEMA_PREFIX = {
    "Person": "PER",
    "Organization": "ORG",
    "Place": "PLC",
    "Work": "WRK",
    "Concept": "CPT",
}

# Some mentions need domain-level correction before schema mapping.
MENTION_LABEL_OVERRIDES = {
    "computable numbers": "WORK_OF_ART",
    "ace": "CONCEPT",
    "o.b.e.": "CONCEPT",
    "public school": "CONCEPT",
    "scientific specialist": "CONCEPT",
    "common entrance examination": "CONCEPT",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def normalize_key(text: str) -> str:
    return normalize_text(text).lower()


def read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: str, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def align_refined_rows(rows: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    aligned_raw: List[Dict[str, str]] = []
    dropped: List[Dict[str, str]] = []

    for row in rows:
        mention = normalize_text(row.get("mention", ""))
        mention_norm = normalize_key(mention)
        label = row.get("label", "").strip()
        start = row.get("start", "").strip()
        end = row.get("end", "").strip()
        method = row.get("method", "").strip()

        label = MENTION_LABEL_OVERRIDES.get(mention_norm, label)
        schema_label = LABEL_TO_SCHEMA.get(label)
        if not schema_label:
            dropped.append(
                {
                    "mention": mention,
                    "mention_norm": mention_norm,
                    "label": label,
                    "reason": "no_schema_mapping",
                }
            )
            continue

        aligned_raw.append(
            {
                "name": mention,
                "name_norm": mention_norm,
                "schema_label": schema_label,
                "source": "MacTutor",
                "source_detail": "entities_refined.csv",
                "method": method,
                "start": start,
                "end": end,
            }
        )

    # De-dup by (schema_label, name_norm) and keep earliest mention.
    best: Dict[Tuple[str, str], Dict[str, str]] = {}
    for row in aligned_raw:
        key = (row["schema_label"], row["name_norm"])
        if key not in best:
            best[key] = row
            continue
        old = best[key]
        try:
            if int(row["start"]) < int(old["start"]):
                best[key] = row
        except Exception:
            pass

    deduped = sorted(best.values(), key=lambda x: (x["schema_label"], x["name_norm"]))

    # Create IDs
    counters = {k: 0 for k in SCHEMA_PREFIX}
    final_rows = []
    for row in deduped:
        schema_label = row["schema_label"]
        counters[schema_label] += 1
        entity_id = f"{SCHEMA_PREFIX[schema_label]}_{counters[schema_label]:03d}"
        final_rows.append(
            {
                "id": entity_id,
                "label": schema_label,
                "name": row["name"],
                "name_norm": row["name_norm"],
                "source": row["source"],
                "source_detail": row["source_detail"],
                "method": row["method"],
                "confidence": "0.70",
            }
        )
    return final_rows, dropped


def suggest_label_for_candidate(mention_norm: str) -> str:
    if any(k in mention_norm for k in ("test", "machine", "problem", "code", "engine", "theory")):
        return "Concept"
    if any(k in mention_norm for k in ("university", "school", "club", "society", "laboratory")):
        return "Organization"
    if any(k in mention_norm for k in ("london", "england", "germany", "india", "states")):
        return "Place"
    return "UNRESOLVED"


def align_review_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for row in rows:
        mention = normalize_text(row.get("mention", ""))
        mention_norm = normalize_key(mention)
        out.append(
            {
                "mention": mention,
                "mention_norm": mention_norm,
                "original_label": row.get("label", ""),
                "suggested_schema_label": suggest_label_for_candidate(mention_norm),
                "reason": row.get("reason", ""),
            }
        )
    return sorted(out, key=lambda x: x["mention_norm"])


def main() -> None:
    parser = argparse.ArgumentParser(description="对齐实体类型到知识图谱 schema。")
    parser.add_argument("--input", default="data/processed/entities_refined.csv", help="精清洗实体 CSV")
    parser.add_argument("--review", default="data/processed/entities_review.csv", help="待复核实体 CSV")
    parser.add_argument("--out", default="data/processed", help="输出目录")
    parser.add_argument("--drop_review", action="store_true", help="将待人工复核项全部丢弃")
    args = parser.parse_args()

    refined_rows = read_csv(args.input)
    review_rows = read_csv(args.review) if os.path.exists(args.review) else []

    aligned_rows, dropped_rows = align_refined_rows(refined_rows)
    review_aligned_rows = align_review_rows(review_rows)

    if args.drop_review:
        for row in review_aligned_rows:
            dropped_rows.append(
                {
                    "mention": row["mention"],
                    "mention_norm": row["mention_norm"],
                    "label": row["original_label"],
                    "reason": "manual_review_dropped",
                }
            )
        review_aligned_rows = []

    aligned_path = os.path.join(args.out, "entities_schema_aligned.csv")
    dropped_path = os.path.join(args.out, "entities_schema_dropped.csv")
    review_path = os.path.join(args.out, "entities_schema_review.csv")

    write_csv(
        aligned_path,
        ["id", "label", "name", "name_norm", "source", "source_detail", "method", "confidence"],
        aligned_rows,
    )
    write_csv(
        dropped_path,
        ["mention", "mention_norm", "label", "reason"],
        dropped_rows,
    )
    write_csv(
        review_path,
        ["mention", "mention_norm", "original_label", "suggested_schema_label", "reason"],
        review_aligned_rows,
    )

    print(f"Refined input:     {len(refined_rows)}")
    print(f"Schema aligned:    {len(aligned_rows)} -> {aligned_path}")
    print(f"Schema dropped:    {len(dropped_rows)} -> {dropped_path}")
    print(f"Schema review:     {len(review_aligned_rows)} -> {review_path}")


if __name__ == "__main__":
    main()
