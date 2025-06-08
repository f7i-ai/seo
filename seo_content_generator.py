import csv
import json
import requests
import time
import re
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
import os
from dotenv import load_dotenv
import anthropic
import openai
from bs4 import BeautifulSoup

# Load environment variables
load_dotenv()


@dataclass
class ContentRequirements:
    meta_title_max: int = 60
    meta_description_min: int = 150
    meta_description_max: int = 160
    word_count_min: int = 2500
    word_count_max: int = 4000
    internal_references: int = 5
    external_references: int = 3


@dataclass
class BlogPost:
    keyword: str
    meta_title: str
    meta_description: str
    title: str
    body: str
    image_prompt: str
    image_url: Optional[str] = None
    internal_links: List[str] = None
    external_links: List[str] = None


class SEOContentGenerator:
    def __init__(self):
        self.anthropic_client = anthropic.Anthropic(
            api_key=os.getenv('ANTHROPIC_API_KEY')
        )
        self.openai_client = openai.OpenAI(
            api_key=os.getenv('OPENAI_API_KEY')
        )
        self.requirements = ContentRequirements()
        self.existing_content = []
        self.competitor_domains = [
            'getmaintainx.com',
            'limblecmms.com',
            'upkeep.com'
        ]

    def load_keywords_from_csv(self, csv_file_path: str) -> List[str]:
        """Load keywords from Ahrefs CSV export"""
        keywords = []

        # Try different encodings commonly used by Ahrefs
        encodings = ['utf-8', 'utf-16', 'iso-8859-1', 'cp1252']

        for encoding in encodings:
            try:
                with open(csv_file_path, 'r', encoding=encoding) as file:
                    # Try both comma and tab separators
                    for delimiter in ['\t', ',']:
                        file.seek(0)  # Reset file position
                        reader = csv.DictReader(file, delimiter=delimiter)

                        # Print available columns for debugging
                        fieldnames = reader.fieldnames
                        print(
                            f"Available columns with {delimiter} delimiter: {fieldnames}")

                        if fieldnames and len(fieldnames) > 1:  # Valid CSV structure
                            for row in reader:
                                # Try different possible column names for keywords
                                keyword = None
                                for col_name in ['Keyword', 'keyword', 'Keywords', 'Query', 'query', 'Search term']:
                                    if col_name in row and row[col_name]:
                                        keyword = row[col_name].strip()
                                        break

                                if keyword:
                                    keywords.append(keyword)

                            if keywords:  # If we found keywords, break
                                break

                if keywords:
                    print(
                        f"Successfully loaded {len(keywords)} keywords using {encoding} encoding")
                    return keywords

            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception as e:
                print(f"Error with {encoding} encoding: {e}")
                continue

        print("Failed to load CSV with any supported encoding")
        return []

    def scrape_existing_content(self, base_url: str = "https://f7i.ai/blog") -> List[str]:
        """Scrape existing blog content to avoid duplicates"""
        existing_topics = []
        try:
            response = requests.get(base_url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract blog titles and topics (adjust selectors based on actual site structure)
            blog_links = soup.find_all('a', href=re.compile(r'/blog'))
            for link in blog_links:
                title = link.get_text().strip().lower()
                if title:
                    existing_topics.append(title)

            # Also extract from meta descriptions and content
            meta_descriptions = soup.find_all(
                'meta', attrs={'name': 'description'})
            for meta in meta_descriptions:
                content = meta.get('content', '').lower()
                existing_topics.append(content)

            print(f"Found {len(existing_topics)} existing content pieces")
            return existing_topics

        except Exception as e:
            print(f"Error scraping existing content: {e}")
            return []

    def check_keyword_overlap(self, keyword: str, existing_content: List[str]) -> bool:
        """Check if keyword overlaps with existing content"""
        keyword_lower = keyword.lower()
        keyword_words = set(keyword_lower.split())

        for content in existing_content:
            content_words = set(content.split())
            # Check for significant overlap (adjust threshold as needed)
            overlap = len(keyword_words.intersection(content_words))
            if overlap >= len(keyword_words) * 0.7:  # 70% overlap threshold
                return True
        return False

    def research_keyword_with_claude(self, keyword: str) -> Dict:
        """Use Claude Deep Research to analyze keyword and competition"""
        research_prompt = f"""
        Conduct deep research on the keyword: "{keyword}"
        
        Please provide:
        1. Search intent analysis
        2. Content gaps in current top-ranking pages
        3. User pain points and questions
        4. Semantic keywords and related terms
        5. Content angle recommendations
        6. Competitive landscape analysis (avoid getmaintainx.com, limblecmms.com, upkeep.com)
        7. Recommended content structure
        
        Focus on maintenance management, industrial operations, and related B2B software topics.
        Output in JSON format.
        """

        try:
            message = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": research_prompt
                }]
            )

            # Get the text content safely
            response_text = message.content[0].text

            # Clean the response to handle control characters
            cleaned_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', response_text)

            # Try to extract JSON from the response
            try:
                research_data = json.loads(cleaned_text)
            except json.JSONDecodeError:
                # If direct parsing fails, try to find JSON block
                json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
                if json_match:
                    research_data = json.loads(json_match.group())
                else:
                    print(f"Could not parse JSON from research response")
                    research_data = {"error": "Failed to parse research data"}

            return research_data

        except Exception as e:
            print(f"Error in keyword research: {e}")
            return {}

    def generate_content_with_claude(self, keyword: str, research_data: Dict) -> BlogPost:
        """Generate high-quality blog content using Claude"""
        content_prompt = f"""
        Write a comprehensive blog post for the keyword: "{keyword}"
        
        Research insights: {json.dumps(research_data, indent=2)}
        
        Requirements:
        - Meta title: Less than 60 characters, compelling and SEO-optimized
        - Meta description: 150-160 characters, includes keyword and call-to-action
        - Main title: Engaging H1 that includes the target keyword
        - Body content: 2500-4000 words, comprehensive and authoritative
        - Include 5 internal link opportunities (use placeholder [INTERNAL-LINK-1] through [INTERNAL-LINK-5])
        - Include 3 external reference opportunities (use placeholder [EXTERNAL-LINK-1] through [EXTERNAL-LINK-3])
        - Structure with proper H2 and H3 headings
        - Include actionable insights and practical advice
        - Write for maintenance managers, facility operators, and industrial decision-makers
        - Avoid content similar to competitors: getmaintainx.com, limblecmms.com, upkeep.com
        
        Also provide:
        - Image generation prompt for a relevant hero image
        
        Output in JSON format with keys: meta_title, meta_description, title, body, image_prompt, internal_links, external_links
        """

        try:
            message = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8000,
                temperature=0.4,
                messages=[{
                    "role": "user",
                    "content": content_prompt
                }]
            )

            # Get the text content safely
            response_text = message.content[0].text

            # Clean the response to handle control characters
            cleaned_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', response_text)

            # Try to extract JSON from the response
            try:
                content_data = json.loads(cleaned_text)
            except json.JSONDecodeError:
                # If direct parsing fails, try to find JSON block
                json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
                if json_match:
                    content_data = json.loads(json_match.group())
                else:
                    print(f"Could not parse JSON from content response")
                    return None

            return BlogPost(
                keyword=keyword,
                meta_title=content_data.get('meta_title', ''),
                meta_description=content_data.get('meta_description', ''),
                title=content_data.get('title', ''),
                body=content_data.get('body', ''),
                image_prompt=content_data.get('image_prompt', ''),
                internal_links=content_data.get('internal_links', []),
                external_links=content_data.get('external_links', [])
            )

        except Exception as e:
            print(f"Error generating content: {e}")
            return None

    def generate_image_with_openai(self, image_prompt: str) -> Optional[str]:
        """Generate hero image using OpenAI DALL-E"""
        try:
            enhanced_prompt = f"""
            Professional, modern illustration for a B2B blog post: {image_prompt}
            Style: Clean, corporate, technology-focused
            Format: Wide landscape format suitable for blog hero image
            Colors: Professional blues, grays, and whites
            No text overlay, high quality, 1792x1024 resolution
            """

            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=enhanced_prompt,
                size="1792x1024",
                quality="standard",
                n=1,
            )

            return response.data[0].url

        except Exception as e:
            print(f"Error generating image: {e}")
            return None

    def format_for_prismic(self, blog_post: BlogPost) -> Dict:
        """Format content for Prismic CMS with proper rich text structure"""

        # Convert markdown-style content to Prismic rich text format
        def convert_to_prismic_richtext(content: str) -> List[Dict]:
            paragraphs = []
            lines = content.split('\n')

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if line.startswith('# '):
                    paragraphs.append({
                        "type": "heading1",
                        "text": line[2:],
                        "spans": []
                    })
                elif line.startswith('## '):
                    paragraphs.append({
                        "type": "heading2",
                        "text": line[3:],
                        "spans": []
                    })
                elif line.startswith('### '):
                    paragraphs.append({
                        "type": "heading3",
                        "text": line[4:],
                        "spans": []
                    })
                else:
                    # Handle links in paragraphs
                    spans = []
                    text = line

                    # Find and process internal links
                    internal_pattern = r'\[INTERNAL-LINK-(\d+)\]'
                    text = re.sub(internal_pattern,
                                  r'internal reference \1', text)

                    # Find and process external links
                    external_pattern = r'\[EXTERNAL-LINK-(\d+)\]'
                    text = re.sub(external_pattern,
                                  r'external reference \1', text)

                    paragraphs.append({
                        "type": "paragraph",
                        "text": text,
                        "spans": spans
                    })

            return paragraphs

        prismic_data = {
            "meta_title": blog_post.meta_title,
            "meta_description": blog_post.meta_description,
            "title": blog_post.title,
            "keyword": blog_post.keyword,
            "hero_image": {
                "url": blog_post.image_url or "",
                "alt": f"Hero image for {blog_post.title}"
            },
            "body": convert_to_prismic_richtext(blog_post.body),
            "internal_references": blog_post.internal_links or [],
            "external_references": blog_post.external_links or []
        }

        return prismic_data

    def save_output(self, prismic_data: Dict, keyword: str, output_dir: str = "generated_content"):
        """Save generated content to JSON file"""
        os.makedirs(output_dir, exist_ok=True)

        # Create safe filename
        safe_keyword = re.sub(r'[^\w\s-]', '', keyword).strip()
        safe_keyword = re.sub(r'[-\s]+', '-', safe_keyword)
        filename = f"{safe_keyword[:50]}.json"

        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(prismic_data, f, indent=2, ensure_ascii=False)

        print(f"Content saved to: {filepath}")
        return filepath


