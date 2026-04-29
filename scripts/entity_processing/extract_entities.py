import argparse
import csv
import os
import re
from collections import defaultdict
from typing import Dict, List, Tuple


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def rule_based_extract(text: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []

    gazetteers = {
        "PERSON": [
            "Alan Turing",
            "Alan Mathison Turing",
            "Julius Mathison Turing",
            "Ethel Sara Stoney",
            "Christopher Morcom",
            "Alonzo Church",
            "John von Neumann",
        ],
        "ORG": [
            "King's College",
            "University of Cambridge",
            "University of Manchester",
            "Princeton University",
            "Bletchley Park",
            "Sherborne School",
            "Indian Civil Service",
        ],
        "GPE": [
            "London",
            "Paddington",
            "Cambridge",
            "Manchester",
            "Wilmslow",
            "Cheshire",
            "England",
            "India",
            "Germany",
            "Britain",
        ],
        "CONCEPT": [
            "Turing machine",
            "Computability",
            "Computing Machinery and Intelligence",
            "Artificial Intelligence",
            "Enigma",
            "Church-Turing thesis",
            "quantum mechanics",
        ],
    }
    for label, terms in gazetteers.items():
        for term in terms:
            pat = r"\b" + re.escape(term) + r"\b"
            for m in re.finditer(pat, text, flags=re.IGNORECASE):
                rows.append(
                    {
                        "mention": m.group(0),
                        "label": label,
                        "start": str(m.start()),
                        "end": str(m.end()),
                        "method": "rule_gazetteer",
                    }
                )

    # Date-like expressions (years).
    for m in re.finditer(r"\b(18|19|20)\d{2}\b", text):
        rows.append(
            {
                "mention": m.group(0),
                "label": "DATE",
                "start": str(m.start()),
                "end": str(m.end()),
                "method": "rule_pattern",
            }
        )

    # Basic proper noun sequence heuristic as candidate mentions.
    for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", text):
        mention = m.group(1).strip()
        if len(mention) < 5:
            continue
        rows.append(
            {
                "mention": mention,
                "label": "CANDIDATE",
                "start": str(m.start()),
                "end": str(m.end()),
                "method": "rule_heuristic",
            }
        )

    return rows


def try_spacy_extract(text: str, model_name: str) -> Tuple[List[Dict[str, str]], str]:
    try:
        import spacy  # type: ignore
    except Exception:
        return [], "spacy_not_installed"

    try:
        nlp = spacy.load(model_name)
    except Exception:
        return [], "spacy_model_not_found"

    doc = nlp(text)
    rows: List[Dict[str, str]] = []
    keep = {"PERSON", "ORG", "GPE", "DATE", "WORK_OF_ART"}
    for ent in doc.ents:
        if ent.label_ not in keep:
            continue
        rows.append(
            {
                "mention": ent.text.strip(),
                "label": ent.label_,
                "start": str(ent.start_char),
                "end": str(ent.end_char),
                "method": "spacy_ner",
            }
        )
    return rows, "ok"


def dedupe_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    output = []
    for r in rows:
        key = (r["mention"].strip(), r["label"], r["start"], r["end"])
        if key in seen:
            continue
        seen.add(key)
        output.append(r)
    output.sort(key=lambda x: int(x["start"]))
    return output


def write_csv(path: str, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_summary(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    counter = defaultdict(int)
    for r in rows:
        counter[r["label"]] += 1
    return [{"label": k, "count": str(v)} for k, v in sorted(counter.items(), key=lambda x: x[1], reverse=True)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract entities from biography text.")
    parser.add_argument("--input", default="data/raw/mactutor_turing.txt", help="Input text file")
    parser.add_argument("--out", default="data/processed/entities", help="Output folder")
    parser.add_argument("--spacy_model", default="en_core_web_sm", help="spaCy model name")
    args = parser.parse_args()

    ensure_dir(args.out)
    text = read_text(args.input)

    spacy_rows, status = try_spacy_extract(text, args.spacy_model)
    rule_rows = rule_based_extract(text)
    all_rows = dedupe_rows(spacy_rows + rule_rows)

    entities_path = os.path.join(args.out, "entities_raw.csv")
    summary_path = os.path.join(args.out, "entities_summary.csv")

    write_csv(
        entities_path,
        ["mention", "label", "start", "end", "method"],
        all_rows,
    )
    write_csv(summary_path, ["label", "count"], build_summary(all_rows))

    print(f"spaCy status: {status}")
    print(f"Saved entities: {len(all_rows)} -> {entities_path}")
    print(f"Saved summary: {summary_path}")


if __name__ == "__main__":
    main()
