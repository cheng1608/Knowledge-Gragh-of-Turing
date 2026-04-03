import argparse
import csv
import os
import re
from typing import Dict, List, Tuple


LABEL_PRIORITY = {
    "PERSON": 1,
    "ORG": 2,
    "GPE": 3,
    "WORK_OF_ART": 4,
    "CONCEPT": 5,
    "CANDIDATE": 6,
    "DATE": 7,
}

NOISE_TERMS = {
    "skip to content",
    "view seven larger pictures",
    "quick info",
    "summary",
    "biography",
    "references",
    "additional resources",
    "cross-references",
    "honours",
}


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def normalize_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_key(text: str) -> str:
    return normalize_text(text).lower()


def is_noise(mention_norm: str) -> bool:
    if not mention_norm:
        return True
    if mention_norm in {"none", "nan", "null"}:
        return True
    if mention_norm in NOISE_TERMS:
        return True
    # only punctuation/symbols
    if re.fullmatch(r"[\W_]+", mention_norm):
        return True
    return False


def read_entities(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def clean_entities(rows: List[Dict[str, str]], min_len: int) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, str]]]:
    noise_rows: List[Dict[str, str]] = []
    date_rows: List[Dict[str, str]] = []
    valid_rows: List[Dict[str, str]] = []

    for row in rows:
        mention = normalize_text(row.get("mention", ""))
        label = row.get("label", "").strip()
        start = row.get("start", "").strip()
        end = row.get("end", "").strip()
        method = row.get("method", "").strip()
        mention_norm = normalize_key(mention)

        current = {
            "mention": mention,
            "mention_norm": mention_norm,
            "label": label,
            "start": start,
            "end": end,
            "method": method,
        }

        if is_noise(mention_norm):
            current["reason"] = "noise_term_or_empty"
            noise_rows.append(current)
            continue

        if len(mention_norm) < min_len:
            current["reason"] = "too_short"
            noise_rows.append(current)
            continue

        if label == "DATE":
            date_rows.append(current)
            continue

        valid_rows.append(current)

    # Resolve label conflicts on same mention_norm by priority.
    best_by_mention: Dict[str, Dict[str, str]] = {}
    for row in valid_rows:
        key = row["mention_norm"]
        if key not in best_by_mention:
            best_by_mention[key] = row
            continue

        old = best_by_mention[key]
        old_p = LABEL_PRIORITY.get(old["label"], 999)
        new_p = LABEL_PRIORITY.get(row["label"], 999)

        if new_p < old_p:
            best_by_mention[key] = row
        elif new_p == old_p:
            # keep earlier position if same label priority
            try:
                if int(row["start"]) < int(old["start"]):
                    best_by_mention[key] = row
            except Exception:
                pass

    clean_rows = sorted(best_by_mention.values(), key=lambda x: (x["label"], x["mention_norm"]))
    noise_rows = sorted(noise_rows, key=lambda x: x["mention_norm"])
    date_rows = sorted(date_rows, key=lambda x: int(x["start"]) if x["start"].isdigit() else 10**9)
    return clean_rows, noise_rows, date_rows


def write_csv(path: str, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="初步清洗实体抽取结果。")
    parser.add_argument("--input", default="data/processed/entities_raw.csv", help="实体抽取原始结果 CSV")
    parser.add_argument("--out", default="data/processed", help="输出目录")
    parser.add_argument("--min_len", type=int, default=3, help="最短实体长度（标准化后）")
    args = parser.parse_args()

    ensure_dir(args.out)
    rows = read_entities(args.input)
    clean_rows, noise_rows, date_rows = clean_entities(rows, args.min_len)

    clean_path = os.path.join(args.out, "entities_clean.csv")
    noise_path = os.path.join(args.out, "entities_noise.csv")
    date_path = os.path.join(args.out, "date_mentions.csv")

    write_csv(
        clean_path,
        ["mention", "mention_norm", "label", "start", "end", "method"],
        clean_rows,
    )
    write_csv(
        noise_path,
        ["mention", "mention_norm", "label", "start", "end", "method", "reason"],
        noise_rows,
    )
    write_csv(
        date_path,
        ["mention", "mention_norm", "label", "start", "end", "method"],
        date_rows,
    )

    print(f"Input rows:   {len(rows)}")
    print(f"Clean rows:   {len(clean_rows)} -> {clean_path}")
    print(f"Noise rows:   {len(noise_rows)} -> {noise_path}")
    print(f"Date rows:    {len(date_rows)} -> {date_path}")


if __name__ == "__main__":
    main()
