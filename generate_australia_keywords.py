#!/usr/bin/env python3
"""
Validate and summarise the curated Australia keyword CSV (kw-australia-longtail.csv).

This script does NOT mechanically generate keywords. The CSV is hand-curated
because blindly appending "Australia" to every base keyword creates thousands
of zero-volume phrases that dilute site authority.

The CSV is designed to be used directly with seo_content_generator.py.

Run: python3 generate_australia_keywords.py
"""

import csv
import os
import re
from pathlib import Path
from collections import Counter

SEO_DIR = Path(__file__).resolve().parent
CSV_PATH = SEO_DIR / "kw-australia-longtail.csv"
GENERATED_DIR = SEO_DIR / "generated_content"


def main() -> None:
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found.")
        return

    # Load keywords
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Australia keyword file: {CSV_PATH}")
    print(f"Total keywords: {len(rows)}")

    # Breakdown by tier
    tiers = Counter(r.get("Tier", "").strip() for r in rows)
    print(f"\nBy tier:")
    for t, count in tiers.most_common():
        print(f"  {t or '(blank)'}: {count}")

    # Breakdown by state
    states = Counter(r.get("State", "").strip() for r in rows if r.get("State", "").strip())
    print(f"\nState-level breakdown:")
    for s, count in states.most_common():
        print(f"  {s}: {count}")

    # Compliance vs non-compliance
    compliance = sum(1 for r in rows if r.get("Compliance_relevant", "").strip().upper() == "Y")
    print(f"\nCompliance-relevant: {compliance}")
    print(f"Non-compliance: {len(rows) - compliance}")

    # Intents
    intents = Counter(r.get("Intents", "").strip() for r in rows)
    print(f"\nBy intent:")
    for intent, count in intents.most_common():
        print(f"  {intent or '(blank)'}: {count}")

    # Base keyword categories
    bases = Counter(r.get("Base Keyword", "").strip() for r in rows)
    print(f"\nBase keyword categories: {len(bases)}")
    for b, count in bases.most_common():
        print(f"  {b}: {count}")

    # Check overlap with already-generated content
    if GENERATED_DIR.exists():
        existing = set()
        for f in os.listdir(GENERATED_DIR):
            if f.endswith(".json"):
                existing.add(f.replace(".json", "").lower())

        overlap = []
        for r in rows:
            kw = r.get("Keyword", "")
            safe = re.sub(r"[^\w\s-]", "", kw).strip()
            safe = re.sub(r"[-\s]+", "-", safe).lower()[:50]
            if safe in existing:
                overlap.append(kw)

        if overlap:
            print(f"\nAlready generated ({len(overlap)} will be skipped by seo_content_generator):")
            for o in overlap:
                print(f"  - {o}")
        else:
            print(f"\nNo overlap with existing generated content (all {len(rows)} are new).")
    else:
        print(f"\ngenerated_content/ directory not found; cannot check overlap.")

    print(f"\nTo generate content, run:")
    print(f"  python3 seo_content_generator.py")
    print(f"  (enter path: kw-australia-longtail.csv when prompted)")


if __name__ == "__main__":
    main()
