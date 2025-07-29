import csv
import json
import requests
import time
import re
import base64
import subprocess
import logging
import datetime
from typing import List, Dict, Optional, Any, Tuple
from urllib.parse import urlparse
import os
from dotenv import load_dotenv
import google.generativeai as genai  # type: ignore
import openai
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, field_validator, model_validator

# Load environment variables
load_dotenv()

# Configure logging


def setup_logging():
    """Set up logging to write to the logs directory"""
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)

    # Create log filename with current date
    current_date = datetime.datetime.now().strftime('%Y%m%d')
    log_filename = f'logs/seo_generator_{current_date}.log'

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()  # Keep console output for user interaction
        ]
    )

    # Create logger
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("SEO Content Generator session started")
    logger.info("=" * 50)

    return logger


# Initialize logger
logger = setup_logging()


class ContentRequirements(BaseModel):
    """Configuration for content generation requirements"""
    meta_title_max: int = Field(default=60, ge=1, le=100)
    meta_description_min: int = Field(default=50, ge=50, le=160)
    meta_description_max: int = Field(default=160, ge=50, le=160)
    word_count_min: int = Field(default=2500, ge=1000, le=5000)
    word_count_max: int = Field(default=4000, ge=2500, le=10000)
    internal_references: int = Field(default=5, ge=1, le=10)
    external_references: int = Field(default=3, ge=1, le=10)

    @model_validator(mode='after')
    def validate_ranges(self):
        if self.meta_description_max < self.meta_description_min:
            raise ValueError(
                'meta_description_max must be >= meta_description_min')
        if self.word_count_max < self.word_count_min:
            raise ValueError('word_count_max must be >= word_count_min')
        return self


class BlogPost(BaseModel):
    """Model for a generated blog post"""
    keyword: str = Field(..., min_length=1, max_length=200)
    meta_title: str = Field(..., min_length=1, max_length=100)
    meta_description: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=500)
    image_prompt: str = Field(..., min_length=10, max_length=1000)
    image_url: Optional[str] = Field(default=None)
    local_image_path: Optional[str] = Field(default=None)
    internal_links: Optional[List[str]] = Field(default_factory=list)
    external_links: Optional[List[str]] = Field(default_factory=list)

    @field_validator('body')
    @classmethod
    def validate_word_count(cls, v: str) -> str:
        word_count = len(v.split())
        if word_count < 2000:
            raise ValueError(
                f'Body must have at least 2000 words, got {word_count}')
        return v

    @field_validator('meta_description')
    @classmethod
    def validate_meta_description_length(cls, v: str) -> str:
        if len(v) > 160:
            # Truncate to 160 chars, preferably at word boundary
            truncated = v[:160]
            last_space = truncated.rfind(' ')
            if last_space > 140:  # Only use word boundary if it's reasonably close to 160
                truncated = truncated[:last_space]
            logger.warning(
                f"Meta description truncated from {len(v)} to {len(truncated)} characters")
            return truncated
        elif len(v) < 50:
            logger.warning(
                f"Meta description is short ({len(v)} chars) but keeping as-is")
        return v


class SERPEntry(BaseModel):
    """Model for SERP (Search Engine Results Page) data entry"""
    title: str = Field(default="")
    url: str = Field(default="")
    position: str = Field(default="")
    traffic: str = Field(default="")
    difficulty: str = Field(default="")
    volume: str = Field(default="")
    cpc: str = Field(default="")
    type: str = Field(default="")
    intents: str = Field(default="")


class ResearchData(BaseModel):
    """Model for keyword research data"""
    keyword: str
    search_intent: str = Field(default="")
    content_gaps: str = Field(default="")
    pain_points: str = Field(default="")
    semantic_keywords: str = Field(default="")
    content_angles: str = Field(default="")
    competitive_landscape: str = Field(default="")
    content_structure: str = Field(default="")
    industry_trends: str = Field(default="")
    authoritative_sources: str = Field(default="")
    semantic_keywords_list: List[str] = Field(default_factory=list)
    error: Optional[str] = Field(default=None)


