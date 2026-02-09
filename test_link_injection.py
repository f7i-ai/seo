#!/usr/bin/env python3
"""
Test script for the link injection feature.
Reads existing content and adds internal links using a second LLM pass.
"""

import os
import sys
from seo_content_generator import SEOContentGenerator

def main():
    # Get file path from command line or use default
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    else:
        test_file = "generated_content/signal-analysis-for-condition-monitoring.md"

    # Check for is_pillar flag
    is_pillar = "--pillar" in sys.argv or "-p" in sys.argv

    if not os.path.exists(test_file):
        print(f"File not found: {test_file}")
        sys.exit(1)

    # Initialize generator
    generator = SEOContentGenerator()

    # Load internal URLs from sitemap
    print("Loading internal URLs from sitemap...")
    generator.load_existing_content_from_sitemap("https://f7i.ai/sitemap.xml")
    print(f"Loaded {len(generator.available_internal_urls)} internal URLs")

    print(f"\nReading content from: {test_file}")
    with open(test_file, 'r') as f:
        content = f.read()

    # Extract just the body content (skip metadata header)
    lines = content.split('\n')
    body_start = 0
    divider_count = 0
    for i, line in enumerate(lines):
        if line.strip() == '---':
            divider_count += 1
            if divider_count == 1:
                body_start = i + 1
                break

    body_content = '\n'.join(lines[body_start:])

    # Extract keyword from metadata
    keyword = "content"
    for line in lines[:body_start]:
        if line.startswith("**Keyword:**"):
            keyword = line.replace("**Keyword:**", "").strip()
            break

    print(f"Keyword: {keyword}")
    print(f"Content length: {len(body_content.split())} words")
    print(f"Mode: {'Pillar' if is_pillar else 'Standard'}")

    # Count existing internal links
    import re
    existing_links = len(re.findall(r'\[([^\]]+)\]\((/[^)]+)\)', body_content))
    print(f"Existing internal links: {existing_links}")

    # Run link injection
    print(f"\n--- Running link injection ---\n")

    linked_content = generator.add_internal_links(
        content=body_content,
        keyword=keyword,
        is_pillar=is_pillar
    )

    # Create output filename
    base_name = os.path.splitext(test_file)[0]
    output_file = f"{base_name}-LINKED.md"

    # Reconstruct with metadata
    metadata = '\n'.join(lines[:body_start])
    full_output = metadata + '\n' + linked_content

    with open(output_file, 'w') as f:
        f.write(full_output)

    # Count new links
    new_links = len(re.findall(r'\[([^\]]+)\]\((/[^)]+)\)', linked_content))

    print(f"\n--- Link injection complete ---")
    print(f"Output saved to: {output_file}")
    print(f"Internal links: {existing_links} -> {new_links} (+{new_links - existing_links})")

if __name__ == "__main__":
    main()
