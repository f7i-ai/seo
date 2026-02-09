#!/usr/bin/env python3
"""
Generate industry hero images for f7i-public industries page using Gemini image model.
Reference: seo_content_generator.generate_image_with_gemini (same client and API).

Run from seo/ with GEMINI_API_KEY set. Outputs to f7i-public/public/images/industries/
by default, or set INDUSTRY_IMAGES_OUTPUT_DIR.
"""

import os
import sys
from pathlib import Path

# Ensure we can import from same package
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from dotenv import load_dotenv
load_dotenv(SCRIPT_DIR / ".env")

# Default: write to f7i-public if it exists next to seo
F7I_PUBLIC_IMAGES = SCRIPT_DIR.parent / "f7i-public" / "public" / "images" / "industries"
OUTPUT_DIR = os.environ.get("INDUSTRY_IMAGES_OUTPUT_DIR", str(F7I_PUBLIC_IMAGES))

INDUSTRIES = [
    {
        "slug": "food-manufacturing",
        "name": "Food Manufacturing",
        "image_prompt": (
            "Professional food manufacturing facility, stainless steel equipment, "
            "conveyors and mixing equipment in the background, workers in white hygiene gear "
            "and hairnets, clean modern factory floor, soft industrial lighting, "
            "photo-realistic, high quality, no text or logos in the image."
        ),
    },
    {
        "slug": "mining",
        "name": "Mining",
        "image_prompt": (
            "Rugged mining environment, large haul truck or crusher in background, "
            "dust and industrial atmosphere, workers in high-vis vests and hard hats, "
            "dramatic natural lighting, photo-realistic, high quality, "
            "no text or logos in the image."
        ),
    },
    {
        "slug": "automotive",
        "name": "Automotive",
        "image_prompt": (
            "Modern automotive assembly line, car body or assembly station in focus, "
            "workers in factory attire, clean industrial setting with overhead lighting, "
            "photo-realistic, high quality, no text or logos in the image."
        ),
    },
    {
        "slug": "pharmaceutical",
        "name": "Pharmaceutical",
        "image_prompt": (
            "Clean pharmaceutical manufacturing environment, stainless steel vessels "
            "or tablet press in background, workers in white lab coats and appropriate PPE, "
            "sterile clean room aesthetic, cool neutral lighting, photo-realistic, high quality, "
            "no text or logos in the image."
        ),
    },
    {
        "slug": "packaging",
        "name": "Packaging",
        "image_prompt": (
            "Packaging production line, form-fill-seal or cartoning equipment, "
            "boxes and conveyors, workers in factory setting, well-lit industrial environment, "
            "photo-realistic, high quality, no text or logos in the image."
        ),
    },
]


def main() -> None:
    from seo_content_generator import SEOContentGenerator

    generator = SEOContentGenerator()
    if generator.gemini_image_client is None:
        print("❌ Gemini image client not available. Install google-genai and set GEMINI_API_KEY.")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"📁 Output directory: {OUTPUT_DIR}")
    print(f"🎨 Generating {len(INDUSTRIES)} industry images with Gemini...\n")

    for i, industry in enumerate(INDUSTRIES, 1):
        slug = industry["slug"]
        name = industry["name"]
        prompt = industry["image_prompt"]
        print(f"[{i}/{len(INDUSTRIES)}] {name} ({slug})...")
        _, local_path = generator.generate_image_with_gemini(
            image_prompt=prompt,
            keyword=slug,
            output_dir=OUTPUT_DIR,
        )
        if local_path:
            print(f"    ✅ {local_path}")
        else:
            print(f"    ❌ Failed to generate image for {name}")

    print("\n✅ Done. Copy or commit images from the output directory to f7i-public if needed.")


if __name__ == "__main__":
    main()