class ContentData(BaseModel):
    """Model for parsed content data"""
    meta_title: str = Field(default="")
    meta_description: str = Field(default="")
    title: str = Field(default="")
    body: str = Field(default="")
    image_prompt: str = Field(default="")


class PrismicData(BaseModel):
    """Model for Prismic CMS formatted data"""
    meta_title: str
    meta_description: str
    title: str
    keyword: str
    hero_image: Dict[str, Any]
    image_prompt: str
    markdown_body: str
    word_count: int = Field(ge=0)
    link_count: int = Field(ge=0)


class SEOContentGenerator:
    """Main class for generating SEO-optimized content with proper typing"""

    def __init__(self) -> None:
        # Configure Gemini 2.5 Pro
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))  # type: ignore
        self.gemini_model = genai.GenerativeModel(  # type: ignore
            'gemini-2.5-pro-preview-03-25')

        self.openai_client: openai.OpenAI = openai.OpenAI(
            api_key=os.getenv('OPENAI_API_KEY')
        )
        self.requirements: ContentRequirements = ContentRequirements()
        self.existing_content: List[str] = []
        self.competitor_domains: List[str] = [
            'getmaintainx.com',
            'limblecmms.com',
            'upkeep.com'
        ]
        self.available_internal_urls: List[str] = []  # Cache for sitemap URLs

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

                        # Log available columns for debugging
                        fieldnames = reader.fieldnames
                        logger.debug(
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
                    logger.info(
                        f"Successfully loaded {len(keyword_data)} unique keywords with SERP data using {encoding} encoding")
                    return keyword_data

            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception as e:
                logger.warning(f"Error with {encoding} encoding: {e}")
                continue

        logger.error("Failed to load CSV with any supported encoding")
        return {}

    def load_existing_content_from_sitemap(self, sitemap_url: str) -> List[str]:
        """Load existing blog slugs from the sitemap to avoid duplicates"""
        existing_slugs: List[str] = []
        try:
            logger.info(f"Fetching sitemap from {sitemap_url}")
            response = requests.get(sitemap_url, timeout=15)
            response.raise_for_status()

            # Parse XML sitemap
            soup = BeautifulSoup(response.content, 'xml')
            urls = soup.find_all('loc')

            # Cache all available URLs for internal link verification
            self.available_internal_urls = []

            for url in urls:
                if url.text:
                    # Store full URL path for internal link verification
                    parsed_url = urlparse(url.text)  # type: ignore
                    path = parsed_url.path  # type: ignore
                    if path and path != '/':
                        self.available_internal_urls.append(
                            path)  # type: ignore

                    # Extract blog slugs for content overlap checking
                    if '/blog/' in url.text:  # type: ignore
                        if path.startswith('/blog/'):  # type: ignore
                            # Remove /blog/ prefix and trailing slashes
                            slug = path.replace(  # type: ignore
                                '/blog/', '', 1).strip('/')  # type: ignore
                            if slug:
                                # Convert slug to words for better matching
                                slug_words = slug.replace(  # type: ignore
                                    '-', ' ')  # type: ignore
                                existing_slugs.append(
                                    slug_words)  # type: ignore

            logger.info(
                f"Found {len(existing_slugs)} existing blog posts from sitemap")
            logger.info(
                f"Cached {len(self.available_internal_urls)} internal URLs for verification")
            return existing_slugs

        except Exception as e:
            logger.error(f"Error loading sitemap: {e}")
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

    def verify_internal_url(self, url_path: str) -> bool:
        """Verify if an internal URL path exists in the sitemap"""
        if not url_path.startswith('/'):
            url_path = '/' + url_path

        # Check exact match
        if url_path in self.available_internal_urls:
            return True

        # Check with trailing slash
        if url_path.rstrip('/') + '/' in self.available_internal_urls:
            return True

        # Check without trailing slash
        if url_path.rstrip('/') in self.available_internal_urls:
            return True

        return False

    def verify_external_url(self, url: str) -> bool:
        """Verify if an external URL is accessible"""
        try:
            # Use HEAD request to check if URL exists without downloading content
            response = requests.head(url, timeout=10, allow_redirects=True)
            return response.status_code < 400
        except Exception:
            try:
                # Fallback to GET request if HEAD doesn't work
                response = requests.get(url, timeout=10, allow_redirects=True)
                return response.status_code < 400
            except Exception:
                return False

    def validate_and_clean_markdown_links(self, markdown_content: str) -> str:
        """Validate and clean links in markdown content"""
        logger.info("Validating and cleaning markdown links...")

        # Find all markdown links [text](url)
        link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        links = re.findall(link_pattern, markdown_content)

        cleaned_content = markdown_content
        validated_count = 0
        removed_count = 0

        for link_text, link_url in links:
            original_link = f'[{link_text}]({link_url})'

            # Check if it's an internal or external link
            if link_url.startswith('/') or not link_url.startswith('http'):
                # Internal link
                if self.verify_internal_url(link_url):
                    logger.debug(f"Internal link verified: {link_url}")
                    validated_count += 1
                else:
                    logger.warning(
                        f"Invalid internal link removed: {link_url}")
                    # Remove the link but keep the text
                    cleaned_content = cleaned_content.replace(
                        original_link, link_text)
                    removed_count += 1
            else:
                # External link
                if self.verify_external_url(link_url):
                    logger.debug(f"External link verified: {link_url}")
                    validated_count += 1
                else:
                    logger.warning(
                        f"Invalid external link removed: {link_url}")
                    # Remove the link but keep the text
                    cleaned_content = cleaned_content.replace(
                        original_link, link_text)
                    removed_count += 1

        logger.info(
            f"Link validation: {validated_count} verified, {removed_count} removed")
        return cleaned_content

    def research_keyword_with_gemini(self, keyword: str, serp_data: Optional[List[Dict[str, Any]]] = None) -> ResearchData:
        """Use Gemini to analyze keyword and competition"""

        logger.info(f"Starting deep research for keyword: '{keyword}'")
        start_time: float = time.time()

        # Build SERP analysis section
        serp_analysis: str = ""
        if serp_data:
            logger.info(f"Analyzing {len(serp_data)} SERP results...")
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
            logger.warning(f"No SERP data available for '{keyword}'")

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

        logger.debug(
            f"Sending research prompt to Gemini (length: {len(research_prompt)} chars)")

        try:
            logger.info(f"Calling Gemini API...")
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
                        logger.warning(
                            f"Rate limit hit, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:  # Don't wait on last attempt
                            time.sleep(wait_time)
                            continue
                    raise e  # Re-raise if not rate limit or last attempt

            if response is None:
                raise Exception("Failed to get response from Gemini API")

            api_time = time.time() - api_start
            logger.info(f"Gemini API call took {api_time:.2f} seconds")

            # Get the text content
            response_text = response.text
            response_length = len(response_text)
            logger.info(f"Received response ({response_length} characters)")

            # Show first 200 chars of response for debugging
            preview = response_text[:200].replace('\n', ' ')
            logger.debug(f"Response preview: {preview}...")

            # Parse markdown response into structured data
            logger.info(f"Parsing markdown response...")
            research_dict = self._parse_research_markdown(
                response_text, keyword)

            if research_dict and not research_dict.get("error"):
                logger.info(
                    f"Successfully parsed markdown with {len(research_dict)} sections")
                logger.debug(
                    f"Research data keys: {list(research_dict.keys())}")
                research_data = ResearchData(**research_dict)
            else:
                logger.error(f"Failed to parse markdown response")
                research_data = ResearchData(
                    keyword=keyword,
                    error="Failed to parse research data"
                )

            total_time: float = time.time() - start_time
            logger.info(
                f"Research completed in {total_time:.2f} seconds total")

            return research_data

        except Exception as e:
            error_time: float = time.time() - start_time
            logger.error(
                f"Error in keyword research after {error_time:.2f} seconds: {e}")
            return ResearchData(keyword=keyword, error=str(e))

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
            logger.error(f"Error parsing markdown: {e}")
            return {"error": f"Markdown parsing failed: {e}", "raw_response": markdown_text[:500]}

    def _parse_content_markdown(self, markdown_text: str) -> Optional[ContentData]:
        """Parse structured markdown content into ContentData model"""
        try:
            text: str = markdown_text.strip()
            content: Dict[str, str] = {}

            # Extract sections using regex - simplified format without separate link sections
            patterns = {
                'meta_title': r'## META_TITLE\s*\n(.*?)(?=##\s+(?:META_DESCRIPTION|MAIN_TITLE|BODY_CONTENT|IMAGE_PROMPT)|$)',
                'meta_description': r'## META_DESCRIPTION\s*\n(.*?)(?=##\s+(?:META_TITLE|MAIN_TITLE|BODY_CONTENT|IMAGE_PROMPT)|$)',
                'title': r'## MAIN_TITLE\s*\n(.*?)(?=##\s+(?:META_TITLE|META_DESCRIPTION|BODY_CONTENT|IMAGE_PROMPT)|$)',
                'body': r'## BODY_CONTENT\s*\n(.*?)(?=##\s+(?:IMAGE_PROMPT)|$)',
                'image_prompt': r'## IMAGE_PROMPT\s*\n(.*?)(?=##\s+(?:META_TITLE|META_DESCRIPTION|MAIN_TITLE|BODY_CONTENT)|$)',
            }

            # Extract each section
            for key, pattern in patterns.items():
                match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if match:
                    content[key] = match.group(1).strip()
                else:
                    content[key] = ""

            # Clean up bracket placeholders in text fields
            for key in ['meta_title', 'meta_description', 'title', 'body', 'image_prompt']:
                if content.get(key):
                    # Remove markdown bracket placeholders like [Less than 60 characters...]
                    content[key] = re.sub(r'^\[.*?\]\s*', '', content[key])

            return ContentData(**content)

        except Exception as e:
            logger.error(f"Error parsing content markdown: {e}")
            return None

    def generate_content_with_gemini(self, keyword: str, research_data: ResearchData) -> Optional[BlogPost]:
        """Generate high-quality blog content using Gemini"""

        # Create simplified research summary for the prompt
        research_summary: str = ""
        if research_data.search_intent:
            research_summary += f"Search Intent: {research_data.search_intent[:200]}...\n"
        if research_data.semantic_keywords_list:
            # First 10 keywords
            keywords = research_data.semantic_keywords_list[:10]
            research_summary += f"Related Keywords: {', '.join(keywords)}\n"
        if research_data.content_angles:
            research_summary += f"Content Angles: {research_data.content_angles[:200]}...\n"

        # Build available internal URLs context
        internal_urls_context = ""
        if self.available_internal_urls:
            # Show a sample of available URLs for reference
            # First 20 URLs as examples
            sample_urls = self.available_internal_urls[:20]
            internal_urls_context = f"""

        AVAILABLE INTERNAL URLS (for reference when adding internal links):
        {chr(10).join(sample_urls)}
        (And {len(self.available_internal_urls)} total available internal URLs)
        """

        content_prompt = f"""
        Write a comprehensive, in-depth blog post for the keyword: "{keyword}"

        Research insights:
        {research_summary}
        {internal_urls_context}

        CRITICAL REQUIREMENTS:
        - MINIMUM 2500 words in the BODY_CONTENT section - this is NON-NEGOTIABLE
        - Target 3000-4000 words for maximum SEO impact
        - Write for maintenance managers, facility operators, and industrial decision-makers
        - Include actionable insights, practical advice, real-world examples, and step-by-step guidance
        - Avoid content similar to competitors: getmaintainx.com, limblecmms.com, upkeep.com
        - Cover the topic comprehensively with multiple angles and detailed explanations
        - The year is 2025.

        CONTENT STRUCTURE REQUIREMENTS:
        - Use multiple H2 sections (## headings) to organize content
        - Include H3 subsections (### headings) for detailed coverage
        - Provide concrete examples, case studies, and actionable tips
        - Include troubleshooting guides, best practices, and implementation steps
        - Add technical details, calculations, and industry standards where relevant

        MARKDOWN LINK REQUIREMENTS:
        - EMBED 3-5 internal links directly in the BODY_CONTENT using markdown format: [anchor text](/url/path)
        - Use ONLY URLs from the available internal URLs list provided above
        - EMBED 2-3 external links to authoritative sources using markdown format: [anchor text](https://example.com)
        - Use reputable domains like: isixsigma.com, nist.gov, ieee.org, asme.org, reliabilityweb.com, maintenanceworld.com
        - Place links naturally in context where they add value

        IMAGE PROMPT REQUIREMENTS:
        - Generate a hero image for the blog post using the IMAGE_PROMPT section
        - The image should be relevant manufacturing, maintenance, and operations and the keyword and the content of the blog post
        - The image should be a high-quality, photo realistic, professional image
        - The image should not have any words or text.
        - When showing multiple people, use different genders and ethnicities.
        - People should be from diverse backgrounds.
        - People should be wearing protective equipment, such as hard hats or hair nets, safety glasses, and high-visibility clothing or PPE.

        Output in this EXACT structured markdown format:

        # Blog Post: {keyword}

        ## META_TITLE
        [Less than 60 characters, compelling and SEO-optimized]

        ## META_DESCRIPTION
        [150-160 characters, includes keyword and call-to-action]

        ## MAIN_TITLE
        [Engaging H1 that includes the target keyword]

        ## BODY_CONTENT
        [MINIMUM 2500 words in clean Markdown format with proper H2 and H3 headings. Include 3-5 internal links and 2-3 external links embedded naturally in the content using markdown link syntax [text](url). This should be a comprehensive, detailed article covering all aspects of the topic.]

        ## IMAGE_PROMPT
        [Detailed prompt for generating a relevant hero image related to the keyword]

        REMEMBER:
        - The BODY_CONTENT section must be at least 2500 words
        - Include links directly in the markdown content, not as separate sections
        - Only use internal URLs from the provided list
        - Test external links to ensure they work
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
                        logger.warning(
                            f"Rate limit hit, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:  # Don't wait on last attempt
                            time.sleep(wait_time)
                            continue
                    raise e  # Re-raise if not rate limit or last attempt

            if response is None:
                raise Exception("Failed to get response from Gemini API")

            # Get the text content
            response_text = response.text

            # Parse markdown response into structured data
            logger.info(f"Parsing markdown content response...")
            content_data = self._parse_content_markdown(response_text)

            if not content_data:
                logger.error(f"Could not parse markdown from content response")
                return None

            # Validate and clean links in the markdown body
            cleaned_body: str = self.validate_and_clean_markdown_links(
                content_data.body)

            return BlogPost(
                keyword=keyword,
                meta_title=content_data.meta_title,
                meta_description=content_data.meta_description,
                title=content_data.title,
                body=cleaned_body,
                image_prompt=content_data.image_prompt,
                internal_links=[],  # No longer using separate link sections
                external_links=[]   # Links are now embedded in the markdown
            )

        except Exception as e:
            logger.error(f"Error generating content: {e}")
            return None

    def download_image_from_url(self, image_url: str, keyword: str, output_dir: str = "generated_content") -> Optional[str]:
        """Download image from URL and save locally"""
        try:
            logger.info(f"Downloading image from URL...")

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

            logger.info(f"Image saved to: {local_filepath}")
            return local_filepath

        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None

    def save_base64_image(self, b64_data: str, keyword: str, output_dir: str = "generated_content") -> Optional[str]:
        """Save base64 image data to local file"""
        try:
            logger.info(f"Saving base64 image data locally...")

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

            logger.info(f"Base64 image saved to: {local_filepath}")
            return local_filepath

        except Exception as e:
            logger.error(f"Error saving base64 image: {e}")
            return None

    def generate_image_with_openai(self, image_prompt: str, keyword: str = "", output_dir: str = "generated_content") -> Tuple[Optional[str], Optional[str]]:
        """Generate hero image using OpenAI GPT-4 Image Generation and save it locally"""
        try:
            logger.info(f"Generating image with prompt: {image_prompt}")
            logger.debug(f"Prompt length: {len(image_prompt)} characters")

            # Use the actual image prompt from Gemini
            logger.info(f"Calling OpenAI GPT-4 Image Generation API...")
            response = self.openai_client.images.generate(
                model="gpt-image-1",
                prompt=image_prompt,
                size="1536x1024",
                quality="auto",
                n=1,
            )

            logger.info(f"Image generated successfully!")
            if response.data and len(response.data) > 0:
                first_image = response.data[0]

                # GPT-4 Image returns base64 data, not URLs
                if hasattr(first_image, 'b64_json') and first_image.b64_json:
                    logger.info(f"Received base64 image data")

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
                    logger.info(f"Image URL: {image_url[:50]}...")

                    if keyword:
                        local_path = self.download_image_from_url(
                            image_url, keyword, output_dir)
                        return image_url, local_path
                    else:
                        return image_url, None
                else:
                    logger.error(f"No usable image data in response")
                    return None, None
            else:
                logger.error(f"No image data received from OpenAI")
                return None, None

        except Exception as e:
            logger.error(
                f"Error generating image with GPT-4 Image Generation: {e}")
            logger.warning(f"No fallback model - returning None")
            return None, None

    def format_for_prismic(self, blog_post: BlogPost) -> PrismicData:
        """Format content for Prismic CMS with the markdown body for the new slice"""

        hero_image: Dict[str, Any] = {
            "url": blog_post.image_url or "",
            "local_path": blog_post.local_image_path or "",
            "alt": f"Hero image for {blog_post.title}",
            "source": "gpt-image-1" if blog_post.local_image_path and not blog_post.image_url else "url"
        }

        return PrismicData(
            meta_title=blog_post.meta_title,
            meta_description=blog_post.meta_description,
            title=blog_post.title,
            keyword=blog_post.keyword,
            hero_image=hero_image,
            image_prompt=blog_post.image_prompt,
            markdown_body=blog_post.body,  # Raw markdown for the new slice
            word_count=len(blog_post.body.split()),
            link_count=len(re.findall(
                r'\[([^\]]+)\]\(([^\)]+)\)', blog_post.body))
        )

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
            logger.warning(
                f"Incomplete content found for '{keyword}' (JSON: {json_exists}, MD: {md_exists})")
            return False
        else:
            return False

    def save_output(self, prismic_data: PrismicData, keyword: str, body_markdown: str, output_dir: str = "generated_content") -> Tuple[str, str]:
        """Save generated content to JSON file and separate markdown file"""
        os.makedirs(output_dir, exist_ok=True)

        # Create safe filename
        safe_keyword: str = re.sub(r'[^\w\s-]', '', keyword).strip()
        safe_keyword = re.sub(r'[-\s]+', '-', safe_keyword)

        # Save JSON with markdown body reference
        json_data = prismic_data.model_dump()
        json_data['markdown_body'] = "[See separate markdown file]"

        json_filename = f"{safe_keyword[:50]}.json"
        json_filepath = os.path.join(output_dir, json_filename)

        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        # Save Markdown body separately (this is the content for Prismic)
        md_filename = f"{safe_keyword[:50]}.md"
        md_filepath = os.path.join(output_dir, md_filename)

        with open(md_filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {prismic_data.title}\n\n")
            f.write(f"**Keyword:** {keyword}\n\n")
            f.write(f"**Meta Title:** {prismic_data.meta_title}\n\n")
            f.write(
                f"**Meta Description:** {prismic_data.meta_description}\n\n")
            f.write(f"**Word Count:** {prismic_data.word_count}\n\n")
            f.write(f"**Link Count:** {prismic_data.link_count}\n\n")
            f.write("---\n\n")
            f.write(body_markdown)

        logger.info(f"Content saved to:")
        logger.info(f"  JSON: {json_filepath}")
        logger.info(f"  Markdown: {md_filepath}")
        logger.info(
            f"  Stats: {prismic_data.word_count} words, {prismic_data.link_count} links")

        # Check if there's a local image file
        image_extensions = ['.png', '.jpg', '.jpeg', '.webp']
        for ext in image_extensions:
            image_file = os.path.join(output_dir, f"{safe_keyword[:50]}{ext}")
            if os.path.exists(image_file):
                logger.info(f"  Image: {image_file}")
                break

        return json_filepath, md_filepath

    def upload_to_prismic(self, json_filepath: str, skip_upload: bool = False) -> Dict[str, Any]:
        """Upload generated content to Prismic CMS using Node.js script"""
        try:
            logger.info(f"Uploading to Prismic...")

            # Prepare command
            cmd = ["node", "prismic_uploader.js", json_filepath]
            if skip_upload:
                cmd.append("--skip-upload")

            # Run the Node.js uploader
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )

            if result.returncode == 0:
                if skip_upload:
                    logger.info(f"Prismic upload test completed successfully")
                else:
                    logger.info(f"Successfully uploaded to Prismic")
                return {
                    "success": True,
                    "output": result.stdout,
                    "skipped": skip_upload
                }
            else:
                logger.error(f"Prismic upload failed:")
                logger.error(f"Error: {result.stderr}")
                return {
                    "success": False,
                    "error": result.stderr,
                    "output": result.stdout
                }

        except Exception as e:
            logger.error(f"Error calling Prismic uploader: {e}")
            return {
                "success": False,
                "error": str(e)
            }


def main() -> None:
    """Main function to run the SEO content generator"""
    generator: SEOContentGenerator = SEOContentGenerator()

    print("🚀 SEO Content Generator for f7i.ai")
    print("=" * 50)

    # Get CSV file path
    csv_path: str = input(
        "Enter path to your Ahrefs keyword CSV file: ").strip()
    if not os.path.exists(csv_path):
        print("❌ CSV file not found!")
        return

    # Get sitemap URL
    sitemap_url: str = input(
        "Enter sitemap URL (default: https://f7i.ai/sitemap.xml): ").strip()
    if not sitemap_url:
        sitemap_url = "https://f7i.ai/sitemap.xml"

    # Get Prismic upload preference
    prismic_choice: str = input(
        "Upload to Prismic after generation? (y/n/test) [test]: ").strip().lower()
    if not prismic_choice:
        prismic_choice = "test"

    upload_to_prismic: bool = prismic_choice in ['y', 'yes', 'test']
    skip_prismic_upload: bool = prismic_choice == "test"

    if upload_to_prismic:
        if skip_prismic_upload:
            print(
                "🧪 Prismic test mode: Will validate uploads without actually creating documents")
        else:
            print("📤 Prismic upload enabled: Will create documents in Prismic CMS")
    else:
        print("⏭️  Prismic upload disabled: Only local files will be created")

    # Load keywords with SERP data
    keyword_data: Dict[str, List[Dict[str, Any]]
                       ] = generator.load_keywords_from_csv(csv_path)
    if not keyword_data:
        print("❌ No keywords found in CSV!")
        logger.error("No keywords found in CSV file")
        return

    # Load existing content from sitemap
    print(f"\n🔍 Loading existing content from sitemap: {sitemap_url}")
    logger.info(f"Loading existing content from sitemap: {sitemap_url}")
    existing_content: List[str] = generator.load_existing_content_from_sitemap(
        sitemap_url)

    # Filter out keywords that overlap with existing content OR already have generated content
    filtered_keywords: List[str] = []
    skipped_overlap: int = 0
    skipped_existing: int = 0

    for keyword in keyword_data.keys():
        # Check if content already exists
        if generator.check_existing_content(keyword):
            print(f"✅ Skipping '{keyword}' - content already generated")
            logger.info(f"Skipping '{keyword}' - content already generated")
            skipped_existing += 1
            continue

        # Check for content overlap with existing blog
        if generator.check_keyword_overlap(keyword, existing_content):
            print(
                f"⚠️  Skipping '{keyword}' - overlaps with existing blog content")
            logger.warning(
                f"Skipping '{keyword}' - overlaps with existing blog content")
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
    generation_stats = {
        "total": len(filtered_keywords),
        "successful": 0,
        "failed": 0,
        "prismic_uploaded": 0,
        "prismic_failed": 0,
        "prismic_tested": 0
    }

    for i, keyword in enumerate(filtered_keywords, 1):
        print(
            f"\n📝 Processing keyword {i}/{len(filtered_keywords)}: {keyword}")
        logger.info(
            f"Processing keyword {i}/{len(filtered_keywords)}: {keyword}")

        try:
            # Research keyword with SERP data
            print("  🔬 Researching keyword with SERP analysis...")
            logger.info("Researching keyword with SERP analysis...")
            serp_data = keyword_data.get(keyword, [])
            research_data = generator.research_keyword_with_gemini(
                keyword, serp_data)

            # Generate content
            print("  ✍️  Generating content...")
            logger.info("Generating content...")
            blog_post = generator.generate_content_with_gemini(
                keyword, research_data)

            if not blog_post:
                print(f"  ❌ Failed to generate content for: {keyword}")
                logger.error(f"Failed to generate content for: {keyword}")
                generation_stats["failed"] += 1
                continue

            # Generate image
            print("  🎨 Generating hero image...")
            logger.info("Generating hero image...")
            image_url, local_image_path = generator.generate_image_with_openai(
                blog_post.image_prompt, keyword)
            blog_post.image_url = image_url
            blog_post.local_image_path = local_image_path

            # Format for Prismic
            print("  📋 Formatting for Prismic...")
            logger.info("Formatting for Prismic...")
            prismic_data = generator.format_for_prismic(blog_post)

            # Save output
            body_markdown = blog_post.body  # Get the original markdown body
            json_path, _ = generator.save_output(
                prismic_data, keyword, body_markdown)
            print(f"  ✅ Content generated successfully!")
            logger.info(f"Content generated successfully for: {keyword}")
            generation_stats["successful"] += 1

            # Upload to Prismic if enabled
            if upload_to_prismic:
                prismic_result = generator.upload_to_prismic(
                    json_path, skip_prismic_upload)

                if prismic_result["success"]:
                    if prismic_result.get("skipped"):
                        generation_stats["prismic_tested"] += 1
                    else:
                        print(f"  🚀 Content published to Prismic CMS!")
                        logger.info(
                            f"Content published to Prismic CMS for: {keyword}")
                        generation_stats["prismic_uploaded"] += 1
                else:
                    print(f"  ⚠️  Prismic upload failed, but content saved locally")
                    print(
                        f"     You can retry later with: node prismic_uploader.js {json_path}")
                    logger.error(f"Prismic upload failed for: {keyword}")
                    generation_stats["prismic_failed"] += 1

            # Rate limiting
            time.sleep(2)

        except Exception as e:
            print(f"  ❌ Error processing '{keyword}': {e}")
            logger.error(f"Error processing '{keyword}': {e}")
            generation_stats["failed"] += 1
            continue

    # Final summary
    print(f"\n🎉 Content generation complete!")
    print(f"📊 Final Statistics:")
    print(f"   • Total keywords processed: {generation_stats['total']}")
    print(f"   • Successfully generated: {generation_stats['successful']}")
    print(f"   • Failed: {generation_stats['failed']}")

    if upload_to_prismic:
        if skip_prismic_upload:
            print(
                f"   • Prismic tests passed: {generation_stats['prismic_tested']}")
        else:
            print(
                f"   • Uploaded to Prismic: {generation_stats['prismic_uploaded']}")
            if generation_stats['prismic_failed'] > 0:
                print(
                    f"   • Prismic upload failed: {generation_stats['prismic_failed']}")

    print(f"\n📁 Check the 'generated_content' folder for your files.")

    logger.info("SEO content generation session completed")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
