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
import google.generativeai as genai  # type: ignore
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
    local_image_path: Optional[str] = None
    internal_links: Optional[List[str]] = None
    external_links: Optional[List[str]] = None


class SEOContentGenerator:
    def __init__(self):
        # Configure Gemini 2.5 Pro
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))  # type: ignore
        self.gemini_model = genai.GenerativeModel(  # type: ignore
            'gemini-2.5-pro-preview-03-25')

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

    def research_keyword_with_gemini(self, keyword: str, serp_data: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Use Gemini to analyze keyword and competition"""

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
        
        Use web search to gather current information about:
        - Latest industry trends related to this keyword
        - Recent developments in maintenance management and CMMS
        - Current best practices and emerging technologies
        - Authoritative sources and industry reports
        
        Then perform detailed analysis and output in this EXACT structured markdown format:

        # Research Analysis: {keyword}

        ## Search Intent Analysis
        [What are users really looking for? What stage of buyer's journey? What problems are they solving?]

        ## Content Gap Analysis  
        [What topics are missing from current top-ranking pages? What questions aren't answered? What depth is lacking?]

        ## User Pain Points & Questions
        [What specific challenges do maintenance managers face? Most common questions? Market misconceptions?]

        ## Semantic Keywords & Related Terms
        [Provide 20+ related keywords, LSI terms, technical terminology, question-based long-tail keywords - one per line with bullets]

        ## Content Angle Recommendations
        [Unique angles to outrank current results, better content formats, specific hooks and value propositions]

        ## Competitive Landscape
        [Competitor content strengths/weaknesses, differentiation opportunities. Avoid similarities to getmaintainx.com, limblecmms.com, upkeep.com]

        ## Recommended Content Structure
        [Detailed outline with H2/H3 headings, key points for each section, optimal content length]

        ## Industry Trends & Developments
        [Latest trends in maintenance management, CMMS developments, emerging technologies]

        ## Authoritative Sources
        [Industry reports, research studies, expert sources to reference]

        Use this EXACT format with these EXACT headings. Focus on maintenance management, industrial operations, CMMS, and B2B software topics.
        """

        print(
            f"    📝 Sending research prompt to Gemini (length: {len(research_prompt)} chars)")

        try:
            print(f"    🤖 Calling Gemini API...")
            api_start = time.time()

            # Add retry logic for rate limiting
            max_retries = 3
            response = None
            for attempt in range(max_retries):
                try:
                    response = self.gemini_model.generate_content(  # type: ignore
                        research_prompt,
                        generation_config=genai.types.GenerationConfig(  # type: ignore
                            temperature=0.3,
                            max_output_tokens=4000,  # Reduced for free tier
                        )
                    )
                    break  # Success, exit retry loop

                except Exception as e:
                    if "429" in str(e) or "quota" in str(e).lower():
                        wait_time = min(60 * (attempt + 1),
                                        300)  # Max 5 minutes
                        print(
                            f"    ⏳ Rate limit hit, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:  # Don't wait on last attempt
                            time.sleep(wait_time)
                            continue
                    raise e  # Re-raise if not rate limit or last attempt

            if response is None:
                raise Exception("Failed to get response from Gemini API")

            api_time = time.time() - api_start
            print(f"    ⏱️  Gemini API call took {api_time:.2f} seconds")

            # Get the text content
            response_text = response.text
            response_length = len(response_text)
            print(f"    📄 Received response ({response_length} characters)")

            # Show first 200 chars of response for debugging
            preview = response_text[:200].replace('\n', ' ')
            print(f"    👀 Response preview: {preview}...")

            # Parse markdown response into structured data
            print(f"    🔧 Parsing markdown response...")
            research_data = self._parse_research_markdown(
                response_text, keyword)

            if research_data:
                print(
                    f"    ✅ Successfully parsed markdown with {len(research_data)} sections")
                print(
                    f"    🔑 Research data keys: {list(research_data.keys())}")
            else:
                print(f"    ❌ Failed to parse markdown response")
                research_data = {
                    "error": "Failed to parse research data",
                    "raw_response": response_text[:500]
                }

            total_time = time.time() - start_time
            print(
                f"    🏁 Research completed in {total_time:.2f} seconds total")

            return research_data

        except Exception as e:
            error_time = time.time() - start_time
            print(
                f"    ❌ Error in keyword research after {error_time:.2f} seconds: {e}")
            return {"error": str(e)}

    def _parse_research_markdown(self, markdown_text: str, keyword: str) -> Dict[str, Any]:
        """Parse structured markdown research into dictionary"""
        try:
            # Clean the text
            text = markdown_text.strip()

            # Extract sections using regex
            sections: Dict[str, Any] = {}
            sections['keyword'] = keyword

            # Define section patterns
            patterns = {
                'search_intent': r'## Search Intent Analysis\s*\n(.*?)(?=##|$)',
                'content_gaps': r'## Content Gap Analysis\s*\n(.*?)(?=##|$)',
                'pain_points': r'## User Pain Points & Questions\s*\n(.*?)(?=##|$)',
                'semantic_keywords': r'## Semantic Keywords & Related Terms\s*\n(.*?)(?=##|$)',
                'content_angles': r'## Content Angle Recommendations\s*\n(.*?)(?=##|$)',
                'competitive_landscape': r'## Competitive Landscape\s*\n(.*?)(?=##|$)',
                'content_structure': r'## Recommended Content Structure\s*\n(.*?)(?=##|$)',
                'industry_trends': r'## Industry Trends & Developments\s*\n(.*?)(?=##|$)',
                'authoritative_sources': r'## Authoritative Sources\s*\n(.*?)(?=##|$)'
            }

            # Extract each section
            for key, pattern in patterns.items():
                match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if match:
                    sections[key] = match.group(1).strip()
                else:
                    sections[key] = ""

            # Parse semantic keywords into list
            if sections.get('semantic_keywords'):
                keywords_text = sections['semantic_keywords']
                # Extract bullet points or lines
                keywords: List[str] = []
                for line in keywords_text.split('\n'):
                    line = line.strip()
                    if line and (line.startswith('-') or line.startswith('•') or line.startswith('*')):
                        keyword = line.lstrip('-•* ').strip()
                        if keyword:
                            keywords.append(keyword)
                sections['semantic_keywords_list'] = keywords

            return sections

        except Exception as e:
            print(f"    ❌ Error parsing markdown: {e}")
            return {"error": f"Markdown parsing failed: {e}", "raw_response": markdown_text[:500]}

    def _parse_content_markdown(self, markdown_text: str) -> Optional[Dict[str, Any]]:
        """Parse structured markdown content into dictionary"""
        try:
            text = markdown_text.strip()
            content = {}

            # Extract sections using regex - handle H2 sections within BODY_CONTENT
            patterns = {
                'meta_title': r'## META_TITLE\s*\n(.*?)(?=##\s+(?:META_DESCRIPTION|MAIN_TITLE|BODY_CONTENT|IMAGE_PROMPT|INTERNAL_LINKS|EXTERNAL_LINKS)|$)',
                'meta_description': r'## META_DESCRIPTION\s*\n(.*?)(?=##\s+(?:META_TITLE|MAIN_TITLE|BODY_CONTENT|IMAGE_PROMPT|INTERNAL_LINKS|EXTERNAL_LINKS)|$)',
                'title': r'## MAIN_TITLE\s*\n(.*?)(?=##\s+(?:META_TITLE|META_DESCRIPTION|BODY_CONTENT|IMAGE_PROMPT|INTERNAL_LINKS|EXTERNAL_LINKS)|$)',
                'body': r'## BODY_CONTENT\s*\n(.*?)(?=##\s+(?:IMAGE_PROMPT|INTERNAL_LINKS|EXTERNAL_LINKS)|$)',
                'image_prompt': r'## IMAGE_PROMPT\s*\n(.*?)(?=##\s+(?:META_TITLE|META_DESCRIPTION|MAIN_TITLE|BODY_CONTENT|INTERNAL_LINKS|EXTERNAL_LINKS)|$)',
                'internal_links_raw': r'## INTERNAL_LINKS\s*\n(.*?)(?=##\s+(?:META_TITLE|META_DESCRIPTION|MAIN_TITLE|BODY_CONTENT|IMAGE_PROMPT|EXTERNAL_LINKS)|$)',
                'external_links_raw': r'## EXTERNAL_LINKS\s*\n(.*?)(?=##\s+(?:META_TITLE|META_DESCRIPTION|MAIN_TITLE|BODY_CONTENT|IMAGE_PROMPT|INTERNAL_LINKS)|$)'
            }

            # Extract each section
            for key, pattern in patterns.items():
                match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if match:
                    content[key] = match.group(1).strip()
                else:
                    content[key] = ""

            # Parse internal links
            internal_links = []
            if content.get('internal_links_raw'):
                for line in content['internal_links_raw'].split('\n'):
                    line = line.strip()
                    if line.startswith('-'):
                        # Parse format: - [Anchor text] -> /url/path (Context: description)
                        link_match = re.search(
                            r'-\s*\[(.*?)\]\s*->\s*(\S+)\s*\(Context:\s*(.*?)\)', line)
                        if link_match:
                            internal_links.append({
                                'anchor_text': str(link_match.group(1).strip()),
                                'suggested_url': str(link_match.group(2).strip()),
                                'context': str(link_match.group(3).strip())
                            })
            content['internal_links'] = internal_links

            # Parse external links
            external_links = []
            if content.get('external_links_raw'):
                for line in content['external_links_raw'].split('\n'):
                    line = line.strip()
                    if line.startswith('-'):
                        # Parse format: - [Anchor text] -> https://url.com (Context: description)
                        link_match = re.search(
                            r'-\s*\[(.*?)\]\s*->\s*(\S+)\s*\(Context:\s*(.*?)\)', line)
                        if link_match:
                            external_links.append({
                                'anchor_text': str(link_match.group(1).strip()),
                                'url': str(link_match.group(2).strip()),
                                'context': str(link_match.group(3).strip())
                            })
            content['external_links'] = external_links

            # Clean up bracket placeholders in text fields
            for key in ['meta_title', 'meta_description', 'title', 'body', 'image_prompt']:
                if content.get(key):
                    # Remove markdown bracket placeholders like [Less than 60 characters...]
                    content[key] = re.sub(r'^\[.*?\]\s*', '', content[key])

            return content

        except Exception as e:
            print(f"    ❌ Error parsing content markdown: {e}")
            return None

    def generate_content_with_gemini(self, keyword: str, research_data: Dict[str, Any]) -> Optional[BlogPost]:
        """Generate high-quality blog content using Gemini"""

        # Create simplified research summary for the prompt
        research_summary = ""
        if 'search_intent' in research_data:
            research_summary += f"Search Intent: {research_data['search_intent'][:200]}...\n"
        if 'semantic_keywords_list' in research_data:
            # First 10 keywords
            keywords = research_data['semantic_keywords_list'][:10]
            research_summary += f"Related Keywords: {', '.join(keywords)}\n"
        if 'content_angles' in research_data:
            research_summary += f"Content Angles: {research_data['content_angles'][:200]}...\n"

        content_prompt = f"""
        Write a comprehensive, in-depth blog post for the keyword: "{keyword}"
        
        Research insights:
        {research_summary}
        
        CRITICAL REQUIREMENTS:
        - MINIMUM 2500 words in the BODY_CONTENT section - this is NON-NEGOTIABLE
        - Target 3000-4000 words for maximum SEO impact
        - Write for maintenance managers, facility operators, and industrial decision-makers
        - Include actionable insights, practical advice, real-world examples, and step-by-step guidance
        - Avoid content similar to competitors: getmaintainx.com, limblecmms.com, upkeep.com
        - Cover the topic comprehensively with multiple angles and detailed explanations
        
        CONTENT STRUCTURE REQUIREMENTS:
        - Use multiple H2 sections (## headings) to organize content
        - Include H3 subsections (### headings) for detailed coverage
        - Provide concrete examples, case studies, and actionable tips
        - Include troubleshooting guides, best practices, and implementation steps
        - Add technical details, calculations, and industry standards where relevant
        
        Output in this EXACT structured markdown format:

        # Blog Post: {keyword}

        ## META_TITLE
        [Less than 60 characters, compelling and SEO-optimized]

        ## META_DESCRIPTION  
        [150-160 characters, includes keyword and call-to-action]

        ## MAIN_TITLE
        [Engaging H1 that includes the target keyword]

        ## BODY_CONTENT
        [MINIMUM 2500 words in clean Markdown format with proper H2 and H3 headings. This should be a comprehensive, detailed article covering all aspects of the topic. Include introduction, multiple main sections, practical guidance, examples, best practices, and conclusion.]

        ## IMAGE_PROMPT
        [Detailed prompt for generating a relevant hero image related to the keyword]

        ## INTERNAL_LINKS
        - [Anchor text for link 1] -> /suggested/url/path1 (Context: where this appears in the content)
        - [Anchor text for link 2] -> /suggested/url/path2 (Context: where this appears in the content)
        - [Anchor text for link 3] -> /suggested/url/path3 (Context: where this appears in the content)
        - [Anchor text for link 4] -> /suggested/url/path4 (Context: where this appears in the content)
        - [Anchor text for link 5] -> /suggested/url/path5 (Context: where this appears in the content)

        ## EXTERNAL_LINKS
        - [Anchor text for external link 1] -> https://authoritative-source1.com (Context: where this appears in the content)
        - [Anchor text for external link 2] -> https://authoritative-source2.com (Context: where this appears in the content)
        - [Anchor text for external link 3] -> https://authoritative-source3.com (Context: where this appears in the content)

        REMEMBER: The BODY_CONTENT section must be at least 2500 words. Write a thorough, comprehensive article that covers the topic in depth.
        """

        try:
            # Add retry logic for rate limiting
            max_retries = 3
            response = None
            for attempt in range(max_retries):
                try:
                    response = self.gemini_model.generate_content(  # type: ignore
                        content_prompt,
                        generation_config=genai.types.GenerationConfig(  # type: ignore
                            temperature=0.4,
                            max_output_tokens=12000,  # Increased for full 4000-word content
                        )
                    )
                    break  # Success, exit retry loop

                except Exception as e:
                    if "429" in str(e) or "quota" in str(e).lower():
                        wait_time = min(60 * (attempt + 1),
                                        300)  # Max 5 minutes
                        print(
                            f"    ⏳ Rate limit hit, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:  # Don't wait on last attempt
                            time.sleep(wait_time)
                            continue
                    raise e  # Re-raise if not rate limit or last attempt

            if response is None:
                raise Exception("Failed to get response from Gemini API")

            # Get the text content
            response_text = response.text

            # Parse markdown response into structured data
            print(f"    🔧 Parsing markdown content response...")
            content_data = self._parse_content_markdown(response_text)

            if not content_data:
                print(f"Could not parse markdown from content response")
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

    def download_image_from_url(self, image_url: str, keyword: str, output_dir: str = "generated_content") -> Optional[str]:
        """Download image from URL and save locally"""
        try:
            print(f"    📥 Downloading image from URL...")

            # Create safe filename based on keyword
            safe_keyword = re.sub(r'[^\w\s-]', '', keyword).strip()
            safe_keyword = re.sub(r'[-\s]+', '-', safe_keyword)

            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)

            # Download the image
            response = requests.get(image_url, stream=True, timeout=30)
            response.raise_for_status()

            # Determine file extension from content type or URL
            content_type = response.headers.get('content-type', '')
            if 'png' in content_type.lower():
                extension = '.png'
            elif 'jpeg' in content_type.lower() or 'jpg' in content_type.lower():
                extension = '.jpg'
            elif 'webp' in content_type.lower():
                extension = '.webp'
            else:
                # Default to .png for unknown types
                extension = '.png'

            # Create local filename
            local_filename = f"{safe_keyword[:50]}{extension}"
            local_filepath = os.path.join(output_dir, local_filename)

            # Save the image
            with open(local_filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"    ✅ Image saved to: {local_filepath}")
            return local_filepath

        except Exception as e:
            print(f"    ❌ Error downloading image: {e}")
            return None

    def save_base64_image(self, b64_data: str, keyword: str, output_dir: str = "generated_content") -> Optional[str]:
        """Save base64 image data to local file"""
        try:
            print(f"    💾 Saving base64 image data locally...")

            # Create safe filename based on keyword
            safe_keyword = re.sub(r'[^\w\s-]', '', keyword).strip()
            safe_keyword = re.sub(r'[-\s]+', '-', safe_keyword)

            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)

            # Decode base64 data
            image_data = base64.b64decode(b64_data)

            # Create local filename (GPT-4 Image typically returns PNG)
            local_filename = f"{safe_keyword[:50]}.png"
            local_filepath = os.path.join(output_dir, local_filename)

            # Save the image
            with open(local_filepath, 'wb') as f:
                f.write(image_data)

            print(f"    ✅ Base64 image saved to: {local_filepath}")
            return local_filepath

        except Exception as e:
            print(f"    ❌ Error saving base64 image: {e}")
            return None

    def generate_image_with_openai(self, image_prompt: str, keyword: str = "", output_dir: str = "generated_content") -> tuple[Optional[str], Optional[str]]:
        """Generate hero image using OpenAI GPT-4 Image Generation and save it locally"""
        try:
            print(f"    🎨 Generating image with prompt: {image_prompt}")
            print(f"    📏 Prompt length: {len(image_prompt)} characters")

            # Use the actual image prompt from Gemini
            print(f"    🤖 Calling OpenAI GPT-4 Image Generation API...")
            response = self.openai_client.images.generate(
                model="gpt-image-1",
                prompt=image_prompt,
                size="1024x1024",
                quality="medium",
                n=1,
            )

            print(f"    ✅ Image generated successfully!")
            if response.data and len(response.data) > 0:
                first_image = response.data[0]

                # GPT-4 Image returns base64 data, not URLs
                if hasattr(first_image, 'b64_json') and first_image.b64_json:
                    print(f"    📊 Received base64 image data")

                    if keyword:
                        local_path = self.save_base64_image(
                            first_image.b64_json, keyword, output_dir)
                        # For base64 images, we don't have a remote URL
                        return None, local_path
                    else:
                        return None, None

                # Fallback: check for URL (for compatibility with other models)
                elif hasattr(first_image, 'url') and first_image.url:
                    image_url = first_image.url
                    print(f"    🔗 Image URL: {image_url[:50]}...")

                    if keyword:
                        local_path = self.download_image_from_url(
                            image_url, keyword, output_dir)
                        return image_url, local_path
                    else:
                        return image_url, None
                else:
                    print(f"    ❌ No usable image data in response")
                    return None, None
            else:
                print(f"    ❌ No image data received from OpenAI")
                return None, None

        except Exception as e:
            print(
                f"    ❌ Error generating image with GPT-4 Image Generation: {e}")
            print(f"    ⚠️  No fallback model - returning None")
            return None, None

    def format_for_prismic(self, blog_post: BlogPost) -> Dict[str, Any]:
        """Format content for Prismic CMS with proper rich text structure"""

        # Convert markdown-style content to Prismic rich text format
        def convert_to_prismic_richtext(content: str) -> List[Dict[str, Any]]:
            paragraphs: List[Dict[str, Any]] = []
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
                    spans: List[Dict[str, Any]] = []
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
                "local_path": blog_post.local_image_path or "",
                "alt": f"Hero image for {blog_post.title}",
                "source": "gpt-image-1" if blog_post.local_image_path and not blog_post.image_url else "url"
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

    def save_output(self, prismic_data: Dict[str, Any], keyword: str, body_markdown: str, output_dir: str = "generated_content") -> tuple[str, str]:
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

        # Check if there's a local image file
        image_extensions = ['.png', '.jpg', '.jpeg', '.webp']
        for ext in image_extensions:
            image_file = os.path.join(output_dir, f"{safe_keyword[:50]}{ext}")
            if os.path.exists(image_file):
                print(f"  🖼️  Image: {image_file}")
                break

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
    filtered_keywords: List[str] = []
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
            image_url, local_image_path = generator.generate_image_with_openai(
                blog_post.image_prompt, keyword)
            blog_post.image_url = image_url
            blog_post.local_image_path = local_image_path

            # Format for Prismic
            print("  📋 Formatting for Prismic...")
            prismic_data = generator.format_for_prismic(blog_post)

            # Save output
            body_markdown = blog_post.body  # Get the original markdown body
            generator.save_output(
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
