import argparse
import csv
import os
import re
from typing import Dict, List, Tuple


KEEP_LABELS = {"PERSON", "ORG", "GPE", "WORK_OF_ART", "CONCEPT"}

LEADING_STOPWORDS = (
    "the ",
    "a ",
    "an ",
    "on ",
    "in ",
    "when ",
    "however ",
)

NOISE_SINGLE_TOKENS = {
    "next",
}

KNOWN_PERSONS = {
    "alan turing",
    "julius mathison turing",
    "ethel sara stoney",
    "christopher morcom",
    "gordon brown",
    "newman",
    "hitler",
    "w g welchman",
    "mathison turing",
    "morcom",
    "turing",
}

KNOWN_ORGS = {
    "king's college",
    "princeton university",
    "university of manchester",
    "bletchley park",
    "indian civil service",
    "national physical laboratory",
    "moral science club",
    "royal society",
    "walton athletic club",
    "cypher school",
}

KNOWN_GPE = {
    "london",
    "paddington",
    "england",
    "cambridge",
    "germany",
    "india",
    "greece",
    "united states",
    "britain",
    "sherborne",
    "manchester",
    "princeton",
    "bletchley",
}

KNOWN_CONCEPTS = {
    "turing machine",
    "church-turing thesis",
    "computability",
    "quantum mechanics",
    "artificial intelligence",
    "enigma",
    "entscheidungsproblem",
    "turing test",
}

KNOWN_WORKS = {
    "on computable numbers",
    "computing machinery and intelligence",
    "biographical memoirs",
}

LABEL_PRIORITY = {
    "PERSON": 1,
    "ORG": 2,
    "GPE": 3,
    "WORK_OF_ART": 4,
    "CONCEPT": 5,
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def normalize_key(text: str) -> str:
    return normalize_text(text).lower()


def strip_leading_noise(text: str) -> str:
    t = normalize_text(text)
    t_low = t.lower()
    changed = True
    while changed:
        changed = False
        for prefix in LEADING_STOPWORDS:
            if t_low.startswith(prefix):
                t = t[len(prefix):].strip()
                t_low = t.lower()
                changed = True
                break
    t = re.sub(r"'s$", "", t, flags=re.IGNORECASE).strip()
    return t


def classify_override(mention_norm: str, label: str) -> str:
    if mention_norm in KNOWN_PERSONS:
        return "PERSON"
    if mention_norm in KNOWN_ORGS:
        return "ORG"
    if mention_norm in KNOWN_GPE:
        return "GPE"
    if mention_norm in KNOWN_WORKS:
        return "WORK_OF_ART"
    if mention_norm in KNOWN_CONCEPTS:
        return "CONCEPT"
    return label


def to_int(value: str) -> int:
    try:
        return int(value)
    except Exception:
        return 10**9


def read_rows(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path: str, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def refine(rows: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]]]:
    refined: List[Dict[str, str]] = []
    review: List[Dict[str, str]] = []
    dropped: List[Dict[str, str]] = []

    for row in rows:
        mention = normalize_text(row.get("mention", ""))
        label = row.get("label", "").strip()
        start = row.get("start", "").strip()
        end = row.get("end", "").strip()
        method = row.get("method", "").strip()

        if label not in KEEP_LABELS and label != "CANDIDATE":
            dropped.append(
                {
                    "mention": mention,
                    "label": label,
                    "start": start,
                    "end": end,
                    "method": method,
                    "reason": "unsupported_label",
                }
            )
            continue

        mention = strip_leading_noise(mention)
        mention_norm = normalize_key(mention)

        if not mention_norm:
            dropped.append(
                {
                    "mention": mention,
                    "label": label,
                    "start": start,
                    "end": end,
                    "method": method,
                    "reason": "empty_after_normalization",
                }
            )
            continue

        if mention_norm in NOISE_SINGLE_TOKENS:
            dropped.append(
                {
                    "mention": mention,
                    "label": label,
                    "start": start,
                    "end": end,
                    "method": method,
                    "reason": "noise_single_token",
                }
            )
            continue

        # Hard correction with domain dictionaries.
        final_label = classify_override(mention_norm, label)

        # Candidate handling: route unknown candidates to manual review.
        if final_label == "CANDIDATE":
            if mention_norm in KNOWN_CONCEPTS:
                final_label = "CONCEPT"
            elif mention_norm in KNOWN_WORKS:
                final_label = "WORK_OF_ART"
            elif mention_norm in KNOWN_ORGS:
                final_label = "ORG"
            elif mention_norm in KNOWN_GPE:
                final_label = "GPE"
            elif mention_norm in KNOWN_PERSONS:
                final_label = "PERSON"
            else:
                review.append(
                    {
                        "mention": mention,
                        "mention_norm": mention_norm,
                        "label": label,
                        "start": start,
                        "end": end,
                        "method": method,
                        "reason": "candidate_needs_manual_review",
                    }
                )
                continue

        refined.append(
            {
                "mention": mention,
                "mention_norm": mention_norm,
                "label": final_label,
                "start": start,
                "end": end,
                "method": method,
            }
        )

    # Deduplicate by (mention_norm), keep label by priority then earliest start.
    best_by_mention: Dict[str, Dict[str, str]] = {}
    for row in refined:
        key = row["mention_norm"]
        if key not in best_by_mention:
            best_by_mention[key] = row
            continue

        old = best_by_mention[key]
        old_p = LABEL_PRIORITY.get(old["label"], 999)
        new_p = LABEL_PRIORITY.get(row["label"], 999)
        if new_p < old_p:
            best_by_mention[key] = row
        elif new_p == old_p and to_int(row["start"]) < to_int(old["start"]):
            best_by_mention[key] = row

    refined_rows = sorted(best_by_mention.values(), key=lambda x: (x["label"], x["mention_norm"]))
    review_rows = sorted(review, key=lambda x: (x["label"], x["mention_norm"]))
    dropped_rows = sorted(dropped, key=lambda x: (x["reason"], x["mention"]))
    return refined_rows, review_rows, dropped_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="进一步清洗实体结果（精清洗）。")
    parser.add_argument("--input", default="data/processed/entities_clean.csv", help="初步清洗结果 CSV")
    parser.add_argument("--out", default="data/processed", help="输出目录")
    args = parser.parse_args()

    rows = read_rows(args.input)
    refined_rows, review_rows, dropped_rows = refine(rows)

    refined_path = os.path.join(args.out, "entities_refined.csv")
    review_path = os.path.join(args.out, "entities_review.csv")
    dropped_path = os.path.join(args.out, "entities_dropped.csv")

    write_rows(
        refined_path,
        ["mention", "mention_norm", "label", "start", "end", "method"],
        refined_rows,
    )
    write_rows(
        review_path,
        ["mention", "mention_norm", "label", "start", "end", "method", "reason"],
        review_rows,
    )
    write_rows(
        dropped_path,
        ["mention", "label", "start", "end", "method", "reason"],
        dropped_rows,
    )

    print(f"Input rows:    {len(rows)}")
    print(f"Refined rows:  {len(refined_rows)} -> {refined_path}")
    print(f"Review rows:   {len(review_rows)} -> {review_path}")
    print(f"Dropped rows:  {len(dropped_rows)} -> {dropped_path}")


if __name__ == "__main__":
    main()
