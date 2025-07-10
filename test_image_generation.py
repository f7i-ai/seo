#!/usr/bin/env python3
"""
Test script for debugging OpenAI DALL-E image generation issues
"""

import os
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_openai_connection():
    """Test basic OpenAI connection and API key"""
    print("🔍 Testing OpenAI Connection...")

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY not found in environment variables")
        return False

    print(f"✅ API key found: {api_key[:8]}...{api_key[-4:]}")

    # Initialize client
    client = openai.OpenAI(api_key=api_key)

    # Test API connection with a simple call
    try:
        models = client.models.list()
        print(f"✅ API connection successful - found {len(models.data)} models")
        return client
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        return False


def test_image_generation(client):
    """Test image generation with various prompts and settings"""

    test_cases = [
        {
            "name": "Ultra Simple",
            "prompt": "office building",
            "model": "dall-e-2",
            "size": "512x512"
        },
        {
            "name": "Simple Business",
            "prompt": "modern office",
            "model": "dall-e-2",
            "size": "512x512"
        },
        {
            "name": "DALL-E 3 Simple",
            "prompt": "professional building",
            "model": "dall-e-3",
            "size": "1024x1024",
            "quality": "standard"
        },
        {
            "name": "Your Original Prompt",
            "prompt": "Professional office building with modern architecture",
            "model": "dall-e-3",
            "size": "1024x1024",
            "quality": "standard"
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}/{len(test_cases)}: {test_case['name']}")
        print(f"   Prompt: '{test_case['prompt']}'")
        print(f"   Model: {test_case['model']}")
        print(f"   Size: {test_case['size']}")

        try:
            # Prepare arguments
            args = {
                "model": test_case["model"],
                "prompt": test_case["prompt"],
                "size": test_case["size"],
                "n": 1
            }

            # Add quality if DALL-E 3
            if test_case["model"] == "dall-e-3" and "quality" in test_case:
                args["quality"] = test_case["quality"]

            # Make the API call
            response = client.images.generate(**args)

            print(f"   ✅ SUCCESS! Image URL: {response.data[0].url[:50]}...")

        except Exception as e:
            print(f"   ❌ FAILED: {e}")

            # Additional debugging for this specific error
            if hasattr(e, 'response'):
                print(
                    f"      Status: {getattr(e.response, 'status_code', 'Unknown')}")
                print(
                    f"      Headers: {dict(getattr(e.response, 'headers', {}))}")

            if hasattr(e, 'body'):
                print(f"      Body: {e.body}")


def main():
    print("🚀 OpenAI DALL-E Image Generation Debug Tool")
    print("=" * 50)

    # Test connection
    client = test_openai_connection()
    if not client:
        return

    # Test image generation
    test_image_generation(client)

    print("\n" + "=" * 50)
    print("🏁 Testing complete!")


if __name__ == "__main__":
    main()
