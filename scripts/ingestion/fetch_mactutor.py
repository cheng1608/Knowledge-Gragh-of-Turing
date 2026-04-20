import argparse
import json
import os
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup


DEFAULT_URL = "https://mathshistory.st-andrews.ac.uk/Biographies/Turing/"


def clean_text(text: str) -> str:
    return " ".join(text.split())


def extract_paragraphs(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()

    paragraphs = []
    for p in soup.find_all("p"):
        text = clean_text(p.get_text(" ", strip=True))
        if len(text) >= 40:
            paragraphs.append(text)

    if paragraphs:
        return paragraphs

    # Fallback for pages that do not use <p> tags consistently.
    text_lines = soup.get_text("\n", strip=True).splitlines()
    skip_tokens = {
        "Skip to content",
        "MacTutor Home",
        "Biographies",
        "History",
        "Topics",
        "Map",
        "Curves",
        "Search",
        "Quick Info",
        "Summary",
        "View seven larger pictures",
    }
    filtered = []
    for line in text_lines:
        line = clean_text(line)
        if len(line) < 60:
            continue
        if line in skip_tokens:
            continue
        filtered.append(line)

    # Try to keep only biography body section.
    start_idx = 0
    for i, line in enumerate(filtered):
        if line.startswith("Biography") or "Biography Alan Turing was born" in line:
            start_idx = i
            break
    body = filtered[start_idx:]
    if not body:
        body = filtered

    return body


def fetch_page(url: str) -> str:
    headers = {
        "User-Agent": "turing-kg-course-project/0.1 (educational use)",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def save_outputs(output_dir: str, base_name: str, payload: dict) -> None:
    ensure_dir(output_dir)

    json_path = os.path.join(output_dir, f"{base_name}.json")
    txt_path = os.path.join(output_dir, f"{base_name}.txt")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(payload["full_text"])

    print(f"Saved JSON: {json_path}")
    print(f"Saved TXT:  {txt_path}")
    print(f"Paragraphs: {len(payload['paragraphs'])}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch biography text from MacTutor.")
    parser.add_argument("--url", default=DEFAULT_URL, help="MacTutor biography page URL")
    parser.add_argument("--out", default="data/raw", help="Output folder")
    parser.add_argument("--name", default="mactutor_turing", help="Base output file name")
    args = parser.parse_args()

    html = fetch_page(args.url)
    paragraphs = extract_paragraphs(html)

    payload = {
        "source": "MacTutor",
        "source_url": args.url,
        "title": "Alan Turing - MacTutor",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "paragraphs": paragraphs,
        "full_text": "\n".join(paragraphs),
    }

    save_outputs(args.out, args.name, payload)


if __name__ == "__main__":
    main()
