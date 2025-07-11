import csv
import json
import requests
import time
import re
import base64
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from urllib.parse import urlparse
import os
from dotenv import load_dotenv
import google.generativeai as genai
import openai
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

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


class InternalLink(BaseModel):
    anchor_text: str = Field(description="The text to be linked")
    suggested_url: str = Field(description="Suggested internal page URL")
    context: str = Field(
        description="Where this link should appear in the content")


class ExternalLink(BaseModel):
    anchor_text: str = Field(description="The text to be linked")
    url: str = Field(description="External URL to authoritative source")
    context: str = Field(
        description="Where this link should appear in the content")


class BlogPost(BaseModel):
    keyword: str = Field(description="The target keyword for SEO")
    meta_title: str = Field(
        description="SEO meta title (less than 60 characters)")
    meta_description: str = Field(
        description="SEO meta description (150-160 characters)")
    title: str = Field(description="Main article title (H1)")
    body: str = Field(description="Full article content in Markdown format")
    image_prompt: str = Field(description="Prompt for generating hero image")
    image_url: Optional[str] = Field(
        default=None, description="URL or path to generated image")
    internal_links: List[InternalLink] = Field(
        default_factory=list, description="Internal link opportunities")
    external_links: List[ExternalLink] = Field(
        default_factory=list, description="External reference links")


class ResearchData(BaseModel):
    search_intent: str = Field(description="User search intent analysis")
    content_gaps: List[str] = Field(description="Content gaps identified")
    user_pain_points: List[str] = Field(
        description="User pain points and questions")
    semantic_keywords: List[str] = Field(
        description="Related keywords and LSI terms")
    content_angles: List[str] = Field(
        description="Unique content angle recommendations")
    competitive_analysis: str = Field(
        description="Competitive landscape analysis")
    content_structure: List[str] = Field(
        description="Recommended content structure")
    raw_response: Optional[str] = Field(
        default=None, description="Raw response for debugging")


