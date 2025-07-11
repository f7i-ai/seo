import os
import json
import base64
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def generate_image_for_work_order_types():
    """Generate a new hero image for the work order types article"""

    # Initialize OpenAI client
    openai_client = openai.OpenAI(
        api_key=os.getenv('OPENAI_API_KEY')
    )

    # Create a prompt based on the work order types content
    image_prompt = "Professional maintenance management dashboard showing different work order types and categories, modern industrial interface design, clean and organized visual with charts and workflow diagrams, professional business illustration style"

    try:
        print(f"🎨 Generating image with prompt: {image_prompt}")

        # Generate image using OpenAI's latest image generation model
        response = openai_client.images.generate(
            model="gpt-image-1",  # Using the latest image generation model
            prompt=image_prompt,
            size="1536x1024",  # Using landscape format for hero image
            quality="high",
        )

        if not response.data or not response.data[0].b64_json:
            raise Exception("No image data returned from OpenAI")

        image_base64 = response.data[0].b64_json
        print(f"✅ Image generated successfully!")

        # Decode the base64 image data
        image_bytes = base64.b64decode(image_base64)

        # Save the image locally
        image_filename = "work-order-types-hero.png"
        image_path = os.path.join("generated_content", image_filename)

        with open(image_path, 'wb') as f:
            f.write(image_bytes)

        print(f"💾 Image saved locally: {image_path}")

        # Update the JSON file with the local image path
        json_path = os.path.join("generated_content", "work-order-types.json")

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Update the hero image with local path
        data["hero_image"] = {
            "url": image_path,
            "alt": "Hero image for Complete Guide to Work Order Types: Classification, Implementation, and Best Practices"
        }

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"✅ Updated JSON file with new image path: {json_path}")

        return image_path

    except Exception as e:
        print(f"❌ Error generating image: {e}")
        return None


if __name__ == "__main__":
    print("🚀 Regenerating Work Order Types Hero Image")
    print("=" * 50)

    result = generate_image_for_work_order_types()

    if result:
        print(f"\n🎉 Successfully generated and saved new hero image!")
        print(f"📁 Image location: {result}")
    else:
        print(f"\n❌ Failed to generate image")
