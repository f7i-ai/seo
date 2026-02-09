#!/usr/bin/env python3
"""
Generate missing hero images for existing generated_content posts.

Finds all *.json in generated_content/ where hero_image.local_path is empty
but image_prompt is set, calls Gemini to generate the image, saves the PNG,
and updates the JSON so the Prismic uploader can use it.

Run from seo/ with GEMINI_API_KEY set:
  python generate_missing_hero_images.py
  python generate_missing_hero_images.py --dry-run   # list only, no API calls
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from dotenv import load_dotenv
load_dotenv(SCRIPT_DIR / ".env")

CONTENT_DIR = SCRIPT_DIR / "generated_content"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate missing hero images for existing posts")
    parser.add_argument("--dry-run", action="store_true", help="Only list posts missing images, do not call API")
    parser.add_argument("--limit", type=int, default=0, help="Max number of images to generate (0 = all)")
    args = parser.parse_args()

    if not CONTENT_DIR.exists():
        print(f"❌ Content directory not found: {CONTENT_DIR}")
        sys.exit(1)

    # Find JSON files with empty local_path and non-empty image_prompt
    missing = []
    for path in sorted(CONTENT_DIR.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"⚠️  Skip {path.name}: {e}")
            continue
        hero = data.get("hero_image") or {}
        local_path = (hero.get("local_path") or "").strip()
        image_prompt = (data.get("image_prompt") or "").strip()
        if not local_path and image_prompt:
            base_name = path.stem
            missing.append({
                "path": path,
                "base_name": base_name,
                "title": data.get("title", base_name)[:60],
                "image_prompt": image_prompt[:80] + "..." if len(image_prompt) > 80 else image_prompt,
            })

    if not missing:
        print("✅ No posts with missing hero images (empty local_path but set image_prompt).")
        return

    print(f"📷 Found {len(missing)} post(s) missing hero images:\n")
    for i, m in enumerate(missing, 1):
        print(f"  {i}. {m['base_name']}")
        print(f"     Title: {m['title']}")
        print(f"     Prompt: {m['image_prompt']}")
        print()

    if args.dry_run:
        print("Dry run: not generating images. Run without --dry-run to generate.")
        return

    if not os.getenv("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY not set. Add to .env or export.")
        sys.exit(1)

    from seo_content_generator import SEOContentGenerator
    generator = SEOContentGenerator()
    if generator.gemini_image_client is None:
        print("❌ Gemini image client not available. Install google-genai and set GEMINI_API_KEY.")
        sys.exit(1)

    to_run = missing if args.limit <= 0 else missing[: args.limit]
    print(f"🎨 Generating {len(to_run)} hero image(s)...\n")

    for i, m in enumerate(to_run, 1):
        path = m["path"]
        base_name = m["base_name"]
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        prompt = (data.get("image_prompt") or "").strip()
        if not prompt:
            print(f"[{i}/{len(to_run)}] Skip {base_name}: no image_prompt")
            continue
        print(f"[{i}/{len(to_run)}] {base_name}...")
        try:
            _, local_path = generator.generate_image_with_gemini(
                image_prompt=prompt,
                keyword=base_name,
                output_dir=str(CONTENT_DIR),
            )
            if local_path:
                # Store path relative to seo/ so uploader (run from seo/) finds it
                rel_path = os.path.relpath(local_path, SCRIPT_DIR)
                hero = data.get("hero_image") or {}
                hero["local_path"] = rel_path
                if hero.get("alt") is None or hero.get("alt") == "":
                    hero["alt"] = f"Hero image for {data.get('title', base_name)}"
                data["hero_image"] = hero
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"    ✅ {local_path} (JSON updated)")
            else:
                print(f"    ❌ No image returned from API")
        except Exception as e:
            print(f"    ❌ Error: {e}")
        if i < len(to_run):
            time.sleep(2)  # rate limit

    print("\n✅ Done. Re-run Prismic uploader for updated posts to push images.")


if __name__ == "__main__":
    main()
