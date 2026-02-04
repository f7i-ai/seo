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
from google import genai as genai_new  # type: ignore
import openai
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError

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
        # Configure Gemini 3 Pro
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))  # type: ignore
        self.gemini_model = genai.GenerativeModel(  # type: ignore
            'gemini-3-pro-preview')

        # Configure Gemini image generation client (uses newer SDK)
        self.gemini_image_client = genai_new.Client(  # type: ignore
            api_key=os.getenv('GEMINI_API_KEY')
        )

        self.openai_client: openai.OpenAI = openai.OpenAI(
            api_key=os.getenv('OPENAI_API_KEY')
        )
        self.requirements: ContentRequirements = ContentRequirements()
        self.existing_content: List[str] = []
        self.expansion_stats: Dict[str, int] = {"attempted": 0, "successful": 0}
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

            # Add retry logic for rate limiting and timeouts
            max_retries = 3
            response = None
            for attempt in range(max_retries):
                try:
                    response = self.gemini_model.generate_content(  # type: ignore
                        research_prompt,
                        generation_config=genai.types.GenerationConfig(  # type: ignore
                            temperature=0.3,
                            max_output_tokens=4000,  # Reduced for free tier
                        ),
                        request_options={"timeout": 120}  # 2 minute timeout
                    )
                    break  # Success, exit retry loop

                except Exception as e:
                    error_str = str(e).lower()
                    is_retryable = (
                        "429" in str(e) or
                        "quota" in error_str or
                        "504" in str(e) or
                        "deadline" in error_str or
                        "timeout" in error_str
                    )
                    if is_retryable:
                        wait_time = min(30 * (attempt + 1), 90)  # Max 90 seconds
                        logger.warning(
                            f"Retryable error ({e}), waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:  # Don't wait on last attempt
                            time.sleep(wait_time)
                            continue
                    raise e  # Re-raise if not retryable or last attempt

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

    def _get_pillar_prompt(self, keyword: str, research_summary: str, internal_urls_context: str) -> str:
        """Generate the prompt for pillar/hub content - longer, broader coverage with extensive internal linking"""
        return f"""
        Write a comprehensive PILLAR GUIDE for the topic: "{keyword}"

        Research insights:
        {research_summary}
        {internal_urls_context}

        CRITICAL THINKING PHILOSOPHY - THIS IS NON-NEGOTIABLE:

        Do NOT write generic "best practices" content. The reliability industry is drowning in superficial advice that sounds good but doesn't survive contact with reality. Your job is to write content that a 20-year reliability veteran would respect.

        QUESTION EVERYTHING:
        - If you mention a metric (OEE, MTBF, etc.), ask: Is this actually the right thing to measure? When does this metric mislead people? What are they really trying to understand?
        - If you mention a "best practice," ask: When does this practice fail? What context is required for it to work? What are organizations actually doing wrong when they adopt it?
        - If you recommend a technology or approach, ask: What are the trade-offs? When should someone NOT do this? What's the cheaper/simpler alternative that might work just as well?

        THE "JOHN SEWELL TEST" - For every section, ask:
        1. Am I describing the actual PROBLEM, or just a symptom?
        2. Am I helping readers make better DECISIONS, or just giving them more data to ignore?
        3. Would a smart reliability engineer read this and learn something, or roll their eyes?

        AVOID THESE CONTENT FAILURES:
        - Bullet-point lists without explanation (if you list 5 things, explain WHY each matters and WHEN each fails)
        - Metrics without context (don't just say "track OEE" - explain when OEE is useful vs. when it's a vanity metric that hides real problems)
        - "Best practices" without trade-offs (every approach has downsides - acknowledge them)
        - Solutions without problem definition (most organizations fix the wrong things because they confuse symptoms with root causes)
        - Generic advice that could apply to any industry (be specific to this topic's context)

        WHAT MAKES CONTENT VALUABLE:
        - Challenge conventional wisdom when appropriate
        - Acknowledge complexity and nuance
        - Explain the "why" behind every recommendation
        - Include honest trade-offs and limitations
        - Give readers frameworks for DECISIONS, not just information to collect
        - Write in confident prose, not superficial bullet points

        PILLAR CONTENT STRUCTURE (5000-6000 words total):

        1. THE REAL PROBLEM (400-500 words)
           - What is this topic actually trying to solve?
           - Why do most organizations get this wrong?
           - What does success actually look like (not vanity metrics)?

        2. FOUNDATIONAL CONCEPTS (800-1000 words)
           - Define key terms, but explain WHY the distinctions matter
           - Challenge any industry jargon that obscures rather than clarifies
           - Explain the mental models that experienced practitioners use

        3. HOW IT ACTUALLY WORKS (1000-1200 words)
           - Step-by-step explanation with technical depth
           - What happens when each step is done poorly?
           - The difference between "textbook" implementation and reality

        4. IMPLEMENTATION APPROACHES (1000-1200 words)
           - Different strategies and WHEN each applies
           - Decision framework for choosing (not just "it depends")
           - What the vendors won't tell you
           - Common failure modes and how to avoid them

        5. MEASURING WHAT MATTERS (600-800 words)
           - Which metrics actually drive improvement vs. vanity metrics
           - When common metrics (OEE, MTBF) are misleading
           - Leading indicators vs. lagging indicators
           - How to know if you're solving the right problem

        6. COMMON MISTAKES AND HARD TRUTHS (600-800 words)
           - What organizations consistently get wrong
           - Why "best practices" often fail
           - The gap between conference presentations and shop floor reality
           - Uncomfortable truths the industry doesn't discuss

        7. GETTING STARTED WITHOUT GETTING OVERWHELMED (500-600 words)
           - First steps that actually matter (not "buy software")
           - How to build a business case that resonates
           - What to do in your first 90 days
           - When to slow down vs. when to move fast

        AUDIENCE & CONTEXT:
        - Write for experienced maintenance managers and reliability engineers
        - These readers have heard the generic advice before - give them something new
        - Assume they're skeptical of vendor claims and "thought leadership"
        - The year is 2026

        LENGTH REQUIREMENTS:
        - MINIMUM 3500 words, target 4000-4500 for comprehensive coverage
        - NO superficial bullet points - use prose with substance
        - Every section must have DEPTH, not just breadth

        INTERNAL LINKING REQUIREMENTS (CRITICAL FOR PILLAR CONTENT):
        - EMBED 10-15 internal links to related articles using: [anchor text](/url/path)
        - Use ONLY URLs from the available internal URLs list above
        - Link to deeper articles when mentioning subtopics
        - Create a web of connections to cluster content

        EXTERNAL LINKING:
        - Include 3-5 external links to authoritative sources
        - Prefer: isixsigma.com, nist.gov, ieee.org, asme.org, reliabilityweb.com

        IMAGE PROMPT REQUIREMENTS:
        - Describe a hero image showing the breadth of this topic
        - Photo-realistic, professional, industrial setting
        - Diverse people in appropriate PPE
        - No text in the image

        Output in this EXACT structured markdown format:

        # Pillar Guide: {keyword}

        ## META_TITLE
        [Less than 60 characters - compelling, not generic]

        ## META_DESCRIPTION
        [150-160 characters, emphasizes insight over comprehensiveness]

        ## MAIN_TITLE
        [Engaging H1 that promises VALUE, not just coverage]

        ## BODY_CONTENT
        [MINIMUM 3500 words following the structure above. Write in confident prose, not bullet points. Question assumptions. Acknowledge trade-offs.]

        ## IMAGE_PROMPT
        [Detailed prompt for hero image]
        """

    def generate_content_with_gemini(self, keyword: str, research_data: ResearchData, is_pillar: bool = False) -> Optional[BlogPost]:
        """Generate high-quality blog content using Gemini

        Args:
            keyword: Target keyword for content
            research_data: Research data from keyword analysis
            is_pillar: If True, generates longer pillar/hub content (4500+ words)
        """

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

        # Build available internal URLs context - more URLs for pillar content
        internal_urls_context = ""
        if self.available_internal_urls:
            # Show more URLs for pillar content (needs more internal links)
            url_count = 50 if is_pillar else 20
            sample_urls = self.available_internal_urls[:url_count]
            internal_urls_context = f"""

        AVAILABLE INTERNAL URLS (for reference when adding internal links):
        {chr(10).join(sample_urls)}
        (And {len(self.available_internal_urls)} total available internal URLs)
        """

        # Use pillar prompt for hub/pillar content
        if is_pillar:
            content_prompt = self._get_pillar_prompt(keyword, research_summary, internal_urls_context)
        else:
            content_prompt = f"""
        Write a comprehensive blog post for the keyword: "{keyword}"

        Research insights:
        {research_summary}
        {internal_urls_context}

        CONTENT PHILOSOPHY - QUESTION-DRIVEN DEPTH:
        Think like a user interacting with an AI assistant. They start with an initial question, get an answer, then ask follow-up questions to go deeper. Structure this article the same way:

        1. IDENTIFY THE CORE QUESTION: What is the searcher really asking when they type "{keyword}"? What problem are they trying to solve? What decision are they trying to make?

        2. ANSWER IT DIRECTLY: Don't bury the answer. Give them the core insight upfront.

        3. ANTICIPATE FOLLOW-UP QUESTIONS: After reading the initial answer, what would they naturally ask next? Build sections around these follow-ups:
           - "How does this actually work in practice?"
           - "What are the common mistakes to avoid?"
           - "How do I get started?"
           - "What does this cost / what's the ROI?"
           - "What if my situation is different because of X?"
           - "How do I know if it's working?"
           - "What are the edge cases or exceptions?"

        4. GO DEEPER ON EACH FOLLOW-UP: Each follow-up answer should itself anticipate the next level of questions. This creates natural depth rather than superficial breadth.

        AUDIENCE & CONTEXT:
        - Write for maintenance managers, facility operators, and industrial decision-makers
        - These are busy professionals who need actionable information, not fluff
        - They've likely already read generic articles - give them insights they haven't seen
        - Avoid content similar to competitors: getmaintainx.com, limblecmms.com, upkeep.com
        - The year is 2026.

        WHAT MAKES CONTENT VALUABLE:
        - Specific numbers, thresholds, and benchmarks (not "regularly" but "every 500 hours")
        - Real scenarios that acknowledge complexity ("If your facility runs 24/7, here's how this changes...")
        - Decision frameworks ("Use this approach when X, but switch to Y when Z")
        - Honest trade-offs ("This method is faster but requires more upfront investment")
        - Troubleshooting actual problems ("If you're seeing X symptom, check Y first")

        STRUCTURE REQUIREMENTS:
        - MINIMUM 3000 words, target 3500-4000 for comprehensive coverage
        - Include at least 6-8 major H2 sections, each 400-600 words minimum
        - Use H2 sections (##) for major follow-up questions/topics
        - Use H3 subsections (###) for drilling into specifics
        - Each section should feel like a complete answer to a question someone would actually ask
        - Do NOT pad with fluff - each sentence should add value

        MARKDOWN LINK REQUIREMENTS:
        - EMBED 3-5 internal links naturally in context using: [anchor text](/url/path)
        - Use ONLY URLs from the available internal URLs list above
        - EMBED 2-3 external links to authoritative sources: [anchor text](https://example.com)
        - Prefer: isixsigma.com, nist.gov, ieee.org, asme.org, reliabilityweb.com, maintenanceworld.com

        IMAGE PROMPT REQUIREMENTS:
        - Describe a hero image relevant to manufacturing, maintenance, and the keyword
        - Photo-realistic, professional, no text/words in the image
        - Diverse people wearing appropriate PPE (hard hats, safety glasses, high-visibility clothing)
        - Show full body; any handheld devices show only the back, not the display

        Output in this EXACT structured markdown format:

        # Blog Post: {keyword}

        ## META_TITLE
        [Less than 60 characters, compelling and SEO-optimized]

        ## META_DESCRIPTION
        [150-160 characters, includes keyword and call-to-action]

        ## MAIN_TITLE
        [Engaging H1 that includes the target keyword - frame it as addressing the core question]

        ## BODY_CONTENT
        [MINIMUM 3000 words with 6-8 H2 sections of 400-600 words each. Start by directly answering the core question, then structure remaining sections as follow-up questions and answers. Include internal and external links naturally embedded in the markdown.]

        ## IMAGE_PROMPT
        [Detailed prompt for generating the hero image]
        """

        # Set max tokens based on content type
        max_tokens = 12000 if is_pillar else 10000

        try:
            # Add retry logic for rate limiting and timeouts
            max_retries = 3
            response = None
            for attempt in range(max_retries):
                try:
                    response = self.gemini_model.generate_content(  # type: ignore
                        content_prompt,
                        generation_config=genai.types.GenerationConfig(  # type: ignore
                            temperature=0.4,
                            max_output_tokens=max_tokens,
                        ),
                        request_options={"timeout": 240 if is_pillar else 180}
                    )
                    break  # Success, exit retry loop

                except Exception as e:
                    error_str = str(e).lower()
                    is_retryable = (
                        "429" in str(e) or
                        "quota" in error_str or
                        "504" in str(e) or
                        "deadline" in error_str or
                        "timeout" in error_str
                    )
                    if is_retryable:
                        wait_time = min(30 * (attempt + 1), 90)  # Max 90 seconds
                        logger.warning(
                            f"Retryable error ({e}), waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:  # Don't wait on last attempt
                            time.sleep(wait_time)
                            continue
                    raise e  # Re-raise if not retryable or last attempt

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

            # Pre-validation for pillar content (higher word count requirement)
            # Prompt asks for 3500+, but we accept 3000+ as passing
            word_count = len(cleaned_body.split())
            min_words = 3000 if is_pillar else 2000

            if is_pillar and word_count < min_words:
                logger.warning(f"Pillar content under minimum ({word_count}/{min_words} words)")

                # Try expansion for near-misses (2700-2999 words for pillar)
                if 2700 <= word_count < 3000:
                    logger.info(f"Attempting expansion for pillar content...")
                    self.expansion_stats["attempted"] += 1
                    expanded_body = self.expand_content(keyword, content_data, cleaned_body, target_words=3500)

                    if expanded_body:
                        expanded_word_count = len(expanded_body.split())
                        logger.info(f"Pillar expansion result: {word_count} -> {expanded_word_count} words")

                        if expanded_word_count >= 3000:
                            cleaned_body = expanded_body
                            word_count = expanded_word_count
                            self.expansion_stats["successful"] += 1
                        else:
                            logger.warning(f"Pillar expansion insufficient ({expanded_word_count}/3000), saving to drafts")
                            self._save_draft(keyword, content_data, expanded_body, expanded_word_count)
                            return None
                    else:
                        logger.warning(f"Pillar expansion failed, saving original to drafts")
                        self._save_draft(keyword, content_data, cleaned_body, word_count)
                        return None
                else:
                    # Too short for expansion
                    logger.warning(f"Pillar content too short for expansion ({word_count}/3000), saving to drafts")
                    self._save_draft(keyword, content_data, cleaned_body, word_count)
                    return None

            try:
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
            except ValidationError as e:
                # Check if it's a word count error
                error_str = str(e)
                if "Body must have at least 2000 words" in error_str:
                    word_count = len(cleaned_body.split())

                    # For near-misses (1700-1999 words), try to expand the content
                    if 1700 <= word_count < 2000:
                        logger.warning(f"Near-miss word count ({word_count}/2000), attempting expansion...")
                        self.expansion_stats["attempted"] += 1
                        expanded_body = self.expand_content(keyword, content_data, cleaned_body, target_words=2200)

                        if expanded_body:
                            expanded_word_count = len(expanded_body.split())
                            logger.info(f"Expansion result: {word_count} -> {expanded_word_count} words")

                            if expanded_word_count >= 2000:
                                # Try again with expanded content
                                try:
                                    self.expansion_stats["successful"] += 1
                                    return BlogPost(
                                        keyword=keyword,
                                        meta_title=content_data.meta_title,
                                        meta_description=content_data.meta_description,
                                        title=content_data.title,
                                        body=expanded_body,
                                        image_prompt=content_data.image_prompt,
                                        internal_links=[],
                                        external_links=[]
                                    )
                                except ValidationError as e2:
                                    self.expansion_stats["successful"] -= 1  # Undo the increment
                                    logger.warning(f"Expansion still failed validation: {e2}")
                                    # Save expanded version to drafts
                                    self._save_draft(keyword, content_data, expanded_body, expanded_word_count)
                            else:
                                # Expansion didn't reach target, save expanded version to drafts
                                logger.warning(f"Expansion insufficient ({expanded_word_count}/2000), saving to drafts")
                                self._save_draft(keyword, content_data, expanded_body, expanded_word_count)
                        else:
                            # Expansion failed, save original to drafts
                            logger.warning(f"Expansion failed, saving original ({word_count} words) to drafts")
                            self._save_draft(keyword, content_data, cleaned_body, word_count)
                    else:
                        # Too short for expansion (< 1700), save to drafts directly
                        logger.warning(f"Content too short for expansion ({word_count}/2000), saving to drafts")
                        self._save_draft(keyword, content_data, cleaned_body, word_count)

                logger.error(f"Error generating content: {e}")
                return None

        except Exception as e:
            logger.error(f"Error generating content: {e}")
            return None

    def expand_content(self, keyword: str, content_data: ContentData, current_body: str, target_words: int = 2200) -> Optional[str]:
        """Expand under-length content by asking LLM to add more depth to existing sections"""
        current_words = len(current_body.split())
        words_needed = target_words - current_words

        logger.info(f"Expanding content: {current_words} words -> target {target_words} (need +{words_needed} words)")

        expand_prompt = f"""
        The following blog post about "{keyword}" is {current_words} words but needs to be at least {target_words} words.

        EXPAND the content by adding {words_needed}+ more words. Do NOT rewrite - ADD to existing sections.

        EXPANSION STRATEGIES (pick 2-3):
        1. Add a real-world example or case study to an existing section
        2. Add a "Common Mistakes" or "Troubleshooting" section if missing
        3. Expand the "How to get started" or implementation guidance
        4. Add specific numbers, thresholds, or benchmarks where generic advice exists
        5. Add a comparison table or decision framework
        6. Expand on edge cases or "what if" scenarios

        RULES:
        - Keep the existing structure and content intact
        - Add depth, not fluff - every sentence should add value
        - Maintain the same professional tone for industrial/maintenance audience
        - Keep all existing markdown links intact
        - Output the COMPLETE expanded article (not just the additions)

        CURRENT CONTENT:
        {current_body}

        OUTPUT: The complete expanded article in markdown format (just the body content, no meta fields).
        """

        try:
            logger.info("Calling Gemini API for content expansion...")
            response = self.gemini_model.generate_content(  # type: ignore
                expand_prompt,
                generation_config=genai.types.GenerationConfig(  # type: ignore
                    temperature=0.3,  # Lower temperature for more consistent expansion
                    max_output_tokens=15000,
                ),
                request_options={"timeout": 180}
            )

            if response is None:
                logger.error("No response from expansion API call")
                return None

            expanded_body = response.text.strip()
            new_word_count = len(expanded_body.split())

            logger.info(f"Expansion complete: {current_words} -> {new_word_count} words (+{new_word_count - current_words})")

            # Validate and clean links in the expanded content
            cleaned_expanded = self.validate_and_clean_markdown_links(expanded_body)

            return cleaned_expanded

        except Exception as e:
            logger.error(f"Error expanding content: {e}")
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

    def generate_image_with_gemini(self, image_prompt: str, keyword: str = "", output_dir: str = "generated_content") -> Tuple[Optional[str], Optional[str]]:
        """Generate hero image using Gemini 3 Pro Image Preview and save it locally"""
        logger.info(f"Generating image with prompt: {image_prompt}")
        logger.debug(f"Prompt length: {len(image_prompt)} characters")

        # Add retry logic for timeouts and transient errors
        max_retries = 3
        response = None

        for attempt in range(max_retries):
            try:
                logger.info(f"Calling Gemini Image Generation API (attempt {attempt + 1}/{max_retries})...")
                response = self.gemini_image_client.models.generate_content(  # type: ignore
                    model="gemini-3-pro-image-preview",
                    contents=image_prompt,
                    config=genai_new.types.GenerateContentConfig(  # type: ignore
                        response_modalities=['IMAGE'],
                        automatic_function_calling=genai_new.types.AutomaticFunctionCallingConfig(  # type: ignore
                            disable=True
                        ),
                    ),
                )
                break  # Success, exit retry loop

            except Exception as e:
                error_str = str(e).lower()
                is_retryable = (
                    "429" in str(e) or
                    "quota" in error_str or
                    "504" in str(e) or
                    "deadline" in error_str or
                    "timeout" in error_str or
                    "afc" in error_str
                )
                if is_retryable and attempt < max_retries - 1:
                    wait_time = min(30 * (attempt + 1), 60)  # Max 60 seconds
                    logger.warning(
                        f"Retryable error ({e}), waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Error generating image with Gemini: {e}")
                    logger.warning(f"No fallback model - returning None")
                    return None, None

        if response is None:
            logger.error(f"Failed to get image response after {max_retries} attempts")
            return None, None

        try:
            logger.info(f"Image generated successfully!")
            # Check for image data in the response parts
            if response.candidates and len(response.candidates) > 0:
                content = response.candidates[0].content
                if content is not None and content.parts is not None:
                    for part in content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data is not None:
                            inline_data = part.inline_data
                            if inline_data.data is not None and keyword:
                                # Create the output directory if it doesn't exist
                                os.makedirs(output_dir, exist_ok=True)

                                # Create local filename
                                safe_keyword = keyword.replace(' ', '-').replace('/', '-')
                                local_filename = f"{safe_keyword}.png"
                                local_path = os.path.join(output_dir, local_filename)

                                # Save the image data (already bytes from SDK)
                                image_bytes = inline_data.data if isinstance(inline_data.data, bytes) else base64.b64decode(inline_data.data)
                                with open(local_path, 'wb') as f:
                                    f.write(image_bytes)
                                logger.info(f"Image saved to: {local_path}")

                                return None, local_path
                            elif not keyword:
                                return None, None

            logger.error(f"No image data received from Gemini")
            return None, None

        except Exception as e:
            logger.error(
                f"Error processing image response: {e}")
            return None, None

    def format_for_prismic(self, blog_post: BlogPost) -> PrismicData:
        """Format content for Prismic CMS with the markdown body for the new slice"""

        hero_image: Dict[str, Any] = {
            "url": blog_post.image_url or "",
            "local_path": blog_post.local_image_path or "",
            "alt": f"Hero image for {blog_post.title}",
            "source": "gemini-3-pro-image-preview" if blog_post.local_image_path and not blog_post.image_url else "url"
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

    def check_draft_exists(self, keyword: str, output_dir: str = "generated_content/drafts") -> bool:
        """Check if a draft exists for this keyword"""
        safe_keyword = re.sub(r'[^\w\s-]', '', keyword).strip()
        safe_keyword = re.sub(r'[-\s]+', '-', safe_keyword)

        md_filepath = os.path.join(output_dir, f"{safe_keyword[:50]}.md")
        return os.path.exists(md_filepath)

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

    def _save_draft(self, keyword: str, content_data: ContentData, body: str, word_count: int, output_dir: str = "generated_content/drafts") -> Tuple[str, str]:
        """Save under-length content to drafts folder for review"""
        os.makedirs(output_dir, exist_ok=True)

        # Create safe filename
        safe_keyword = re.sub(r'[^\w\s-]', '', keyword).strip()
        safe_keyword = re.sub(r'[-\s]+', '-', safe_keyword)

        # Save JSON
        json_data = {
            "keyword": keyword,
            "meta_title": content_data.meta_title,
            "meta_description": content_data.meta_description,
            "title": content_data.title,
            "image_prompt": content_data.image_prompt,
            "word_count": word_count,
            "shortfall": 2000 - word_count,
            "status": "draft_under_length"
        }

        json_filepath = os.path.join(output_dir, f"{safe_keyword[:50]}.json")
        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        # Save Markdown
        md_filepath = os.path.join(output_dir, f"{safe_keyword[:50]}.md")
        with open(md_filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {content_data.title}\n\n")
            f.write(f"**Status:** DRAFT - Under minimum word count\n")
            f.write(f"**Word Count:** {word_count}/2000 ({2000 - word_count} words short)\n\n")
            f.write(f"**Keyword:** {keyword}\n")
            f.write(f"**Meta Title:** {content_data.meta_title}\n")
            f.write(f"**Meta Description:** {content_data.meta_description}\n\n")
            f.write("---\n\n")
            f.write(body)

        logger.info(f"Draft saved to: {output_dir}/")
        logger.info(f"  JSON: {json_filepath}")
        logger.info(f"  Markdown: {md_filepath}")

        return json_filepath, md_filepath

    def upload_to_prismic(self, json_filepath: str, skip_upload: bool = False, profile: str = "tim") -> Dict[str, Any]:
        """Upload generated content to Prismic CMS using Node.js script"""
        try:
            logger.info(f"Uploading to Prismic...")

            # Prepare command
            cmd = ["node", "prismic_uploader.js", json_filepath]
            if skip_upload:
                cmd.append("--skip-upload")
            if profile:
                cmd.extend(["--profile", profile])

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

    # Get profile selection
    print("\n👤 Available author profiles:")
    print("  1. Tim Cheung - CTO and Co-Founder of Factory AI")
    print("  2. JP - CEO and Co-founder of Factory AI")
    print("  3. Luka - Founding AI Engineer of Factory AI")

    profile_choice: str = input(
        "Select author profile (1/2/3) [1]: ").strip()
    if not profile_choice:
        profile_choice = "1"

    # Map choice to profile names
    profile_map = {
        "1": "tim",
        "2": "jp",
        "3": "luka"
    }

    selected_profile = profile_map.get(profile_choice, "tim")
    profile_names = {
        "tim": "Tim Cheung, CTO and Co-Founder of Factory AI",
        "jp": "JP, CEO and Co-founder of Factory AI",
        "luka": "Luka, Founding AI Engineer of Factory AI"
    }

    print(f"✅ Selected profile: {profile_names[selected_profile]}")

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

    # Get pillar content mode
    pillar_choice: str = input(
        "Generate PILLAR content (longer, hub pages)? (y/n) [n]: ").strip().lower()
    is_pillar_mode: bool = pillar_choice in ['y', 'yes']

    if is_pillar_mode:
        print("📚 Pillar mode: Will generate comprehensive hub content (4500+ words)")
        print("   └─ Best for: topic overviews, ultimate guides, cluster hubs")
    else:
        print("📝 Standard mode: Will generate focused blog content (3000+ words)")

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
        "drafts_saved": 0,
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

            # Check if research failed before attempting content generation
            if research_data.error:
                print(f"  ❌ Research failed for: {keyword}")
                print(f"     Error: {research_data.error}")
                logger.error(f"Research failed for {keyword}: {research_data.error}")
                generation_stats["failed"] += 1
                continue

            # Generate content
            content_type = "pillar content" if is_pillar_mode else "content"
            print(f"  ✍️  Generating {content_type}...")
            logger.info(f"Generating {content_type}...")
            blog_post = generator.generate_content_with_gemini(
                keyword, research_data, is_pillar=is_pillar_mode)

            if not blog_post:
                # Check if a draft was saved (under-length content)
                if generator.check_draft_exists(keyword):
                    print(f"  📝 Content saved as draft (under word count): {keyword}")
                    logger.info(f"Draft saved for under-length content: {keyword}")
                    generation_stats["drafts_saved"] += 1
                else:
                    print(f"  ❌ Failed to generate content for: {keyword}")
                    logger.error(f"Failed to generate content for: {keyword}")
                generation_stats["failed"] += 1
                continue

            # Generate image
            print("  🎨 Generating hero image...")
            logger.info("Generating hero image...")
            image_url, local_image_path = generator.generate_image_with_gemini(
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
                    json_path, skip_prismic_upload, selected_profile)

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
    if generation_stats['drafts_saved'] > 0:
        print(f"   • Drafts saved (under word count): {generation_stats['drafts_saved']}")
        print(f"     └─ Review in: generated_content/drafts/")

    # Show expansion stats if any were attempted
    if generator.expansion_stats["attempted"] > 0:
        print(f"   • Content expansions attempted: {generator.expansion_stats['attempted']}")
        print(f"     └─ Successful: {generator.expansion_stats['successful']}")

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
