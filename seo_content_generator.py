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

    def load_keywords_from_csv(self, csv_file_path: str) -> Dict[str, List[Dict]]:
        """Load keywords from Ahrefs CSV export with SERP data"""
        keyword_data = {}

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
                                    # Initialize keyword data if not exists
                                    if keyword not in keyword_data:
                                        keyword_data[keyword] = []

                                    # Collect SERP data for this keyword
                                    serp_entry = {
                                        'title': row.get('Title', ''),
                                        'url': row.get('URL', ''),
                                        'position': row.get('Position', ''),
                                        'traffic': row.get('Traffic', ''),
                                        'difficulty': row.get('Difficulty', ''),
                                        'volume': row.get('Volume', ''),
                                        'cpc': row.get('CPC', ''),
                                        'type': row.get('Type', ''),
                                        'intents': row.get('Intents', '')
                                    }
                                    keyword_data[keyword].append(serp_entry)

                            if keyword_data:  # If we found keywords, break
                                break

                if keyword_data:
                    print(
                        f"Successfully loaded {len(keyword_data)} unique keywords with SERP data using {encoding} encoding")
                    return keyword_data

            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception as e:
                print(f"Error with {encoding} encoding: {e}")
                continue

        print("Failed to load CSV with any supported encoding")
        return {}

    def load_existing_content_from_sitemap(self, sitemap_url: str) -> List[str]:
        """Load existing blog slugs from the sitemap to avoid duplicates"""
        existing_slugs = []
        try:
            print(f"🕸️  Fetching sitemap from {sitemap_url}")
            response = requests.get(sitemap_url, timeout=15)
            response.raise_for_status()

            # Parse XML sitemap
            soup = BeautifulSoup(response.content, 'xml')
            urls = soup.find_all('loc')

            for url in urls:
                if url.text and '/blog/' in url.text:
                    # Extract the blog slug from URL
                    parsed_url = urlparse(url.text)
                    path = parsed_url.path
                    if path.startswith('/blog/'):
                        # Remove /blog/ prefix and trailing slashes
                        slug = path.replace('/blog/', '', 1).strip('/')
                        if slug:
                            # Convert slug to words for better matching
                            slug_words = slug.replace('-', ' ')
                            existing_slugs.append(slug_words)

            print(
                f"✅ Found {len(existing_slugs)} existing blog posts from sitemap")
            return existing_slugs

        except Exception as e:
            print(f"❌ Error loading sitemap: {e}")
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

    def research_keyword_with_claude(self, keyword: str, serp_data: List[Dict] = None) -> Dict:
        """Use Claude Deep Research to analyze keyword and competition"""

        print(f"    🔍 Starting deep research for keyword: '{keyword}'")
        start_time = time.time()

        # Build SERP analysis section
        serp_analysis = ""
        if serp_data:
            print(f"    📊 Analyzing {len(serp_data)} SERP results...")
            serp_analysis = f"""
            
        SERP Analysis Data:
        The top 10 search results for "{keyword}" are:
        """
            for i, result in enumerate(serp_data[:10], 1):
                serp_analysis += f"""
        {i}. Title: {result.get('title', 'N/A')}
           URL: {result.get('url', 'N/A')}
           Position: {result.get('position', 'N/A')}
           Traffic: {result.get('traffic', 'N/A')}
           Type: {result.get('type', 'N/A')}
           Intents: {result.get('intents', 'N/A')}
        """
        else:
            print(f"    ⚠️  No SERP data available for '{keyword}'")

        research_prompt = f"""
        You are a senior SEO content strategist specializing in B2B industrial and maintenance management topics. 
        
        Conduct COMPREHENSIVE deep research on the keyword: "{keyword}"
        {serp_analysis}
        
        Use web search tools to gather current information about:
        - Latest industry trends related to this keyword
        - Recent developments in maintenance management and CMMS
        - Current best practices and emerging technologies
        - Authoritative sources and industry reports
        
        Then perform detailed analysis in these areas:
        
        1. SEARCH INTENT ANALYSIS:
           - What are users really looking for when they search this keyword?
           - What stage of the buyer's journey are they in?
           - What problems are they trying to solve?
           
        2. CONTENT GAP ANALYSIS:
           - What topics are missing from current top-ranking pages?
           - What questions aren't being answered?
           - What depth of information is lacking?
           
        3. USER PAIN POINTS & QUESTIONS:
           - What specific challenges do maintenance managers face with this topic?
           - What are the most common questions and concerns?
           - What misconceptions exist in the market?
           
        4. SEMANTIC KEYWORDS & RELATED TERMS:
           - Provide 20+ related keywords and LSI terms
           - Include technical terminology and industry jargon
           - Add question-based long-tail keywords
           
        5. CONTENT ANGLE RECOMMENDATIONS:
           - Unique angles that would outrank current results
           - Content formats that would perform better
           - Specific hooks and value propositions
           
        6. COMPETITIVE LANDSCAPE:
           - Analyze competitor content strengths and weaknesses
           - Identify differentiation opportunities
           - Note: Avoid similarities to getmaintainx.com, limblecmms.com, upkeep.com
           
        7. RECOMMENDED CONTENT STRUCTURE:
           - Detailed outline with H2 and H3 headings
           - Key points to cover in each section
           - Optimal content length and format suggestions
           
        Focus specifically on maintenance management, industrial operations, CMMS, and related B2B software topics.
        
        Provide comprehensive, actionable insights that will inform the creation of superior content.
        
        Output your analysis in valid JSON format with clear sections for each analysis area.
        """

        print(
            f"    📝 Sending research prompt to Claude (length: {len(research_prompt)} chars)")

        try:
            print(f"    🤖 Calling Claude API...")
            api_start = time.time()

            message = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": research_prompt
                }]
            )

            api_time = time.time() - api_start
            print(f"    ⏱️  Claude API call took {api_time:.2f} seconds")

            # Get the text content safely
            response_text = message.content[0].text
            response_length = len(response_text)
            print(f"    📄 Received response ({response_length} characters)")

            # Show first 200 chars of response for debugging
            preview = response_text[:200].replace('\n', ' ')
            print(f"    👀 Response preview: {preview}...")

            # Clean the response to handle control characters
            cleaned_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', response_text)

            # Try to extract JSON from the response
            print(f"    🔧 Parsing JSON response...")
            try:
                research_data = json.loads(cleaned_text)
                print(
                    f"    ✅ Successfully parsed JSON with {len(research_data)} top-level keys")

                # Log the keys we got back
                if research_data:
                    print(
                        f"    🔑 Research data keys: {list(research_data.keys())}")

            except json.JSONDecodeError as json_err:
                print(f"    ❌ JSON parsing failed: {json_err}")
                print(f"    🔍 Attempting to extract JSON block from response...")

                # If direct parsing fails, try to find JSON block
                json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
                if json_match:
                    try:
                        research_data = json.loads(json_match.group())
                        print(f"    ✅ Successfully extracted and parsed JSON block")
                    except json.JSONDecodeError:
                        print(f"    ❌ Could not parse extracted JSON block")
                        research_data = {
                            "error": "Failed to parse research data", "raw_response": cleaned_text[:500]}
                else:
                    print(f"    ❌ No JSON block found in response")
                    research_data = {
                        "error": "No JSON found in response", "raw_response": cleaned_text[:500]}

            total_time = time.time() - start_time
            print(
                f"    🏁 Research completed in {total_time:.2f} seconds total")

            return research_data

        except Exception as e:
            error_time = time.time() - start_time
            print(
                f"    ❌ Error in keyword research after {error_time:.2f} seconds: {e}")
            return {"error": str(e)}

    def generate_content_with_claude(self, keyword: str, research_data: Dict) -> BlogPost:
        """Generate high-quality blog content using Claude"""
        content_prompt = f"""
        Write a comprehensive blog post for the keyword: "{keyword}"
        
        Research insights: {json.dumps(research_data, indent=2)}
        
        Requirements:
        - Meta title: Less than 60 characters, compelling and SEO-optimized
        - Meta description: 150-160 characters, includes keyword and call-to-action
        - Main title: Engaging H1 that includes the target keyword
        - Body content: 2500-4000 words, comprehensive and authoritative, formatted in clean Markdown
        - Include 5 internal link opportunities in the body text with actual anchor text
        - Include 3 external reference opportunities in the body text with actual anchor text
        - Structure with proper H2 and H3 headings using Markdown syntax
        - Include actionable insights and practical advice
        - Write for maintenance managers, facility operators, and industrial decision-makers
        - Avoid content similar to competitors: getmaintainx.com, limblecmms.com, upkeep.com
        
        For internal_links array, provide 5 objects with:
        - "anchor_text": the text to be linked
        - "suggested_url": suggested internal page URL (e.g., "/blog/related-topic" or "/features/maintenance-tracking")
        - "context": where this link should appear in the content
        
        For external_links array, provide 3 objects with:
        - "anchor_text": the text to be linked  
        - "url": actual external URL to authoritative sources
        - "context": where this link should appear in the content
        
        Also provide:
        - Image generation prompt for a relevant hero image
        
        Output in JSON format with keys: meta_title, meta_description, title, body, image_prompt, internal_links, external_links
        """

        try:
            message = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
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
            print(f"    🎨 Original image prompt from Claude: {image_prompt}")

            # Heavily sanitize and simplify the prompt
            sanitized_prompt = re.sub(r'[^\w\s.,()-]', '', image_prompt)
            sanitized_prompt = sanitized_prompt[:200]  # Much shorter limit

            # Industrial-themed but safe prompts - avoid "workers", "realistic", etc.
            industrial_safe_prompts = [
                "Modern industrial facility with clean equipment",
                "Professional manufacturing plant interior",
                "Clean industrial facility with modern technology",
                "Professional industrial setting with machinery",
                "Modern factory floor with advanced equipment",
                "Industrial facility with professional lighting"
            ]

            # Try industrial theme first, with fallback to ultra-safe
            simple_prompt = industrial_safe_prompts[0]

            print(f"    📝 Final OpenAI prompt: '{simple_prompt}'")
            print(f"    📏 Prompt length: {len(simple_prompt)} characters")

            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=simple_prompt,
                size="1792x1024",
                quality="hd",
                n=1,
            )

            print(f"    ✅ Image generated successfully!")
            return response.data[0].url

        except Exception as e:
            print(f"    ❌ Error generating image: {e}")
            print(
                f"    🔍 Failed prompt was: '{simple_prompt if 'simple_prompt' in locals() else 'undefined'}'")

            # Try ultra-safe fallback if industrial prompt failed
            if 'industrial' in simple_prompt.lower() or 'factory' in simple_prompt.lower() or 'manufacturing' in simple_prompt.lower():
                print(f"    🔄 Trying ultra-safe fallback prompt...")
                try:
                    fallback_prompt = "Professional business illustration, clean modern style"
                    print(f"    📝 Fallback prompt: '{fallback_prompt}'")

                    response = self.openai_client.images.generate(
                        model="dall-e-3",
                        prompt=fallback_prompt,
                        size="1792x1024",
                        quality="standard",
                        n=1,
                    )

                    print(f"    ✅ Fallback image generated successfully!")
                    return response.data[0].url

                except Exception as fallback_e:
                    print(f"    ❌ Even fallback failed: {fallback_e}")

            # Return None if all attempts failed
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

    def check_existing_content(self, keyword: str, output_dir: str = "generated_content") -> bool:
        """Check if content already exists for this keyword"""
        # Create safe filename (same logic as save_output)
        safe_keyword = re.sub(r'[^\w\s-]', '', keyword).strip()
        safe_keyword = re.sub(r'[-\s]+', '-', safe_keyword)

        json_filename = f"{safe_keyword[:50]}.json"
        md_filename = f"{safe_keyword[:50]}.md"

        json_filepath = os.path.join(output_dir, json_filename)
        md_filepath = os.path.join(output_dir, md_filename)

        # Check if both files exist
        json_exists = os.path.exists(json_filepath)
        md_exists = os.path.exists(md_filepath)

        if json_exists and md_exists:
            return True
        elif json_exists or md_exists:
            # If only one file exists, log it and consider as incomplete
            print(
                f"    ⚠️  Incomplete content found for '{keyword}' (JSON: {json_exists}, MD: {md_exists})")
            return False
        else:
            return False

    def save_output(self, prismic_data: Dict, keyword: str, body_markdown: str, output_dir: str = "generated_content"):
        """Save generated content to JSON file and separate markdown file"""
        os.makedirs(output_dir, exist_ok=True)

        # Create safe filename
        safe_keyword = re.sub(r'[^\w\s-]', '', keyword).strip()
        safe_keyword = re.sub(r'[-\s]+', '-', safe_keyword)

        # Save JSON (without body for cleaner format)
        json_data = prismic_data.copy()
        json_data['body'] = "[See separate markdown file]"

        json_filename = f"{safe_keyword[:50]}.json"
        json_filepath = os.path.join(output_dir, json_filename)

        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        # Save Markdown body separately
        md_filename = f"{safe_keyword[:50]}.md"
        md_filepath = os.path.join(output_dir, md_filename)

        with open(md_filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {prismic_data.get('title', keyword)}\n\n")
            f.write(f"**Keyword:** {keyword}\n\n")
            f.write(
                f"**Meta Title:** {prismic_data.get('meta_title', '')}\n\n")
            f.write(
                f"**Meta Description:** {prismic_data.get('meta_description', '')}\n\n")
            f.write("---\n\n")
            f.write(body_markdown)

            # Add reference sections
            if prismic_data.get('internal_links'):
                f.write("\n\n## Internal Link Suggestions\n\n")
                for i, link in enumerate(prismic_data['internal_links'], 1):
                    f.write(
                        f"{i}. **{link.get('anchor_text', 'N/A')}** → `{link.get('suggested_url', 'N/A')}`\n")
                    f.write(f"   Context: {link.get('context', 'N/A')}\n\n")

            if prismic_data.get('external_links'):
                f.write("\n## External Reference Links\n\n")
                for i, link in enumerate(prismic_data['external_links'], 1):
                    f.write(
                        f"{i}. **{link.get('anchor_text', 'N/A')}** → [{link.get('url', 'N/A')}]({link.get('url', 'N/A')})\n")
                    f.write(f"   Context: {link.get('context', 'N/A')}\n\n")

        print(f"Content saved to:")
        print(f"  📄 JSON: {json_filepath}")
        print(f"  📝 Markdown: {md_filepath}")
        return json_filepath, md_filepath


def main():
    generator = SEOContentGenerator()

    print("🚀 SEO Content Generator for f7i.ai")
    print("=" * 50)

    # Get CSV file path
    csv_path = input("Enter path to your Ahrefs keyword CSV file: ").strip()
    if not os.path.exists(csv_path):
        print("❌ CSV file not found!")
        return

    # Get sitemap URL
    sitemap_url = input(
        "Enter sitemap URL (default: https://f7i.ai/sitemap.xml): ").strip()
    if not sitemap_url:
        sitemap_url = "https://f7i.ai/sitemap.xml"

    # Load keywords with SERP data
    keyword_data = generator.load_keywords_from_csv(csv_path)
    if not keyword_data:
        print("❌ No keywords found in CSV!")
        return

    # Load existing content from sitemap
    print(f"\n🔍 Loading existing content from sitemap: {sitemap_url}")
    existing_content = generator.load_existing_content_from_sitemap(
        sitemap_url)

    # Filter out keywords that overlap with existing content OR already have generated content
    filtered_keywords = []
    skipped_overlap = 0
    skipped_existing = 0

    for keyword in keyword_data.keys():
        # Check if content already exists
        if generator.check_existing_content(keyword):
            print(f"✅ Skipping '{keyword}' - content already generated")
            skipped_existing += 1
            continue

        # Check for content overlap with existing blog
        if generator.check_keyword_overlap(keyword, existing_content):
            print(
                f"⚠️  Skipping '{keyword}' - overlaps with existing blog content")
            skipped_overlap += 1
            continue

        filtered_keywords.append(keyword)

    print(f"\n📊 Content Generation Summary:")
    print(f"   • Total keywords in CSV: {len(keyword_data)}")
    print(f"   • Already generated: {skipped_existing}")
    print(f"   • Overlaps with existing blog: {skipped_overlap}")
    print(f"   • Ready for generation: {len(filtered_keywords)}")
    print(f"\n✅ {len(filtered_keywords)} keywords ready for content generation")

    # Process each keyword
    for i, keyword in enumerate(filtered_keywords, 1):
        print(
            f"\n📝 Processing keyword {i}/{len(filtered_keywords)}: {keyword}")

        try:
            # Research keyword with SERP data
            print("  🔬 Researching keyword with SERP analysis...")
            serp_data = keyword_data.get(keyword, [])
            research_data = generator.research_keyword_with_claude(
                keyword, serp_data)

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
            body_markdown = blog_post.body  # Get the original markdown body
            filepaths = generator.save_output(
                prismic_data, keyword, body_markdown)
            print(f"  ✅ Content generated successfully!")

            # Rate limiting
            time.sleep(2)

        except Exception as e:
            print(f"  ❌ Error processing '{keyword}': {e}")
            continue

    print(f"\n🎉 Content generation complete! Check the 'generated_content' folder for your files.")


if __name__ == "__main__":
    main()