def main():
    generator = SEOContentGenerator()

    print("🚀 SEO Content Generator for f7i.ai")
    print("=" * 50)

    # Get CSV file path
    csv_path = input("Enter path to your Ahrefs keyword CSV file: ").strip()
    if not os.path.exists(csv_path):
        print("❌ CSV file not found!")
        return

    # Load keywords
    keywords = generator.load_keywords_from_csv(csv_path)
    if not keywords:
        print("❌ No keywords found in CSV!")
        return

    # Scrape existing content
    print("\n🔍 Checking existing content on f7i.ai...")
    existing_content = generator.scrape_existing_content()

    # Filter out keywords that overlap with existing content
    filtered_keywords = []
    for keyword in keywords:
        if not generator.check_keyword_overlap(keyword, existing_content):
            filtered_keywords.append(keyword)
        else:
            print(f"⚠️  Skipping '{keyword}' - overlaps with existing content")

    print(f"\n✅ {len(filtered_keywords)} keywords ready for content generation")

    # Process each keyword
    for i, keyword in enumerate(filtered_keywords, 1):
        print(
            f"\n📝 Processing keyword {i}/{len(filtered_keywords)}: {keyword}")

        try:
            # Research keyword
            print("  🔬 Researching keyword...")
            research_data = generator.research_keyword_with_claude(keyword)

            # Generate content
            print("  ✍️  Generating content...")
            blog_post = generator.generate_content_with_claude(
                keyword, research_data)

            if not blog_post:
                print(f"  ❌ Failed to generate content for: {keyword}")
                continue

            # Generate image
            print("  🎨 Generating hero image...")
            blog_post.image_url = generator.generate_image_with_openai(
                blog_post.image_prompt)

            # Format for Prismic
            print("  📋 Formatting for Prismic...")
            prismic_data = generator.format_for_prismic(blog_post)

            # Save output
            filepath = generator.save_output(prismic_data, keyword)
            print(f"  ✅ Content generated successfully!")

            # Rate limiting
            time.sleep(2)

        except Exception as e:
            print(f"  ❌ Error processing '{keyword}': {e}")
            continue

    print(f"\n🎉 Content generation complete! Check the 'generated_content' folder for your files.")


if __name__ == "__main__":
    main()
