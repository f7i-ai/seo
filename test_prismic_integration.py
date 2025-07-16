#!/usr/bin/env python3
"""
Test script for SEO content generation + Prismic upload integration
"""

import os
import sys
from seo_content_generator import SEOContentGenerator


def test_prismic_integration():
    """Test the complete pipeline: content generation + Prismic upload"""

    print("🧪 Testing SEO Content Generator + Prismic Integration")
    print("=" * 60)

    # Test keyword
    test_keyword = "predictive maintenance software"

    try:
        # Initialize generator
        print("🚀 Initializing SEO Content Generator...")
        generator = SEOContentGenerator()

        # Check if we have existing content for this keyword
        if generator.check_existing_content(test_keyword):
            print(f"✅ Found existing content for '{test_keyword}'")

            # Just test the Prismic upload part
            print("📤 Testing Prismic upload with existing content...")
            safe_keyword = test_keyword.replace(' ', '-')
            json_path = f"generated_content/{safe_keyword}.json"

            if os.path.exists(json_path):
                # Test upload
                result = generator.upload_to_prismic(
                    json_path, skip_upload=True)
                if result["success"]:
                    print("✅ Prismic test upload successful!")

                    # Ask if user wants to do real upload
                    choice = input(
                        "\nDo you want to test a real upload to Prismic? (y/n): ").strip().lower()
                    if choice in ['y', 'yes']:
                        print("📤 Uploading to Prismic...")
                        real_result = generator.upload_to_prismic(
                            json_path, skip_upload=False)
                        if real_result["success"]:
                            print("🎉 Successfully uploaded to Prismic!")
                        else:
                            print(
                                f"❌ Upload failed: {real_result.get('error', 'Unknown error')}")
                else:
                    print(
                        f"❌ Test failed: {result.get('error', 'Unknown error')}")
            else:
                print(f"❌ JSON file not found: {json_path}")
        else:
            print(f"⚠️  No existing content found for '{test_keyword}'")
            print("💡 Run the main SEO generator first to create content")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_prismic_integration()
