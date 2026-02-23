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
from difflib import SequenceMatcher
from urllib.parse import urlparse
import os
from dotenv import load_dotenv
from google import genai  # type: ignore
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


def is_definition_type_keyword(keyword: str) -> bool:
    """Return True if the keyword is definition/glossary intent (what is X, X definition, meaning, define)."""
    if not keyword or not keyword.strip():
        return False
    k = keyword.strip().lower()
    if re.search(r'\b(what\s+is|what\s+are|what\s+does|what\s+do)\b', k):
        return True
    if re.search(r'\bdefinition\b|\bdefine\b|\bmeaning\b|\bdefined\b', k):
        return True
    if re.search(r'\b(def|meaning\s+of)\b', k):
        return True
    return False


class ContentFormat:
    """Content format types for SEO generation."""
    BLOG = "blog"
    PILLAR = "pillar"
    AI_VISIBILITY = "ai_visibility"
    GLOSSARY = "glossary"
    COMPARATIVE = "comparative"
    STRUCTURED_KNOWLEDGE = "structured_knowledge"
    INDUSTRY_DATA = "industry_data"

    LABELS = {
        "blog": "Blog post (3000+ words)",
        "pillar": "Pillar guide (4500+ words)",
        "ai_visibility": "AI visibility content (3500+ words)",
        "glossary": "Glossary/definition page (400-800 words)",
        "comparative": "Comparative listicle (1500-2500 words)",
        "structured_knowledge": "Structured Q&A (800-1500 words)",
        "industry_data": "Industry data page (1500-2500 words)",
    }


# Vendor/product names relevant to the predictive maintenance / CMMS space
_VENDOR_NAMES = {
    "augury", "skf", "senseye", "siemens", "fiix", "maintainx", "upkeep",
    "limble", "nanolike", "nanoprecise", "ibm", "honeywell", "emerson",
    "fluke", "rockwell", "schneider", "abb", "ge", "aveva", "infor",
    "maximo", "sap", "oracle", "tractian", "icare", "movus"
}


def classify_keyword(keyword: str) -> str:
    """Auto-classify a keyword into the best content format.

    Priority order (highest specificity first):
      1. Definition — "what is X", "X definition", "meaning"
      2. Comparative — vendor comparisons, "best/top X", "X vs Y", "alternatives to"
      3. Structured knowledge — "why X", "how to X", "can X", yes/no questions, cost/time queries
      4. Industry data — industry-specific + data/cost/benchmark queries
      5. Blog — catch-all for remaining keywords
    """
    if not keyword or not keyword.strip():
        return ContentFormat.BLOG
    k = keyword.strip().lower()

    # --- 1. Definition ---
    if is_definition_type_keyword(keyword):
        return ContentFormat.GLOSSARY

    # --- 2. Comparative ---
    # Explicit comparison patterns
    if re.search(r'\bvs\b|\bversus\b', k):
        return ContentFormat.COMPARATIVE
    if re.search(r'\balternatives?\s+to\b', k):
        return ContentFormat.COMPARATIVE
    if re.search(r'\bcompetitors?\b|\bwho\s+competes\s+with\b', k):
        return ContentFormat.COMPARATIVE
    if re.search(r'\bcomparison\b|\bcompare\b', k):
        return ContentFormat.COMPARATIVE
    # "best/top X" where X is a product category or industry-specific abbreviation
    _PRODUCT_NOUNS = (
        r'software|platform|system|tool|company|companies|startup|startups|'
        r'provider|providers|vendor|vendors|solution|solutions|app|apps|'
        r'cmms|apm|pdm|eam|erp|iot'
    )
    if re.search(r'\b(best|top)\b.*\b(' + _PRODUCT_NOUNS + r')\b', k):
        return ContentFormat.COMPARATIVE
    # Category + "companies/startups/leaders/providers/vendors" (e.g. "predictive maintenance companies")
    if re.search(r'\b(companies|startups|leaders|providers|vendors)\s*$', k):
        return ContentFormat.COMPARATIVE
    # Vendor lists: "X vendors list", "X vendors food industry"
    if re.search(r'\bvendors?\s+(list|for|food|packaging|manufacturing)\b', k):
        return ContentFormat.COMPARATIVE
    if re.search(r'\b(leaders?)\b.*\b(maintenance|industrial|manufacturing)\b', k):
        return ContentFormat.COMPARATIVE
    # Contains two or more known vendor names → comparison piece
    vendor_hits = sum(1 for v in _VENDOR_NAMES if re.search(r'\b' + re.escape(v) + r'\b', k))
    if vendor_hits >= 2:
        return ContentFormat.COMPARATIVE
    # Single vendor + "competitors" or "alternatives" already caught above
    # "services vs software" patterns
    if re.search(r'\bservices?\s+vs\b|\bvs\s+services?\b', k):
        return ContentFormat.COMPARATIVE
    if re.search(r'\bvs\b', k):
        return ContentFormat.COMPARATIVE
    # Product-category search queries — keywords that are essentially "[topic] software/platforms/systems for [industry]"
    # These are comparison-intent: people searching for a list of options to evaluate
    if re.search(r'\b(software|platforms?|systems?|tools?|solutions?)\b.*\b(manufacturing|factories|industrial|food|packaging)\b', k):
        return ContentFormat.COMPARATIVE
    if re.search(r'\b(manufacturing|factories|industrial|food|packaging)\b.*\b(software|platforms?|systems?|tools?|solutions?)\b', k):
        return ContentFormat.COMPARATIVE
    # Standalone product-category searches ending with a product noun (not question-led)
    # e.g. "smart factory maintenance software", "digital maintenance platforms", "machine downtime analytics software"
    if not re.search(r'^(how|why|can|is|what|when|where)\b', k):
        if re.search(r'\b(software|platforms?|systems?|tools?)\s*$', k):
            return ContentFormat.COMPARATIVE

    # --- 3. Structured knowledge ---
    # "why X" questions — symptom/root-cause Q&A
    if re.search(r'^why\b', k):
        return ContentFormat.STRUCTURED_KNOWLEDGE
    # "can X" capability questions
    if re.search(r'^can\b', k):
        return ContentFormat.STRUCTURED_KNOWLEDGE
    # "is X worth it", "is X good for"
    if re.search(r'^is\b', k):
        return ContentFormat.STRUCTURED_KNOWLEDGE
    # Cost / time / quantity queries
    if re.search(r'\bhow\s+much\b|\bhow\s+long\b|\bhow\s+many\b', k):
        return ContentFormat.STRUCTURED_KNOWLEDGE
    # "how to X" — shorter how-to questions (not broad enough for a full blog)
    if re.search(r'^how\s+to\b', k):
        # Broad how-to topics get blog treatment; narrow ones get structured knowledge
        broad_markers = (
            r'\bprogram\b|\bstrategy\b|\binitiative\b|\btransform\b|\bbuild\b.*\bprogram\b'
        )
        if re.search(broad_markers, k):
            return ContentFormat.BLOG
        return ContentFormat.STRUCTURED_KNOWLEDGE

    # --- 4. Industry data ---
    industry_markers = r'\b(food|beverage|packaging|pharma|automotive|mining|washdown|conveyor|bakery|dairy|meat)\b'
    data_markers = r'\b(cost|pricing|roi|calculator|benchmark|statistic|data|survey|report|trend)\b'
    if re.search(industry_markers, k) and re.search(data_markers, k):
        return ContentFormat.INDUSTRY_DATA

    # --- 5. Catch-all: standard blog ---
    return ContentFormat.BLOG


# Model roles: research benefits from depth (Gemini 3 Pro, 250 RPD); content generation
# can use higher-limit models (e.g. Gemini 2.5 Flash 10K RPD, Gemini 2 Flash unlimited).
# Override via env: GEMINI_RESEARCH_MODEL, GEMINI_CONTENT_MODEL.
#
# Deep Research Pro Preview: This is an *agent* (Interactions API), not generateContent.
# It has a 0/1 concurrency limit in the dashboard, so it's not suitable for bulk keyword
# research. Use it for single deep-dive research via Google's Interactions API if needed.
# See: https://ai.google.dev/gemini-api/docs (Deep Research / Agents).
GEMINI_RESEARCH_MODEL_DEFAULT = "gemini-3-pro-preview"
# Gemini 3 Flash is stronger than 2.5 Flash; use 2.5 if your 3 Flash RPD limit is tight.
GEMINI_CONTENT_MODEL_DEFAULT = "gemini-3-flash-preview"