class SEOContentGenerator:
    def __init__(self):
        # Initialize Gemini client
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        self.gemini_model = genai.GenerativeModel('gemini-2.5-pro')

        # Initialize OpenAI client
        self.openai_client = openai.OpenAI(
            api_key=os.getenv('OPENAI_API_KEY')
        )

        self.requirements = ContentRequirements()
        self.existing_content: List[str] = []
        self.competitor_domains = [
            'getmaintainx.com',
            'limblecmms.com',
            'upkeep.com'
        ]

    def load_keywords_from_csv(self, csv_file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """Load keywords from Ahrefs CSV export with SERP data"""
        keyword_data: Dict[str, List[Dict[str, Any]]] = {}

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

    def research_keyword_with_gemini(self, keyword: str, serp_data: List[Dict[str, Any]] = None) -> ResearchData:
        """Use Gemini to analyze keyword and competition with structured output"""

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
        
        Analyze the keyword and provide detailed insights in these areas:
        
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
        
        Respond with structured JSON output matching the ResearchData schema.
        """

        print(
            f"    📝 Sending research prompt to Gemini (length: {len(research_prompt)} chars)")

        try:
            print(f"    🤖 Calling Gemini API...")
            api_start = time.time()

            # Generate content with structured output
            response = self.gemini_model.generate_content(
                research_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=4000,
                    response_mime_type="application/json",
                    response_schema=ResearchData
                )
            )

            api_time = time.time() - api_start
            print(f"    ⏱️  Gemini API call took {api_time:.2f} seconds")

            # Parse the structured response
            research_data = ResearchData.model_validate_json(response.text)
            print(f"    ✅ Successfully parsed structured response")

            total_time = time.time() - start_time
            print(
                f"    🏁 Research completed in {total_time:.2f} seconds total")

            return research_data

        except Exception as e:
            error_time = time.time() - start_time
            print(
                f"    ❌ Error in keyword research after {error_time:.2f} seconds: {e}")
            return ResearchData(
                search_intent="Error in research analysis",
                content_gaps=["Analysis failed"],
                user_pain_points=["Research error"],
                semantic_keywords=["keyword research failed"],
                content_angles=["Unable to analyze"],
                competitive_analysis="Research failed due to error",
                content_structure=["Error in analysis"],
                raw_response=str(e)
            )

    def generate_content_with_gemini(self, keyword: str, research_data: ResearchData) -> BlogPost:
        """Generate high-quality blog content using Gemini with structured output"""
        content_prompt = f"""
        Write a comprehensive blog post for the keyword: "{keyword}"
        
        Research insights: {research_data.model_dump_json(indent=2)}
        
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
        
        Respond with structured JSON output matching the BlogPost schema.
        """

        try:
            response = self.gemini_model.generate_content(
                content_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.4,
                    max_output_tokens=8000,
                    response_mime_type="application/json",
                    response_schema=BlogPost
                )
            )

            # Parse the structured response
            blog_post = BlogPost.model_validate_json(response.text)
            print(f"✅ Successfully generated structured blog post")

            return blog_post

        except Exception as e:
            print(f"Error generating content: {e}")
            # Return a minimal BlogPost with error info
            return BlogPost(
                keyword=keyword,
                meta_title=f"Error generating content for {keyword}",
                meta_description=f"Content generation failed for {keyword}",
                title=f"Error: {keyword}",
                body="Content generation failed due to an error.",
                image_prompt="Error in content generation",
                internal_links=[],
                external_links=[]
            )

    def generate_image_with_openai(self, image_prompt: str) -> Optional[str]:
        """Generate hero image using OpenAI GPT-Image-1 with industrial scenes"""
        try:
            print(f"    🎨 Original image prompt from Gemini: {image_prompt}")

            # Enhance the original prompt to include industrial scene with person
            def enhance_with_industrial_scene(original_prompt: str) -> str:
                """Enhance the original prompt to include industrial scene and person"""

                # Standard industrial scene elements to add
                industrial_elements = [
                    "Professional maintenance professional in a modern manufacturing facility",
                    "Clean, well-lit industrial environment",
                    "Industrial machinery and equipment in the background",
                    "Safety equipment and protocols visible",
                    "Blue and orange accent colors to convey technology and reliability",
                    "Modern industrial design elements"
                ]

                # Clean and prepare the original prompt
                clean_prompt = original_prompt.strip()

                # If the prompt already mentions industrial/factory/manufacturing, enhance it
                if any(word in clean_prompt.lower() for word in ['industrial', 'factory', 'manufacturing', 'facility', 'plant']):
                    enhanced_prompt = f"{clean_prompt}, featuring a professional maintenance worker in the scene. {' '.join(industrial_elements)}. Style should be professional and well-lit."

                # If it mentions specific equipment or concepts, add person working with that equipment
                elif any(word in clean_prompt.lower() for word in ['equipment', 'machine', 'system', 'tool', 'device', 'technology']):
                    enhanced_prompt = f"Professional maintenance technician working with {clean_prompt.lower()} in a modern manufacturing facility. {' '.join(industrial_elements)}. Style should be professional and well-lit."

                # For general/abstract prompts, create a full industrial scene
                else:
                    enhanced_prompt = f"Professional maintenance professional in a modern manufacturing facility working on {clean_prompt.lower()}. {' '.join(industrial_elements)}. Style should be professional and well-lit."

                return enhanced_prompt

            # Enhance the original prompt with industrial scene
            industrial_prompt = enhance_with_industrial_scene(image_prompt)

            print(f"    📝 Industrial scene prompt: '{industrial_prompt}'")
            print(f"    📏 Prompt length: {len(industrial_prompt)} characters")

            # Generate image using OpenAI's latest image generation model
            response = self.openai_client.images.generate(
                model="gpt-image-1",
                prompt=industrial_prompt,
                size="1536x1024",  # Landscape format for hero images
                quality="high",
            )

            if not response.data or not response.data[0].b64_json:
                raise Exception("No image data returned from OpenAI")

            # Get base64 image data
            image_base64 = response.data[0].b64_json
            image_bytes = base64.b64decode(image_base64)

            # Create safe filename from keyword
            safe_filename = re.sub(r'[^\w\s-]', '', image_prompt[:50]).strip()
            safe_filename = re.sub(r'[-\s]+', '-', safe_filename)
            image_filename = f"{safe_filename}-hero.png"
            image_path = os.path.join("generated_content", image_filename)

            # Save image locally
            with open(image_path, 'wb') as f:
                f.write(image_bytes)

            print(f"    ✅ Image generated and saved: {image_path}")
            return image_path

        except Exception as e:
            print(f"    ❌ Error generating image: {e}")
            print(
                f"    🔍 Failed prompt was: '{industrial_prompt if 'industrial_prompt' in locals() else 'undefined'}'")

            # Try simpler fallback prompt
            try:
                print(f"    🔄 Trying fallback industrial prompt...")
                fallback_prompt = "Professional maintenance technician with safety equipment in a modern manufacturing facility with industrial machinery in the background"

                response = self.openai_client.images.generate(
                    model="gpt-image-1",
                    prompt=fallback_prompt,
                    size="1536x1024",
                    quality="standard",
                )

                if response.data and response.data[0].b64_json:
                    image_base64 = response.data[0].b64_json
                    image_bytes = base64.b64decode(image_base64)

                    # Save fallback image
                    fallback_filename = "fallback-industrial-hero.png"
                    fallback_path = os.path.join(
                        "generated_content", fallback_filename)

                    with open(fallback_path, 'wb') as f:
                        f.write(image_bytes)

                    print(f"    ✅ Fallback image generated: {fallback_path}")
                    return fallback_path

            except Exception as fallback_e:
                print(f"    ❌ Fallback also failed: {fallback_e}")

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
            research_data = generator.research_keyword_with_gemini(
                keyword, serp_data)

            # Generate content
            print("  ✍️  Generating content...")
            blog_post = generator.generate_content_with_gemini(
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
