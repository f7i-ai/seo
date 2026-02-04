"""
World Models Thought Leadership Content Generator

A specialized content generator for thought leadership articles about AI world models,
robotics in manufacturing, and the future of factory automation.

This is a customized version of seo_content_generator.py optimized for tech-focused
thought leadership content rather than SEO/maintenance-focused content.
"""

import json
import requests
import time
import re
import base64
import logging
import datetime
from typing import List, Dict, Optional, Any, Tuple
from urllib.parse import urlparse
import os
from dotenv import load_dotenv
import openai
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

# Configure logging
def setup_logging():
    """Set up logging to write to the logs directory"""
    os.makedirs('logs', exist_ok=True)
    current_date = datetime.datetime.now().strftime('%Y%m%d')
    log_filename = f'logs/world_models_{current_date}.log'

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("World Models Content Generator session started")
    logger.info("=" * 50)
    return logger

logger = setup_logging()


class ThoughtLeadershipPost(BaseModel):
    """Model for a thought leadership blog post"""
    topic: str
    meta_title: str
    meta_description: str
    title: str
    body: str
    image_prompt: str
    image_url: Optional[str] = None
    local_image_path: Optional[str] = None


class WorldModelsContentGenerator:
    """Generator for World Models thought leadership content"""

    def __init__(self) -> None:
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.text_model = "gpt-5.1-2025-11-13"  # For text generation
        self.image_model = "gpt-image-1"  # For image generation

    def research_topic(self, topic: str, key_questions: List[str]) -> Dict[str, Any]:
        """Research the World Models topic using OpenAI GPT-5.1"""

        logger.info(f"Researching topic: '{topic}'")

        questions_formatted = "\n".join([f"- {q}" for q in key_questions])

        research_prompt = f"""
You are a senior technology analyst and AI researcher specializing in robotics,
simulation, and industrial AI applications.

Conduct COMPREHENSIVE deep research on the topic: "{topic}"

The article should answer these key questions:
{questions_formatted}

Use your knowledge to gather current information about:
- The state of world models in AI (specifically World Labs, DeepMind, OpenAI research)
- How companies like World Labs (marble.worldlabs.ai) are pioneering this space
- Real-world applications in manufacturing, robotics, and simulation
- Technical challenges and current limitations
- Future implications for factory automation

Output in this EXACT structured markdown format:

# Research Analysis: {topic}

## Executive Summary
[High-level overview of world models and why they matter for manufacturing]

## Current State of Technology
[What are world models? How do they differ from traditional AI? Key players and research]

## The Robot Training Problem
[Why is it difficult to train robots? The sim-to-real gap. Current approaches and limitations]

## How World Models Solve the Training Equation
[Technical explanation of how world models enable better robot training]

## Applications Beyond Robotics
[Digital twins, simulation, design validation, safety testing]

## Current Gaps and Challenges
[What's holding back adoption? Technical, economic, and practical barriers]

## Strategic Recommendations for Manufacturers
[Actionable advice for positioning for an AI/robot future]

## Key Takeaways
[Bullet points of main insights]

Be technically accurate but accessible. Target audience is CTOs, VPs of Engineering,
and manufacturing technology leaders who want to understand the strategic implications.
"""

        try:
            max_retries = 3
            response = None
            for attempt in range(max_retries):
                try:
                    response = self.openai_client.chat.completions.create(
                        model=self.text_model,
                        messages=[
                            {"role": "system", "content": "You are a senior technology analyst and AI researcher specializing in robotics, simulation, and industrial AI applications."},
                            {"role": "user", "content": research_prompt}
                        ],
                        temperature=0.3,
                        max_completion_tokens=8000,
                    )
                    break
                except Exception as e:
                    if "429" in str(e) or "rate" in str(e).lower():
                        wait_time = min(60 * (attempt + 1), 300)
                        logger.warning(f"Rate limit hit, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:
                            time.sleep(wait_time)
                            continue
                    raise e

            if response is None:
                raise Exception("Failed to get response from OpenAI API")

            logger.info("Research completed successfully")
            return {"research": response.choices[0].message.content, "error": None}

        except Exception as e:
            logger.error(f"Error in research: {e}")
            return {"research": "", "error": str(e)}

    def generate_content(self, topic: str, research_data: Dict[str, Any], key_questions: List[str]) -> Optional[ThoughtLeadershipPost]:
        """Generate the thought leadership blog post using OpenAI GPT-5.1"""

        questions_formatted = "\n".join([f"- {q}" for q in key_questions])

        content_prompt = f"""
Write a comprehensive thought leadership blog post for Factory AI's technology newsletter.

Topic: "{topic}"

Research insights to incorporate:
{research_data.get('research', '')[:8000]}

KEY QUESTIONS TO ANSWER:
{questions_formatted}

WRITING REQUIREMENTS:
- Target word count: 3000-4000 words
- Tone: Authoritative but accessible, like a thoughtful CTO sharing insights
- Audience: Manufacturing executives, technology leaders, operations professionals
- Include specific examples and real-world implications
- Reference current developments (World Labs/Marble, robotics advances, etc.)
- Balance technical depth with strategic business implications
- Include actionable recommendations

STRUCTURE REQUIREMENTS:
- Start with a compelling hook that draws in manufacturing leaders
- Use clear H2 sections (## headings) for main topics
- Include H3 subsections (### headings) for detailed points
- End with clear takeaways and a call to action

CONTENT THEMES TO COVER:
1. Why factories aren't fully automated (despite decades of promises)
2. The robot training challenge - why current approaches fall short
3. What world models are and how they change the equation
4. Real applications: digital twins, simulation, pre-build validation
5. Current limitations and the path forward
6. Strategic recommendations for manufacturers preparing for this future

LINK REQUIREMENTS:
- Include 2-3 references to Factory AI's relevant solutions (use internal paths like /solutions/manufacturing-ai-software, /products/predictive-maintenance, /blog/)
- Include 2-3 external links to authoritative sources (research papers, industry reports, credible news sources)

IMAGE PROMPT REQUIREMENTS:
- The hero image should show a futuristic but realistic manufacturing environment
- Include advanced robotics, holographic displays, or simulation interfaces
- Diverse workforce interacting with AI/robotics
- Photorealistic, professional quality
- No text or logos in the image

Output in this EXACT structured markdown format:

# Blog Post: {topic}

## META_TITLE
[Compelling title under 60 characters that captures the essence]

## META_DESCRIPTION
[150-160 characters, intriguing and SEO-friendly]

## MAIN_TITLE
[The main headline for the article - engaging and thought-provoking]

## BODY_CONTENT
[The full article in markdown format with proper H2/H3 structure. MINIMUM 3000 words. Include embedded links using markdown syntax [text](url).]

## IMAGE_PROMPT
[Detailed prompt for generating the hero image]
"""

        try:
            max_retries = 3
            response = None
            for attempt in range(max_retries):
                try:
                    response = self.openai_client.chat.completions.create(
                        model=self.text_model,
                        messages=[
                            {"role": "system", "content": "You are an expert technical writer creating thought leadership content for manufacturing executives."},
                            {"role": "user", "content": content_prompt}
                        ],
                        temperature=0.5,
                        max_completion_tokens=16000,
                    )
                    break
                except Exception as e:
                    if "429" in str(e) or "rate" in str(e).lower():
                        wait_time = min(60 * (attempt + 1), 300)
                        logger.warning(f"Rate limit hit, waiting {wait_time}s")
                        if attempt < max_retries - 1:
                            time.sleep(wait_time)
                            continue
                    raise e

            if response is None:
                raise Exception("Failed to get response from OpenAI API")

            # Parse the response
            content = self._parse_content(response.choices[0].message.content, topic)
            return content

        except Exception as e:
            logger.error(f"Error generating content: {e}")
            return None

    def _parse_content(self, markdown_text: str, topic: str) -> Optional[ThoughtLeadershipPost]:
        """Parse the generated content"""
        try:
            text = markdown_text.strip()

            patterns = {
                'meta_title': r'## META_TITLE\s*\n(.*?)(?=##|$)',
                'meta_description': r'## META_DESCRIPTION\s*\n(.*?)(?=##|$)',
                'title': r'## MAIN_TITLE\s*\n(.*?)(?=##|$)',
                'body': r'## BODY_CONTENT\s*\n(.*?)(?=## IMAGE_PROMPT|$)',
                'image_prompt': r'## IMAGE_PROMPT\s*\n(.*?)(?=##|$)',
            }

            content = {}
            for key, pattern in patterns.items():
                match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if match:
                    content[key] = match.group(1).strip()
                else:
                    content[key] = ""

            # Clean up bracket placeholders
            for key in content:
                if content[key]:
                    content[key] = re.sub(r'^\[.*?\]\s*', '', content[key])

            return ThoughtLeadershipPost(
                topic=topic,
                meta_title=content.get('meta_title', ''),
                meta_description=content.get('meta_description', '')[:160],
                title=content.get('title', ''),
                body=content.get('body', ''),
                image_prompt=content.get('image_prompt', '')
            )

        except Exception as e:
            logger.error(f"Error parsing content: {e}")
            return None

    def generate_image(self, image_prompt: str, topic: str, output_dir: str = "generated_content") -> Tuple[Optional[str], Optional[str]]:
        """Generate hero image using OpenAI"""
        try:
            logger.info(f"Generating image with prompt: {image_prompt[:100]}...")

            response = self.openai_client.images.generate(
                model=self.image_model,
                prompt=image_prompt,
                size="1536x1024",
                quality="auto",
                n=1,
            )

            if response.data and len(response.data) > 0:
                first_image = response.data[0]

                if hasattr(first_image, 'b64_json') and first_image.b64_json:
                    # Save base64 image
                    safe_topic = re.sub(r'[^\w\s-]', '', topic).strip()
                    safe_topic = re.sub(r'[-\s]+', '-', safe_topic)

                    os.makedirs(output_dir, exist_ok=True)
                    local_filepath = os.path.join(output_dir, f"{safe_topic[:50]}.png")

                    image_data = base64.b64decode(first_image.b64_json)
                    with open(local_filepath, 'wb') as f:
                        f.write(image_data)

                    logger.info(f"Image saved to: {local_filepath}")
                    return None, local_filepath

            return None, None

        except Exception as e:
            logger.error(f"Error generating image: {e}")
            return None, None

    def save_output(self, post: ThoughtLeadershipPost, output_dir: str = "generated_content") -> Tuple[str, str]:
        """Save the generated content"""
        os.makedirs(output_dir, exist_ok=True)

        safe_topic = re.sub(r'[^\w\s-]', '', post.topic).strip()
        safe_topic = re.sub(r'[-\s]+', '-', safe_topic)

        # Save JSON
        json_data = {
            "meta_title": post.meta_title,
            "meta_description": post.meta_description,
            "title": post.title,
            "topic": post.topic,
            "hero_image": {
                "local_path": post.local_image_path or "",
                "alt": f"Hero image for {post.title}"
            },
            "image_prompt": post.image_prompt,
            "word_count": len(post.body.split()),
            "markdown_body": "[See separate markdown file]"
        }

        json_filepath = os.path.join(output_dir, f"{safe_topic[:50]}.json")
        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        # Save Markdown
        md_filepath = os.path.join(output_dir, f"{safe_topic[:50]}.md")
        with open(md_filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {post.title}\n\n")
            f.write(f"**Topic:** {post.topic}\n\n")
            f.write(f"**Meta Title:** {post.meta_title}\n\n")
            f.write(f"**Meta Description:** {post.meta_description}\n\n")
            f.write(f"**Word Count:** {len(post.body.split())}\n\n")
            f.write("---\n\n")
            f.write(post.body)

        logger.info(f"Content saved to: {json_filepath}, {md_filepath}")
        return json_filepath, md_filepath


def main():
    """Main function to generate World Models thought leadership content"""

    print("🚀 World Models Thought Leadership Content Generator")
    print("=" * 60)

    # Define the topic and key questions
    topic = "The Rise of World Models in Physical Industries"

    key_questions = [
        "Why aren't all factories automated despite decades of promises?",
        "Why don't we have more robots or advanced robots in manufacturing?",
        "How are robots currently trained, and why is it difficult?",
        "Why is it so hard to train robots on human tasks?",
        "How does a world model help solve the robot training equation?",
        "What other use cases exist for world models? (Digital twins, simulating new environments)",
        "Where are we today? What are the gaps and challenges stopping adoption?",
        "What should manufacturers do to position themselves for a robot future?",
    ]

    print(f"\n📝 Topic: {topic}")
    print(f"\n❓ Key Questions to Address:")
    for q in key_questions:
        print(f"   • {q}")

    # Initialize generator
    generator = WorldModelsContentGenerator()

    # Step 1: Research
    print("\n🔬 Researching topic...")
    research_data = generator.research_topic(topic, key_questions)

    if research_data.get("error"):
        print(f"❌ Research failed: {research_data['error']}")
        return

    print("✅ Research complete!")

    # Step 2: Generate content
    print("\n✍️  Generating content...")
    post = generator.generate_content(topic, research_data, key_questions)

    if not post:
        print("❌ Content generation failed!")
        return

    print(f"✅ Generated {len(post.body.split())} words")

    # Step 3: Generate image
    print("\n🎨 Generating hero image...")
    image_url, local_path = generator.generate_image(post.image_prompt, topic)
    post.image_url = image_url
    post.local_image_path = local_path

    if local_path:
        print(f"✅ Image saved to: {local_path}")
    else:
        print("⚠️  Image generation failed (content still saved)")

    # Step 4: Save output
    print("\n💾 Saving content...")
    json_path, md_path = generator.save_output(post)

    print("\n" + "=" * 60)
    print("🎉 Content generation complete!")
    print(f"\n📁 Files created:")
    print(f"   • JSON: {json_path}")
    print(f"   • Markdown: {md_path}")
    if local_path:
        print(f"   • Image: {local_path}")

    print(f"\n📊 Stats:")
    print(f"   • Title: {post.title}")
    print(f"   • Word count: {len(post.body.split())}")
    print(f"   • Meta title: {post.meta_title}")


if __name__ == "__main__":
    main()