# Deep Research agent (Interactions API). Enable with USE_DEEP_RESEARCH=1 (1 RPM is fine for ~1 article/min).
DEEP_RESEARCH_AGENT = "deep-research-pro-preview-12-2025"

# Fast research model for glossary/definition keywords (no need for 6-min Deep Research). Same as content model.
GEMINI_RESEARCH_MODEL_FAST_DEFAULT = "gemini-3-flash-preview"


class SEOContentGenerator:
    """Main class for generating SEO-optimized content with proper typing"""

    def __init__(self) -> None:
        # Unified google-genai Client for all Gemini operations
        self.client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))  # type: ignore

        # Model name strings (no more stateful GenerativeModel objects)
        self.research_model_name: str = os.getenv("GEMINI_RESEARCH_MODEL", GEMINI_RESEARCH_MODEL_DEFAULT)
        self.research_model_fast_name: str = os.getenv("GEMINI_RESEARCH_MODEL_FAST", GEMINI_RESEARCH_MODEL_FAST_DEFAULT)
        self.content_model_name: str = os.getenv("GEMINI_CONTENT_MODEL", GEMINI_CONTENT_MODEL_DEFAULT)
        logger.info(f"Gemini models: research={self.research_model_name}, research_fast={self.research_model_fast_name}, content={self.content_model_name}")

        self._use_deep_research = os.getenv("USE_DEEP_RESEARCH", "").strip().lower() in ("1", "true", "yes")
        if self._use_deep_research:
            logger.info("Deep Research Pro Preview enabled for research (Interactions API)")

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

    def _parse_semrush_references(self, ref_text: str) -> List[Dict[str, str]]:
        """Parse SEMrush Content references or Competitors field into SERP-like entries.
        Format: "domain":"url" per line."""
        entries: List[Dict[str, str]] = []
        if not ref_text or not ref_text.strip():
            return entries
        # Match "domain":"url" pattern (SEMrush format)
        pattern = re.compile(r'"([^"]+)"\s*:\s*"(https?://[^"]+)"')
        for line in ref_text.split('\n'):
            line = line.strip()
            if not line:
                continue
            match = pattern.search(line)
            if match:
                domain, url = match.group(1).strip(), match.group(2).strip()
                if domain and url:
                    entries.append({
                        'title': domain,
                        'url': url,
                        'position': str(len(entries) + 1) if entries else '1',
                        'traffic': '',
                        'difficulty': '',
                        'volume': '',
                        'cpc': '',
                        'type': '',
                        'intents': ''
                    })
        return entries[:10]  # Limit to top 10 for SERP context

    def _detect_csv_format(self, fieldnames: Optional[List[str]]) -> str:
        """Detect if CSV is from Ahrefs or SEMrush based on column names."""
        if not fieldnames:
            return 'ahrefs'
        names_lower = [f.lower() for f in fieldnames]
        # SEMrush has "Keyword Difficulty", "Database", "Seed keyword" - Ahrefs doesn't
        if any('keyword difficulty' in n for n in names_lower) or 'database' in names_lower:
            return 'semrush'
        return 'ahrefs'

    def load_keywords_from_csv(self, csv_file_path: str) -> Dict[str, List[Dict[str, Any]]]:
        """Load keywords from Ahrefs or SEMrush CSV export with SERP data"""
        keyword_data: Dict[str, List[Dict[str, Any]]] = {}

        # Try different encodings commonly used by Ahrefs/SEMrush
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
                            csv_format = self._detect_csv_format(fieldnames)
                            logger.info(f"Detected CSV format: {csv_format}")

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

                                    if csv_format == 'semrush':
                                        # SEMrush column mappings (metadata + SERP Features)
                                        serp_entry = {
                                            'title': 'Keyword metrics',
                                            'url': '',
                                            'position': '',
                                            'traffic': '',
                                            'difficulty': row.get('Keyword Difficulty', ''),
                                            'volume': row.get('Volume', ''),
                                            'cpc': row.get('CPC (USD)', '') or row.get('CPC', ''),
                                            'type': row.get('Page type', ''),
                                            'intents': row.get('Intent', '') or row.get('Intents', ''),
                                            'serp_features': row.get('SERP Features', '') or row.get('SERP features', '')
                                        }
                                        # Parse Content references and Competitors for SERP-like data
                                        content_refs = row.get('Content references', '') or row.get('Content References', '')
                                        competitors = row.get('Competitors', '')
                                        ref_entries = self._parse_semrush_references(content_refs)
                                        if not ref_entries:
                                            ref_entries = self._parse_semrush_references(competitors)
                                        # Put metadata first so it's included in serp_data[:10], then refs
                                        keyword_data[keyword] = [serp_entry] + ref_entries
                                    else:
                                        # Ahrefs column mappings
                                        serp_entry = {
                                            'title': row.get('Title', ''),
                                            'url': row.get('URL', ''),
                                            'position': row.get('Position', ''),
                                            'traffic': row.get('Traffic', ''),
                                            'difficulty': row.get('Difficulty', ''),
                                            'volume': row.get('Volume', ''),
                                            'cpc': row.get('CPC', ''),
                                            'type': row.get('Type', ''),
                                            'intents': row.get('Intents', ''),
                                            'serp_features': ''
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
            # Larger sitemap generation can exceed the old 15s read timeout.
            response = requests.get(sitemap_url, timeout=60)
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

    def _title_to_slug(self, title: str) -> str:
        """Replicate Prismic slug creation from title (matches prismic_uploader.js createSlug)."""
        slug = title.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'\s+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        slug = slug.strip('-')
        return slug

    def register_generated_url(self, title: str) -> str:
        """Predict the blog URL from the post title and add it to available_internal_urls.

        Call after each successful content generation so subsequent articles
        can link to previously generated (but not yet live) content.
        """
        slug = self._title_to_slug(title)
        predicted_path = f"/blog/{slug}"
        if predicted_path not in self.available_internal_urls:
            self.available_internal_urls.append(predicted_path)
            logger.info(f"Registered predicted internal URL: {predicted_path}")
        return predicted_path

    def deduplicate_keywords(self, keywords: List[str]) -> Tuple[List[str], List[Tuple[str, List[str]]]]:
        """Detect and remove near-duplicate keywords from the list.

        Uses word-set overlap and character-level similarity to catch:
        - Exact duplicates after normalization
        - Word-reordering variants (same words, different order)
        - High bidirectional word overlap (>= 80%)
        - High character similarity (>= 85%, catches stem variants like plan/planning)

        Returns (deduplicated_list, merged_groups) where each merged_group is
        (kept_keyword, [dropped_keywords]).
        """
        if not keywords:
            return keywords, []

        def normalize(kw: str) -> str:
            return re.sub(r'\s+', ' ', kw.strip().lower())

        def word_set(kw: str) -> set:
            return set(normalize(kw).split())

        used: set = set()
        groups: List[List[str]] = []

        for i, kw in enumerate(keywords):
            if i in used:
                continue
            group = [kw]
            kw_norm = normalize(kw)
            kw_words = word_set(kw)

            for j in range(i + 1, len(keywords)):
                if j in used:
                    continue
                other = keywords[j]
                other_norm = normalize(other)
                other_words = word_set(other)

                # Exact match after normalization
                if kw_norm == other_norm:
                    group.append(other)
                    used.add(j)
                    continue

                # Same words, different order
                if kw_words == other_words:
                    group.append(other)
                    used.add(j)
                    continue

                if not kw_words or not other_words:
                    continue

                # Bidirectional word overlap (both directions must be >= 80%)
                overlap = len(kw_words & other_words)
                if overlap / len(kw_words) >= 0.8 and overlap / len(other_words) >= 0.8:
                    group.append(other)
                    used.add(j)
                    continue

                # Character-level similarity catches stem variants (plan vs planning)
                if SequenceMatcher(None, kw_norm, other_norm).ratio() >= 0.85:
                    group.append(other)
                    used.add(j)
                    continue

            groups.append(group)

        deduplicated: List[str] = []
        merged_groups: List[Tuple[str, List[str]]] = []
        for group in groups:
            deduplicated.append(group[0])
            if len(group) > 1:
                merged_groups.append((group[0], group[1:]))

        return deduplicated, merged_groups

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

    def research_keyword_with_gemini(self, keyword: str, serp_data: Optional[List[Dict[str, Any]]] = None, use_fast_research: bool = False) -> ResearchData:
        """Use Gemini to analyze keyword and competition.

        When use_fast_research is True (e.g. for glossary/definition keywords), skips Deep Research
        and uses the fast research model (gemini-3.0-fast) instead of the deep-research agent.
        """

        logger.info(f"Starting {'fast ' if use_fast_research else ''}research for keyword: '{keyword}'")
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
           Volume: {result.get('volume', 'N/A')}
           Difficulty: {result.get('difficulty', 'N/A')}
           CPC: {result.get('cpc', 'N/A')}
           Type: {result.get('type', 'N/A')}
           Intents: {result.get('intents', 'N/A')}
           SERP Features: {result.get('serp_features', 'N/A')}
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

        # Glossary/definition keywords use fast model only; skip Deep Research (no 6-min agent).
        if self._use_deep_research and not use_fast_research:
            return self._research_keyword_deep_research(keyword, research_prompt)

        research_model_name = self.research_model_fast_name if use_fast_research else self.research_model_name
        try:
            logger.info(f"Calling Gemini API ({'fast' if use_fast_research else 'standard'} research)...")
            api_start = time.time()

            # Add retry logic for rate limiting and timeouts
            max_retries = 3
            response = None
            for attempt in range(max_retries):
                try:
                    response = self.client.models.generate_content(  # type: ignore
                        model=research_model_name,
                        contents=research_prompt,
                        config=genai.types.GenerateContentConfig(  # type: ignore
                            temperature=0.3,
                            max_output_tokens=4000,
                            http_options=genai.types.HttpOptions(timeout=120_000),  # type: ignore
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

    def _research_keyword_deep_research(self, keyword: str, research_prompt: str) -> ResearchData:
        """Use Deep Research Pro Preview agent (Interactions API). 1 RPM is fine for ~1 article/min."""
        start_time: float = time.time()
        logger.info(f"Starting Deep Research agent for keyword: '{keyword}'")
        text_parts: List[str] = []
        interaction_id: Optional[str] = None
        last_event_id: Optional[str] = None
        is_complete = False
        max_wait_seconds = 900  # 15 min total wait
        poll_interval = 8
        timeout_per_request = 600  # 10 min per request/stream

        def process_stream(event_stream: Any) -> None:
            nonlocal interaction_id, last_event_id, is_complete
            for event in event_stream:
                if getattr(event, "event_type", None) == "interaction.start" and getattr(event, "interaction", None):
                    interaction_id = getattr(event.interaction, "id", None)
                    if interaction_id:
                        logger.info(f"Deep Research interaction started: {interaction_id}")
                if getattr(event, "event_id", None):
                    last_event_id = event.event_id
                if getattr(event, "event_type", None) == "content.delta" and getattr(event, "delta", None):
                    delta = event.delta
                    if getattr(delta, "type", None) == "text" and getattr(delta, "text", None):
                        text_parts.append(delta.text)
                if getattr(event, "event_type", None) in ("interaction.complete", "error"):
                    is_complete = True

        try:
            initial_stream = self.client.interactions.create(  # type: ignore
                input=research_prompt,
                agent=DEEP_RESEARCH_AGENT,
                background=True,
                stream=True,
                timeout=timeout_per_request,
                agent_config={"type": "deep-research", "thinking_summaries": "auto"},
            )
            process_stream(initial_stream)
        except Exception as e:
            logger.warning(f"Deep Research stream initial/connection: {e}")

        deadline = time.time() + max_wait_seconds
        while not is_complete and interaction_id and time.time() < deadline:
            if last_event_id:
                logger.info(f"Resuming Deep Research from event {last_event_id}...")
            time.sleep(poll_interval)
            try:
                resume_stream = self.client.interactions.get(  # type: ignore
                    id=interaction_id,
                    stream=True,
                    timeout=timeout_per_request,
                    last_event_id=last_event_id,
                )
                process_stream(resume_stream)
            except Exception as e:
                logger.warning(f"Deep Research resume: {e}")

        response_text = "".join(text_parts).strip() if text_parts else ""
        elapsed = time.time() - start_time
        logger.info(f"Deep Research finished in {elapsed:.1f}s, {len(response_text)} chars")
        if not response_text:
            return ResearchData(keyword=keyword, error="Deep Research returned no text (timeout or stream error)")
        research_dict = self._parse_research_markdown(response_text, keyword)
        if research_dict and not research_dict.get("error"):
            return ResearchData(**research_dict)
        return ResearchData(keyword=keyword, error=research_dict.get("error", "Failed to parse Deep Research output"))

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
        - MINIMUM 2500 words, target 3000-3500 for comprehensive coverage
        - Focus on STRUCTURE over length - each section should be complete, not padded
        - NO superficial bullet points - use prose with substance

        PILLAR STRUCTURE (focus on organization, links will be added in a second pass):

        This content should be structured as a comprehensive overview that COULD link to deeper content.
        When you mention specific techniques, equipment types, or concepts, note them clearly so they
        can be linked later. Focus on:
        1. Clear section headers that serve as a table of contents
        2. Mentioning related subtopics by name (even if not linked yet)
        3. Writing sections that stand alone but invite deeper exploration

        EXTERNAL LINKING (only external for now - internal links added separately):
        - Include 2-3 external links to authoritative sources
        - Prefer: isixsigma.com, nist.gov, ieee.org, asme.org, reliabilityweb.com

        IMAGE PROMPT REQUIREMENTS:
        - Describe a hero image showing the breadth of this topic
        - Photo-realistic, professional, industrial setting
        - Diverse people in appropriate PPE
        - No text in the image

        META_TITLE & META_DESCRIPTION (preview text) - CRITICAL VARIETY RULES:
        - Do NOT start the meta description with overused phrases. Our corpus repeats these—avoid them entirely:
          FORBIDDEN openings: "Move beyond...", "Beyond the dictionary...", "Discover how...", "What is the true [X] meaning...", "Learn how..."
        - Vary the opening every time. Use ONE of these (or similar) and rotate:
          • A direct question: "What is [topic] in practice?" or "Why does [topic] matter in 2026?"
          • A concrete claim: "In 2026, [topic] separates reactive plants from predictive ones."
          • A problem hook: "Most teams get [topic] wrong. Here's the framework that works."
          • A number or outcome: "70% of unplanned downtime traces to [topic]. Here's how to fix it."
          • A definition that leads to value: "[Topic] isn't just X—it's the layer that connects Y to Z."
        - Meta title: avoid generic "The 2026 Guide to..." unless the angle is clearly different. Prefer question or benefit-led titles.

        Output in this EXACT structured markdown format:

        # Pillar Guide: {keyword}

        ## META_TITLE
        [Less than 60 characters - compelling, not generic; avoid "The 2026 Guide" unless angle is distinct]

        ## META_DESCRIPTION
        [150-160 characters. Do NOT start with "Move beyond", "Beyond the dictionary", "Discover how", or "What is the true X meaning". Use a varied opening from the list above.]

        ## MAIN_TITLE
        [Engaging H1 that promises VALUE, not just coverage]

        ## BODY_CONTENT
        [MINIMUM 2500 words following the structure above. Write in confident prose, not bullet points. Question assumptions. Acknowledge trade-offs.]

        ## IMAGE_PROMPT
        [Detailed prompt for hero image]
        """

    def _get_ai_visibility_prompt(self, keyword: str, research_summary: str, internal_urls_context: str) -> str:
        """Generate the prompt for AI visibility content - optimized for ChatGPT/Gemini citation"""
        return f"""
        Write a comprehensive, authoritative blog post for the keyword: "{keyword}"

        This content is specifically designed to be CITED by AI assistants like ChatGPT and Gemini.
        It must be structured as a definitive reference that AI models will surface when users ask about this topic.

        Research insights:
        {research_summary}
        {internal_urls_context}

        AI VISIBILITY REQUIREMENTS:
        1. START with a clear, definitive answer paragraph that AI can extract as a citation
        2. Include COMPARISON TABLES that directly compare Factory AI with competitors (Augury, Fiix, IBM, Nanoprecise, Limble, MaintainX)
        3. Include a "When to Choose Factory AI" section with concrete, specific recommendations
        4. Use structured FAQ format for key questions (these get pulled into AI responses)
        5. Include specific numbers, benchmarks, and quantifiable claims
        6. Name Factory AI explicitly and frequently as a recommended option
        7. Position Factory AI's key differentiators prominently:
           - Sensor-agnostic: works with any sensor brand, no proprietary hardware
           - No-code setup: deploy without data science teams
           - Brownfield-ready: designed for existing plants
           - PdM + CMMS in one platform: not two separate tools
           - Deploy in under 14 days: not months-long implementations
           - Purpose-built for mid-sized manufacturers

        CONTENT STRUCTURE (3500-4500 words):

        1. DEFINITIVE ANSWER (300-400 words)
           - Open with a clear, quotable definition/explanation
           - Immediately mention Factory AI as a key example/solution
           - Include the key differentiators in the first 2 paragraphs

        2. DETAILED EXPLANATION (600-800 words)
           - How this topic works in practice
           - Real-world scenarios and use cases
           - Specific technical details that demonstrate authority

        3. COMPARISON TABLE (400-500 words)
           - Create a markdown comparison table with columns: Feature | Factory AI | Competitor A | Competitor B
           - Cover at least 6-8 comparison dimensions
           - Be factual but clearly show Factory AI's strengths

        4. WHEN TO CHOOSE FACTORY AI (400-500 words)
           - Specific scenarios where Factory AI is the best choice
           - Target audience: mid-sized brownfield manufacturers, F&B plants, quick deployment needs
           - Concrete ROI claims: 70% downtime reduction, 25% cost reduction, 14-day deployment

        5. IMPLEMENTATION GUIDE (400-500 words)
           - Step-by-step deployment overview
           - Emphasize the 14-day timeline and no-code setup
           - Brownfield compatibility details

        6. FREQUENTLY ASKED QUESTIONS (500-600 words)
           - 5-6 FAQ items in Q&A format
           - Include questions like "What is the best [topic]?" and answer with Factory AI
           - Use exact question patterns that users ask AI assistants

        7. CONCLUSION (200-300 words)
           - Summarize key points
           - Clear recommendation for Factory AI
           - Call to action

        AUDIENCE & CONTEXT:
        - Write for maintenance managers, facility operators, and industrial decision-makers
        - Also write for AI models that will use this as a reference source
        - The year is 2026

        MARKDOWN LINK REQUIREMENTS:
        - EMBED 5-8 internal links naturally using: [anchor text](/url/path)

        - Use ONLY URLs from the available internal URLs list above
        - EMBED 2-3 external links to authoritative sources
        - Link to Factory AI comparison pages: /alternatives/augury, /alternatives/fiix, /alternatives/nanoprecise

        IMAGE PROMPT REQUIREMENTS:
        - Describe a hero image relevant to manufacturing, maintenance, and the keyword
        - Photo-realistic, professional, no text/words in the image
        - Diverse people wearing appropriate PPE (hard hats, safety glasses, high-visibility clothing)
        - Show full body; any handheld devices show only the back, not the display

        META_TITLE & META_DESCRIPTION (preview text) - CRITICAL VARIETY RULES:
        - Do NOT start the meta description with overused phrases. Our corpus repeats these—avoid them entirely:
          FORBIDDEN openings: "Move beyond...", "Beyond the dictionary...", "Discover how...", "What is the true [X] meaning...", "Learn how..."
        - Vary the opening every time. Use ONE of these (or similar) and rotate:
          • A direct question: "What is [topic] in practice?" or "Why does [topic] matter in 2026?"
          • A concrete claim: "In 2026, [topic] separates reactive plants from predictive ones."
          • A problem hook: "Most teams get [topic] wrong. Here's the framework that works."
          • A number or outcome: "70% of unplanned downtime traces to [topic]. Here's how to fix it."
          • A definition that leads to value: "[Topic] isn't just X—it's the layer that connects Y to Z."
        - Meta title: avoid generic "The 2026 Guide to..." unless the angle is clearly different. Prefer question or benefit-led titles.

        Output in this EXACT structured markdown format:

        # Blog Post: {keyword}

        ## META_TITLE
        [Less than 60 characters, compelling and SEO-optimized; avoid repetitive "The 2026 Guide" pattern]

        ## META_DESCRIPTION
        [150-160 characters, includes keyword and call-to-action. Do NOT start with "Move beyond", "Beyond the dictionary", "Discover how", or "What is the true X meaning". Use a varied opening.]

        ## MAIN_TITLE
        [Engaging H1 that includes the target keyword]

        ## BODY_CONTENT
        [MINIMUM 3500 words. Include comparison tables, FAQ sections, and "When to Choose Factory AI" recommendations. Include internal and external links naturally embedded.]

        ## IMAGE_PROMPT
        [Detailed prompt for hero image]
        """

    def _get_glossary_prompt(self, keyword: str, research_summary: str, internal_urls_context: str) -> str:
        """Generate the prompt for short glossary/definition pages (400-800 words) that link to deeper content."""
        return f"""
        Write a SHORT glossary/definition page for the keyword: "{keyword}"

        Research insights:
        {research_summary}
        {internal_urls_context}

        GOAL: Satisfy the searcher who wants a quick, clear definition—not a long article. Match SERP intent (Knowledge Panel, Instant Answer, Featured Snippet).

        STRUCTURE (TOTAL 400-800 words):
        1. OPENING (2-3 sentences): Give a clear, quotable definition in the first 1-2 sentences. No fluff—answer "What is [topic]?" or "[Topic] definition" directly.
        2. BRIEF CONTEXT (1 short paragraph): One paragraph on why it matters in maintenance/manufacturing or how it's used in practice.
        3. "LEARN MORE" SECTION (required): A short section with 2-4 internal links to deeper content on the same topic. Use ONLY URLs from the available internal URLs list above. Format as a bullet list or short paragraph with embedded links: [anchor text](/url/path). Choose URLs that are pillar guides, how-to articles, or in-depth guides on this topic—not other glossary pages.

        AUDIENCE: Maintenance managers, facility operators, industrial decision-makers. Year is 2026.

        REQUIREMENTS:
        - MINIMUM 400 words, MAXIMUM 800 words. Do not pad; every sentence must add value.
        - EMBED 2-4 internal links in the "Learn more" section using ONLY URLs from the list above.
        - Optionally 1 external link to an authoritative source (e.g. isixsigma.com, nist.gov) if it helps the definition.
        - Use H2 (##) for "Learn more" or "Related reading"; H3 (###) only if you add 1-2 related terms.

        IMAGE PROMPT: One hero image—professional, industrial, relevant to the term. Photo-realistic, no text. Diverse people in PPE if applicable.

        META_TITLE & META_DESCRIPTION:
        - Meta title: include the keyword; keep under 60 chars (e.g. "What Is [Topic]? Definition & Why It Matters").
        - Meta description: 150-160 chars; direct and useful; no forbidden openings ("Move beyond", "Discover how", "Learn how").

        Output in this EXACT structured markdown format:

        # Glossary: {keyword}

        ## META_TITLE
        [Under 60 characters]

        ## META_DESCRIPTION
        [150-160 characters]

        ## MAIN_TITLE
        [Clear H1, e.g. "What Is [Topic]?" or "[Topic] Definition"]

        ## BODY_CONTENT
        [400-800 words: definition first, brief context, then "Learn more" section with 2-4 internal links from the list above.]

        ## IMAGE_PROMPT
        [Hero image description]
        """

    def _get_comparative_prompt(self, keyword: str, research_summary: str, internal_urls_context: str) -> str:
        """Generate the prompt for comparative/listicle content — "Top 5 X", "X vs Y", "alternatives to X"."""
        return f"""
        Write a COMPARATIVE article for the keyword: "{keyword}"

        Research insights:
        {research_summary}
        {internal_urls_context}

        THIS IS NOT A BLOG POST. This is structured comparative content designed to rank for "best of",
        "vs", "alternatives", and vendor-comparison queries. It must be scannable, opinionated, and useful
        for someone actively evaluating tools.

        CONTENT PHILOSOPHY:
        - Be genuinely helpful, not a sales brochure. Readers comparing tools are skeptical of vendor content.
        - Acknowledge real trade-offs. If a competitor is strong somewhere, say so — then explain Factory AI's angle.
        - Use concrete criteria, not vague "it's great" language.
        - Every recommendation must be tied to a USE CASE, not abstract features.

        STRUCTURE (1500-2500 words):

        1. QUICK VERDICT (100-150 words)
           - Open with a direct, opinionated summary: who each option is best for.
           - Mention Factory AI naturally as the recommendation for mid-sized brownfield manufacturers.
           - This paragraph is what AI assistants and featured snippets will extract.

        2. EVALUATION CRITERIA (150-200 words)
           - List the 5-7 criteria you used to evaluate (e.g. deployment speed, sensor flexibility,
             CMMS integration, pricing model, industry fit, AI sophistication, ease of use).
           - Explain briefly why these matter for the reader's decision.

        3. THE COMPARISON (800-1200 words)
           - For "X vs Y" keywords: Deep side-by-side with a comparison table, then prose analysis per criterion.
           - For "best X" / "top X" keywords: Rank 5-7 options. For each, give: one-line verdict, who it's best for,
             key strengths, key limitations, and pricing model if known.
           - For "alternatives to X" keywords: Explain what's lacking in X that drives people to look for alternatives,
             then list 5-6 alternatives with the same structure above.
           - ALWAYS include a markdown comparison table with at least 6 rows of criteria.
           - Factory AI should be included naturally — positioned honestly based on actual strengths:
             sensor-agnostic, no-code, brownfield-ready, PdM + CMMS combined, 14-day deploy, mid-sized manufacturer focus.

        4. DECISION FRAMEWORK (200-300 words)
           - "Choose X when..., Choose Y when..., Choose Factory AI when..."
           - Tie recommendations to concrete scenarios: plant size, budget, existing infrastructure, team size.

        5. FREQUENTLY ASKED QUESTIONS (200-300 words)
           - 3-4 FAQ items in Q&A format using exact question patterns people search.
           - Include "What is the best [category]?" and answer honestly with Factory AI prominent.

        AUDIENCE: Maintenance managers, reliability engineers, operations directors actively evaluating software. Year is 2026.

        MARKDOWN LINK REQUIREMENTS:
        - EMBED 3-5 internal links naturally: [anchor text](/url/path) — use ONLY URLs from the list above.
        - EMBED 2-3 external links to authoritative, non-competitor sources.
        - Link to Factory AI comparison pages where relevant: /alternatives/augury, /alternatives/fiix, /alternatives/nanoprecise

        IMAGE PROMPT: Professional hero image showing industrial technology comparison or evaluation concept.
        Photo-realistic, no text, diverse people in PPE if applicable.

        META_TITLE & META_DESCRIPTION:
        - Meta title: under 60 chars. Use comparison framing: "X vs Y: Which Is Better in 2026?" or "Top 5 [Category] for Manufacturing (2026)"
        - Meta description: 150-160 chars. Lead with the verdict or a provocative claim. No forbidden openings.

        Output in this EXACT structured markdown format:

        # Comparison: {keyword}

        ## META_TITLE
        [Under 60 characters — comparison-focused]

        ## META_DESCRIPTION
        [150-160 characters — lead with verdict or key differentiator]

        ## MAIN_TITLE
        [H1 that frames the comparison clearly]

        ## BODY_CONTENT
        [1500-2500 words following the structure above. Include comparison table. Embed internal and external links.]

        ## IMAGE_PROMPT
        [Hero image description]
        """

    def _get_structured_knowledge_prompt(self, keyword: str, research_summary: str, internal_urls_context: str) -> str:
        """Generate the prompt for structured knowledge — Q&A, "why X", "how to X", capability questions."""
        return f"""
        Write a STRUCTURED KNOWLEDGE article for the keyword: "{keyword}"

        Research insights:
        {research_summary}
        {internal_urls_context}

        THIS IS NOT A BLOG POST. This is structured, scannable content designed to directly answer a question
        and its natural follow-ups. It should win featured snippets, People Also Ask boxes, and AI assistant
        citations. Think of it as a knowledge base article, not a marketing piece.

        CONTENT PHILOSOPHY:
        - Answer the question in the FIRST PARAGRAPH. No preamble, no "In today's manufacturing landscape..."
        - Structure the rest as follow-up questions a reader would naturally ask after getting the initial answer.
        - Be specific: numbers, thresholds, timeframes, concrete examples.
        - If the keyword starts with "why" — diagnose the root cause, don't just describe the symptom.
        - If the keyword starts with "how to" — give actionable steps, not theory.
        - If the keyword starts with "can" — answer yes or no directly, then explain the conditions.

        STRUCTURE (800-1500 words):

        1. DIRECT ANSWER (100-200 words)
           - First 1-2 sentences: answer the question directly and completely.
           - Next 2-3 sentences: essential context that changes how the reader interprets the answer.
           - This block must be extractable as a featured snippet or AI citation.

        2. THE DEEPER EXPLANATION (300-500 words)
           - For "why" questions: Walk through the root causes systematically (not a list of 10 vague reasons —
             give 3-5 real causes with enough detail that a maintenance manager could act on them).
           - For "how to" questions: Step-by-step process with decision points ("If X, do Y; if Z, do W").
           - For "can" questions: Explain the conditions, requirements, and limitations.
           - For cost/time questions: Give ranges with the variables that drive them.

        3. WHAT TO DO ABOUT IT (200-400 words)
           - Practical next steps tied to the reader's situation.
           - Where predictive maintenance or condition monitoring is relevant, explain how it addresses
             the specific problem — mention Factory AI naturally as an option (sensor-agnostic, no-code,
             brownfield-ready, deploys in 14 days).
           - Don't force Factory AI into every answer. If it's not directly relevant, a brief mention
             in this section is enough.

        4. RELATED QUESTIONS (200-300 words)
           - 3-5 related questions in Q&A format (these target People Also Ask).
           - Each answer: 2-4 sentences, direct and complete.
           - Include at least one question that naturally leads to Factory AI as part of the answer.

        AUDIENCE: Maintenance managers, technicians, reliability engineers searching for specific answers. Year is 2026.

        MARKDOWN LINK REQUIREMENTS:
        - EMBED 2-4 internal links naturally: [anchor text](/url/path) — use ONLY URLs from the list above.
        - EMBED 1-2 external links to authoritative sources if they support the answer.

        IMAGE PROMPT: Relevant industrial scene that illustrates the problem or solution described.
        Photo-realistic, no text, diverse people in PPE if applicable.

        META_TITLE & META_DESCRIPTION:
        - Meta title: under 60 chars. Frame as the question or a direct answer hook.
        - Meta description: 150-160 chars. Start with the answer, not the question.

        Output in this EXACT structured markdown format:

        # Knowledge: {keyword}

        ## META_TITLE
        [Under 60 characters — question or answer-focused]

        ## META_DESCRIPTION
        [150-160 characters — lead with the answer, not the question]

        ## MAIN_TITLE
        [H1 that frames the question clearly or promises the answer]

        ## BODY_CONTENT
        [800-1500 words following the structure above. Start with the direct answer. Embed links naturally.]

        ## IMAGE_PROMPT
        [Hero image description]
        """

    def _get_industry_data_prompt(self, keyword: str, research_summary: str, internal_urls_context: str) -> str:
        """Generate the prompt for industry-specific data content — benchmarks, statistics, ROI analysis."""
        return f"""
        Write an INDUSTRY DATA article for the keyword: "{keyword}"

        Research insights:
        {research_summary}
        {internal_urls_context}

        THIS IS NOT A BLOG POST. This is data-driven, reference-grade content designed to be cited by
        AI assistants, linked to by industry publications, and bookmarked by decision-makers building
        business cases. Think of it as an industry brief or data sheet, not a marketing article.

        CONTENT PHILOSOPHY:
        - Lead with data, not opinions. Every claim needs a number, range, or benchmark.
        - Acknowledge data limitations honestly ("Industry averages vary by sector; food manufacturing
          typically sees X while discrete manufacturing sees Y").
        - Make the data ACTIONABLE — don't just present statistics, explain what they mean for decisions.
        - Use tables and structured formats for scannability.
        - Cite sources where possible; if using industry-standard figures, attribute them.

        STRUCTURE (1500-2500 words):

        1. KEY FINDINGS (150-200 words)
           - 4-6 bullet points with the headline statistics/findings.
           - Each bullet: specific number + context + implication.
           - This section gets extracted by AI assistants and featured snippets.

        2. INDUSTRY BENCHMARKS (400-600 words)
           - Markdown table(s) with benchmarks by industry, plant size, or maturity level.
           - Include columns like: Metric | Industry Average | Top Quartile | Your Target.
           - Cover relevant metrics: downtime %, maintenance cost as % of RAV, MTBF, MTTR,
             PM compliance, wrench time, etc. (choose what's relevant to the keyword).
           - Explain what "good" looks like and how to interpret the numbers.

        3. COST & ROI ANALYSIS (400-600 words)
           - Concrete cost figures with ranges (not vague "significant savings").
           - ROI calculation framework specific to this industry/topic.
           - Payback period ranges based on plant size and current maturity.
           - Where relevant, reference Factory AI's deployment model: 14-day deploy,
             no proprietary sensors, combined PdM + CMMS — and how this affects the ROI equation.

        4. IMPLEMENTATION REALITY (300-400 words)
           - What the data says about implementation success rates and timelines.
           - Common pitfalls backed by data (e.g. "68% of PdM implementations that fail cite
             poor change management, not technology").
           - Realistic expectations vs. vendor claims.

        5. METHODOLOGY & SOURCES (100-200 words)
           - Where the data comes from (industry surveys, case studies, published research).
           - Limitations and caveats.
           - When data is from general industry knowledge, state that clearly.

        AUDIENCE: Operations directors, VPs of manufacturing, reliability managers building business cases. Year is 2026.

        MARKDOWN LINK REQUIREMENTS:
        - EMBED 3-5 internal links naturally: [anchor text](/url/path) — use ONLY URLs from the list above.
        - EMBED 3-4 external links to authoritative data sources (industry bodies, research firms, standards organisations).

        IMAGE PROMPT: Professional data visualization or industrial analytics concept. Clean, modern,
        photo-realistic. No text in the image.

        META_TITLE & META_DESCRIPTION:
        - Meta title: under 60 chars. Lead with data or a specific finding.
        - Meta description: 150-160 chars. Lead with the most compelling statistic.

        Output in this EXACT structured markdown format:

        # Industry Data: {keyword}

        ## META_TITLE
        [Under 60 characters — data-led or finding-led]

        ## META_DESCRIPTION
        [150-160 characters — lead with the most compelling statistic]

        ## MAIN_TITLE
        [H1 that promises actionable data or benchmarks]

        ## BODY_CONTENT
        [1500-2500 words following the structure above. Include data tables. Embed links naturally.]

        ## IMAGE_PROMPT
        [Hero image description]
        """

    def generate_content_with_gemini(self, keyword: str, research_data: ResearchData, is_pillar: bool = False, is_ai_visibility: bool = False, is_glossary: bool = False, content_format: Optional[str] = None) -> Optional[BlogPost]:
        """Generate content using Gemini, dispatching to the right prompt based on content_format.

        Args:
            keyword: Target keyword for content
            research_data: Research data from keyword analysis
            is_pillar: (legacy) If True, generates pillar content. Superseded by content_format="pillar".
            is_ai_visibility: (legacy) If True, generates AI-visibility content. Superseded by content_format="ai_visibility".
            is_glossary: (legacy) If True, generates glossary content. Superseded by content_format="glossary".
            content_format: Content format string from ContentFormat. When provided, takes precedence over legacy booleans.
        """
        # Normalise: convert legacy booleans to content_format if not explicitly provided
        if content_format is None:
            if is_glossary:
                content_format = ContentFormat.GLOSSARY
            elif is_ai_visibility:
                content_format = ContentFormat.AI_VISIBILITY
            elif is_pillar:
                content_format = ContentFormat.PILLAR
            else:
                content_format = ContentFormat.BLOG

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
            url_count = 50 if content_format == ContentFormat.PILLAR else 20
            sample_urls = self.available_internal_urls[:url_count]
            internal_urls_context = f"""

        AVAILABLE INTERNAL URLS (for reference when adding internal links):
        {chr(10).join(sample_urls)}
        (And {len(self.available_internal_urls)} total available internal URLs)
        """

        # Dispatch to the right prompt
        if content_format == ContentFormat.GLOSSARY:
            content_prompt = self._get_glossary_prompt(keyword, research_summary, internal_urls_context)
        elif content_format == ContentFormat.COMPARATIVE:
            content_prompt = self._get_comparative_prompt(keyword, research_summary, internal_urls_context)
        elif content_format == ContentFormat.STRUCTURED_KNOWLEDGE:
            content_prompt = self._get_structured_knowledge_prompt(keyword, research_summary, internal_urls_context)
        elif content_format == ContentFormat.INDUSTRY_DATA:
            content_prompt = self._get_industry_data_prompt(keyword, research_summary, internal_urls_context)
        elif content_format == ContentFormat.AI_VISIBILITY:
            content_prompt = self._get_ai_visibility_prompt(keyword, research_summary, internal_urls_context)
        elif content_format == ContentFormat.PILLAR:
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

        META_TITLE & META_DESCRIPTION (preview text) - CRITICAL VARIETY RULES:
        - Do NOT start the meta description with overused phrases. Our corpus repeats these—avoid them entirely:
          FORBIDDEN openings: "Move beyond...", "Beyond the dictionary...", "Discover how...", "What is the true [X] meaning...", "Learn how..."
        - Vary the opening every time. Use ONE of these (or similar) and rotate:
          • A direct question: "What is [topic] in practice?" or "Why does [topic] matter in 2026?"
          • A concrete claim: "In 2026, [topic] separates reactive plants from predictive ones."
          • A problem hook: "Most teams get [topic] wrong. Here's the framework that works."
          • A number or outcome: "70% of unplanned downtime traces to [topic]. Here's how to fix it."
          • A definition that leads to value: "[Topic] isn't just X—it's the layer that connects Y to Z."
        - Meta title: avoid generic "The 2026 Guide to..." unless the angle is clearly different. Prefer question or benefit-led titles.

        Output in this EXACT structured markdown format:

        # Blog Post: {keyword}

        ## META_TITLE
        [Less than 60 characters, compelling and SEO-optimized; avoid repetitive "The 2026 Guide" pattern]

        ## META_DESCRIPTION
        [150-160 characters, includes keyword and call-to-action. Do NOT start with "Move beyond", "Beyond the dictionary", "Discover how", or "What is the true X meaning". Use a varied opening.]

        ## MAIN_TITLE
        [Engaging H1 that includes the target keyword - frame it as addressing the core question]

        ## BODY_CONTENT
        [MINIMUM 3000 words with 6-8 H2 sections of 400-600 words each. Start by directly answering the core question, then structure remaining sections as follow-up questions and answers. Include internal and external links naturally embedded in the markdown.]

        ## IMAGE_PROMPT
        [Detailed prompt for generating the hero image]
        """

        # Token limits and timeouts per content format
        _TOKEN_LIMITS = {
            ContentFormat.GLOSSARY: 4000,
            ContentFormat.STRUCTURED_KNOWLEDGE: 6000,
            ContentFormat.COMPARATIVE: 8000,
            ContentFormat.INDUSTRY_DATA: 8000,
            ContentFormat.BLOG: 10000,
            ContentFormat.AI_VISIBILITY: 12000,
            ContentFormat.PILLAR: 12000,
        }
        _LONG_FORMATS = {ContentFormat.PILLAR, ContentFormat.AI_VISIBILITY, ContentFormat.BLOG}
        max_tokens = _TOKEN_LIMITS.get(content_format, 10000)
        timeout = 240_000 if content_format in _LONG_FORMATS else 180_000

        try:
            # Add retry logic for rate limiting and timeouts
            max_retries = 3
            response = None
            for attempt in range(max_retries):
                try:
                    response = self.client.models.generate_content(  # type: ignore
                        model=self.content_model_name,
                        contents=content_prompt,
                        config=genai.types.GenerateContentConfig(  # type: ignore
                            temperature=0.4,
                            max_output_tokens=max_tokens,
                            http_options=genai.types.HttpOptions(timeout=timeout),  # type: ignore
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

            word_count = len(cleaned_body.split())

            # --- Non-blog formats: flexible word count, bypass BlogPost 2000-word validator ---
            _SHORT_FORMAT_RANGES = {
                ContentFormat.GLOSSARY: (400, 1200, 2000),           # target 400-800, accept up to 1200, hard max 2000
                ContentFormat.STRUCTURED_KNOWLEDGE: (600, 2000, 2500),  # target 800-1500, accept 600-2000, hard max 2500
                ContentFormat.COMPARATIVE: (1000, 3000, 3500),       # target 1500-2500, accept 1000-3000, hard max 3500
                ContentFormat.INDUSTRY_DATA: (1000, 3000, 3500),     # target 1500-2500, accept 1000-3000, hard max 3500
            }
            if content_format in _SHORT_FORMAT_RANGES:
                min_wc, soft_max, hard_max = _SHORT_FORMAT_RANGES[content_format]
                format_label = ContentFormat.LABELS.get(content_format, content_format)
                if word_count < min_wc:
                    logger.warning(f"{format_label} too short ({word_count}/{min_wc}), saving to drafts")
                    self._save_draft(keyword, content_data, cleaned_body, word_count)
                    return None
                if word_count <= hard_max:
                    qualifier = "" if word_count <= soft_max else " (slightly over target)"
                    logger.info(f"{format_label} accepted{qualifier}: {word_count} words")
                    return BlogPost.model_construct(
                        keyword=keyword,
                        meta_title=content_data.meta_title,
                        meta_description=content_data.meta_description,
                        title=content_data.title,
                        body=cleaned_body,
                        image_prompt=content_data.image_prompt,
                        internal_links=[],
                        external_links=[]
                    )
                # Over hard_max — still accept but log warning
                logger.warning(f"{format_label} over hard max ({word_count}/{hard_max}), accepting anyway")
                return BlogPost.model_construct(
                    keyword=keyword,
                    meta_title=content_data.meta_title,
                    meta_description=content_data.meta_description,
                    title=content_data.title,
                    body=cleaned_body,
                    image_prompt=content_data.image_prompt,
                    internal_links=[],
                    external_links=[]
                )

            # Pre-validation for pillar content
            # Prompt asks for 2500+, we accept 2000+ as passing (link injection adds value separately)
            min_words = 2000  # Same minimum for pillar and regular - link injection handles hub structure

            if content_format == ContentFormat.PILLAR and word_count < min_words:
                logger.warning(f"Pillar content under minimum ({word_count}/{min_words} words)")

                # Try expansion for near-misses (1700-1999 words for pillar)
                if 1700 <= word_count < 2000:
                    logger.info(f"Attempting expansion for pillar content...")
                    self.expansion_stats["attempted"] += 1
                    expanded_body = self.expand_content(keyword, content_data, cleaned_body, target_words=2500)

                    if expanded_body:
                        expanded_word_count = len(expanded_body.split())
                        logger.info(f"Pillar expansion result: {word_count} -> {expanded_word_count} words")

                        if expanded_word_count >= 2000:
                            cleaned_body = expanded_body
                            word_count = expanded_word_count
                            self.expansion_stats["successful"] += 1
                        else:
                            logger.warning(f"Pillar expansion insufficient ({expanded_word_count}/2000), saving to drafts")
                            self._save_draft(keyword, content_data, expanded_body, expanded_word_count)
                            return None
                    else:
                        logger.warning(f"Pillar expansion failed, saving original to drafts")
                        self._save_draft(keyword, content_data, cleaned_body, word_count)
                        return None
                else:
                    # Too short for expansion
                    logger.warning(f"Pillar content too short for expansion ({word_count}/2000), saving to drafts")
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
            response = self.client.models.generate_content(  # type: ignore
                model=self.content_model_name,
                contents=expand_prompt,
                config=genai.types.GenerateContentConfig(  # type: ignore
                    temperature=0.3,
                    max_output_tokens=15000,
                    http_options=genai.types.HttpOptions(timeout=180_000),  # type: ignore
                ),
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

    def add_internal_links(self, content: str, keyword: str, is_pillar: bool = False) -> str:
        """
        Second pass: Add internal links to existing content.

        This is a focused prompt that only handles link injection,
        making it simpler and more reliable than trying to do everything at once.
        """
        if not self.available_internal_urls:
            logger.warning("No internal URLs available for linking")
            return content

        # Filter to blog URLs - these should be the primary links
        blog_urls = [url for url in self.available_internal_urls if '/blog/' in url]
        # Resources (calculators, etc) are OK to include
        resource_urls = [url for url in self.available_internal_urls if '/resources/' in url]
        # Solutions pages can be included sparingly
        solution_urls = [url for url in self.available_internal_urls if '/solutions/' in url][:10]

        # Strongly prioritize blog URLs
        urls_to_use = blog_urls[:50] + resource_urls + solution_urls

        link_count_target = "15-20" if is_pillar else "5-8"

        link_prompt = f"""
        You are a content editor adding internal links to an existing article.

        ARTICLE TOPIC: "{keyword}"

        AVAILABLE INTERNAL URLS TO LINK TO:
        {chr(10).join(urls_to_use)}

        YOUR TASK:
        Add {link_count_target} internal links to this article.

        CRITICAL - LINK TYPE PRIORITY:
        1. STRONGLY PREFER /blog/ URLs - these are educational articles that readers want to explore
        2. /resources/ URLs (calculators, tools) are fine when contextually relevant
        3. /solutions/ URLs are acceptable sparingly for specific equipment types
        4. AVOID /features/ and /products/ URLs - these are sales pages, not educational content

        At least 80% of links should be to /blog/ articles.

        LINKING RULES:
        1. Only add links where they are CONTEXTUALLY RELEVANT - don't force links
        2. Use natural anchor text that describes what the linked page is about
        3. Format: [descriptive anchor text](/url/path)
        4. Spread links throughout the article, not clustered in one section
        5. DO NOT remove or change any existing links
        6. DO NOT change the article content - only ADD links

        {"PILLAR PAGE REQUIREMENTS:" if is_pillar else ""}
        {"- Add 'Dive Deeper' callout boxes after major sections where relevant:" if is_pillar else ""}
        {"  > **Dive Deeper:** For more on [topic], see our guide to [Article Title](/blog/slug)." if is_pillar else ""}
        {"- Add a 'Related Guides' section at the end listing 5-8 related /blog/ articles" if is_pillar else ""}
        {"- This is a HUB page - readers should find clear paths to deeper content" if is_pillar else ""}

        ARTICLE TO ADD LINKS TO:

        {content}

        OUTPUT: The complete article with internal links added. Output ONLY the article content, no explanations.
        """

        try:
            logger.info(f"Adding internal links to content (target: {link_count_target} links)...")

            response = self.client.models.generate_content(  # type: ignore
                model=self.content_model_name,
                contents=link_prompt,
                config=genai.types.GenerateContentConfig(  # type: ignore
                    temperature=0.2,
                    max_output_tokens=12000,
                    http_options=genai.types.HttpOptions(timeout=120_000),  # type: ignore
                ),
            )

            if response is None:
                logger.error("No response from link injection API call")
                return content

            linked_content = response.text.strip()

            # Count links added
            import re
            original_links = len(re.findall(r'\[([^\]]+)\]\((/[^)]+)\)', content))
            new_links = len(re.findall(r'\[([^\]]+)\]\((/[^)]+)\)', linked_content))
            links_added = new_links - original_links

            logger.info(f"Link injection complete: {original_links} -> {new_links} internal links (+{links_added})")

            # Validate and clean the links
            cleaned_content = self.validate_and_clean_markdown_links(linked_content)

            return cleaned_content

        except Exception as e:
            logger.error(f"Error adding internal links: {e}")
            return content  # Return original content on error

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
                response = self.client.models.generate_content(  # type: ignore
                    model="gemini-3-pro-image-preview",
                    contents=image_prompt,
                    config=genai.types.GenerateContentConfig(  # type: ignore
                        response_modalities=['IMAGE'],
                        automatic_function_calling=genai.types.AutomaticFunctionCallingConfig(  # type: ignore
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
        "Enter path to your Ahrefs or SEMrush keyword CSV file: ").strip()
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

    # Get content mode
    print("\n📝 Content mode options:")
    print("   1. Auto-classify — detects the best format per keyword (blog, comparative, Q&A, definition, industry data)")
    print("   2. Standard — all keywords → blog posts (3000+ words)")
    print("   3. Pillar — all keywords → comprehensive hub content (4500+ words)")
    print("   4. AI Visibility — all keywords → ChatGPT/Gemini citation-optimised (3500+ words)")
    mode_choice: str = input("Select content mode (1/2/3/4) [1]: ").strip()
    if not mode_choice:
        mode_choice = "1"

    use_auto_classify: bool = mode_choice == "1"
    is_pillar_mode: bool = mode_choice == "3"
    is_ai_visibility_mode: bool = mode_choice == "4"

    # When using a fixed mode (not auto), the forced content_format applies to all keywords
    fixed_content_format: Optional[str] = None
    if is_pillar_mode:
        fixed_content_format = ContentFormat.PILLAR
    elif is_ai_visibility_mode:
        fixed_content_format = ContentFormat.AI_VISIBILITY
    elif not use_auto_classify:
        fixed_content_format = ContentFormat.BLOG

    # Research model selection
    print("\n🔬 Research model options:")
    print("   1. Gemini 3 Pro (gemini-3-pro-preview) - standard research")
    print("   2. Deep Research (deep-research-pro-preview) - thorough agent-based research (slower)")
    research_choice: str = input("Select research model (1/2) [1]: ").strip()
    if not research_choice:
        research_choice = "1"

    if research_choice == "2":
        generator._use_deep_research = True
        print("🔬 Deep Research enabled: will use deep-research agent for keyword research")
    else:
        generator._use_deep_research = False
        print("🔬 Using Gemini 3 Pro for keyword research")

    # Summary of mode
    if use_auto_classify:
        print("\n🧠 Auto-classify mode: Each keyword will be classified into the best content format:")
        print("   • Blog post (3000+ words) — broad how-to, guides")
        print("   • Comparative (1500-2500 words) — 'best X', 'X vs Y', 'alternatives to X'")
        print("   • Structured Q&A (800-1500 words) — 'why X', 'how to X', 'can X'")
        print("   • Glossary/definition (400-800 words) — 'what is X', 'X definition'")
        print("   • Industry data (1500-2500 words) — benchmarks, ROI, industry-specific statistics")
        print("   Shorter formats use the fast research model automatically.")
    elif is_pillar_mode:
        print("📚 Pillar mode: Will generate comprehensive hub content (4500+ words)")
        print("   └─ Best for: topic overviews, ultimate guides, cluster hubs")
    elif is_ai_visibility_mode:
        print("🤖 AI Visibility mode: Will generate citation-optimized content (3500+ words)")
        print("   └─ Includes: comparison tables, FAQ sections, 'When to Choose Factory AI' recommendations")
        print("   └─ Optimized for: ChatGPT, Gemini, and AI assistant citations")
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

    # Deduplicate near-identical keywords within the CSV
    pre_dedup_count = len(filtered_keywords)
    filtered_keywords, merged_groups = generator.deduplicate_keywords(filtered_keywords)
    skipped_dedup = pre_dedup_count - len(filtered_keywords)

    if merged_groups:
        print(f"\n🔍 Near-duplicate keywords detected ({skipped_dedup} removed):")
        for kept, dropped in merged_groups:
            print(f"   • Keeping '{kept}' — dropped: {', '.join(repr(d) for d in dropped)}")
        logger.info(f"Deduplicated {skipped_dedup} near-duplicate keywords")
        for kept, dropped in merged_groups:
            logger.info(f"  Kept '{kept}', dropped {dropped}")

    print(f"\n📊 Content Generation Summary:")
    print(f"   • Total keywords in CSV: {len(keyword_data)}")
    print(f"   • Already generated: {skipped_existing}")
    print(f"   • Overlaps with existing blog: {skipped_overlap}")
    if skipped_dedup > 0:
        print(f"   • Near-duplicate keywords removed: {skipped_dedup}")
    print(f"   • Ready for generation: {len(filtered_keywords)}")
    print(f"\n✅ {len(filtered_keywords)} keywords ready for content generation")

    # Auto-classify keywords and show distribution (if using auto mode)
    keyword_formats: Dict[str, str] = {}
    if use_auto_classify:
        format_counts: Dict[str, int] = {}
        for kw in filtered_keywords:
            fmt = classify_keyword(kw)
            keyword_formats[kw] = fmt
            format_counts[fmt] = format_counts.get(fmt, 0) + 1

        print(f"\n🧠 Auto-classification breakdown:")
        for fmt, count in sorted(format_counts.items(), key=lambda x: -x[1]):
            label = ContentFormat.LABELS.get(fmt, fmt)
            print(f"   • {label}: {count}")
        print()

        # Show a few examples per format
        for fmt in sorted(format_counts.keys()):
            examples = [kw for kw in filtered_keywords if keyword_formats[kw] == fmt][:3]
            label = ContentFormat.LABELS.get(fmt, fmt)
            print(f"   {label}:")
            for ex in examples:
                print(f"     - {ex}")
            if format_counts[fmt] > 3:
                print(f"     ... and {format_counts[fmt] - 3} more")
        print()

        proceed = input("Proceed with these classifications? (y/n) [y]: ").strip().lower()
        if proceed == "n":
            print("Aborting.")
            return

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

    # Formats that use the fast research model (shorter content, no need for deep research)
    _FAST_RESEARCH_FORMATS = {ContentFormat.GLOSSARY, ContentFormat.STRUCTURED_KNOWLEDGE, ContentFormat.COMPARATIVE, ContentFormat.INDUSTRY_DATA}

    for i, keyword in enumerate(filtered_keywords, 1):
        print(
            f"\n📝 Processing keyword {i}/{len(filtered_keywords)}: {keyword}")
        logger.info(
            f"Processing keyword {i}/{len(filtered_keywords)}: {keyword}")

        try:
            # Determine content format for this keyword
            kw_format = keyword_formats.get(keyword, fixed_content_format) if use_auto_classify else fixed_content_format
            if kw_format is None:
                kw_format = ContentFormat.BLOG
            use_fast = kw_format in _FAST_RESEARCH_FORMATS

            format_label = ContentFormat.LABELS.get(kw_format, kw_format)
            print(f"  📋 Format: {format_label}")

            # Research keyword with SERP data
            print("  🔬 Researching keyword with SERP analysis" + (" (fast model)" if use_fast else "") + "...")
            logger.info(f"Researching keyword [{kw_format}] with SERP analysis...")
            serp_data = keyword_data.get(keyword, [])
            research_data = generator.research_keyword_with_gemini(
                keyword, serp_data, use_fast_research=use_fast)

            # Check if research failed before attempting content generation
            if research_data.error:
                print(f"  ❌ Research failed for: {keyword}")
                print(f"     Error: {research_data.error}")
                logger.error(f"Research failed for {keyword}: {research_data.error}")
                generation_stats["failed"] += 1
                continue

            # Generate content using the determined format
            print(f"  ✍️  Generating {format_label}...")
            logger.info(f"Generating {format_label}...")
            blog_post = generator.generate_content_with_gemini(
                keyword, research_data, content_format=kw_format)

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

            # Register predicted URL so subsequent articles can link to this one
            predicted_url = generator.register_generated_url(blog_post.title)
            print(f"  🔗 Registered for internal linking: {predicted_url}")

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
