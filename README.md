# SEO Content Generator & Prismic Uploader

A comprehensive system for automated SEO content generation and publishing to Prismic CMS. This system generates high-quality, SEO-optimized blog posts using AI and automatically publishes them to your Prismic repository.

## 🚀 Features

### Content Generation
- **AI-Powered Research**: Uses Gemini 3 Pro (or configurable model) for deep keyword research and competitive analysis; content generation uses a separate high-limit model (e.g. Gemini 2.5 Flash) to avoid RPD limits
- **High-Quality Content**: Generates 2500-4000 word blog posts with proper structure and SEO optimization
- **Image Generation**: Creates hero images using OpenAI's GPT-4 Image Generation
- **Link Validation**: Automatically validates internal and external links
- **SERP Analysis**: Analyzes search engine results to identify content gaps and opportunities

### Prismic Integration
- **Automated Upload**: Seamlessly uploads content to Prismic CMS with proper formatting
- **Asset Management**: Handles image uploads to Prismic Asset API
- **Structured Content**: Creates properly formatted slices and rich text content
- **Duplicate Prevention**: Checks for existing content to avoid duplicates

### Background Processing
- **Scheduled Execution**: Automated background agent for continuous content generation
- **Queue Management**: Processes multiple keywords with configurable concurrency
- **Monitoring & Logging**: Comprehensive logging and status monitoring
- **Email Notifications**: Optional email alerts for processing status

## 📋 Prerequisites

### Required API Keys
- **Google Gemini API Key**: For content generation and research
- **OpenAI API Key**: For image generation (optional; hero images can use Gemini)
- **Prismic Write Token**: For uploading content to Prismic CMS

### System Requirements
- **Python 3.8+**: For content generation
- **Node.js 16+**: For Prismic upload functionality
- **npm**: For Node.js dependencies

## 🛠️ Installation

### 1. Clone and Setup Python Environment

```bash
cd seo/
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install Node.js Dependencies

```bash
npm install
```

### 3. Environment Configuration

Create a `.env` file in the `seo/` directory:

```bash
# Required API Keys
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
PRISMIC_API_KEY=your_prismic_write_token_here

# Optional: Gemini model split (saves Gemini 3 Pro RPD; see "Rate limits" below)
# GEMINI_RESEARCH_MODEL=gemini-3-pro-preview
# GEMINI_CONTENT_MODEL=gemini-3-flash-preview
# Optional: Use Deep Research Pro Preview for research (1 RPM; set to 1 to enable)
# USE_DEEP_RESEARCH=1

# Optional: Enable debug mode
DEBUG=true
```

### Rate limits & model choice

Gemini 3 Pro has a **250 requests/day (RPD)** limit. The generator uses **two models** by default so you can run many more keywords per day without sacrificing research quality:

| Role | Default model | Typical limit | Used for |
|------|----------------|---------------|----------|
| **Research** | `gemini-3-pro-preview` | 250 RPD | Keyword + SERP analysis (1 call per keyword) |
| **Content** | `gemini-3-flash-preview` | Check dashboard | Article generation, expansion, internal links (2–4 calls per keyword) |

So you get **up to ~250 research runs/day** (Gemini 3 Pro) and content on **Gemini 3 Flash** (better quality than 2.5 Flash). Override via env:

- `GEMINI_RESEARCH_MODEL` – e.g. `gemini-3-pro-preview`
- `GEMINI_CONTENT_MODEL` – e.g. `gemini-3-flash-preview` (default, best quality), or `gemini-2.5-flash` (10K RPD) / `gemini-2.0-flash` (unlimited RPD) if your 3 Flash RPD is tight

**Deep Research Pro Preview** is an *agent* (Interactions API). You can try it for research by setting `USE_DEEP_RESEARCH=1` in your environment. The agent has a 1 RPM–style limit, which is fine if you generate about one piece of content per minute. Requires `google-genai` (see requirements). The script will use the same structured markdown format and stream with reconnection for long-running runs.

### 4. Prepare Keyword Data

Create a CSV file named `kw.csv` with your keywords. The system supports various CSV formats from SEO tools like Ahrefs. Required columns:
- `Keyword` (or similar): The target keyword
- Optional SERP data columns: `Title`, `URL`, `Position`, `Traffic`, etc.

Example CSV structure:
```csv
Keyword,Position,Traffic,Difficulty,Volume
maintenance management software,5,120,45,1200
predictive maintenance,3,80,55,2100
cmms software,8,200,65,3500
```

## 🎯 Usage

### Interactive Mode (Recommended for First Time)

```bash
python seo_content_generator.py
```

This will prompt you for:
- CSV file path
- Sitemap URL (default: https://f7i.ai/sitemap.xml)
- Prismic upload preference (y/n/test)

### Non-Interactive Mode

```bash
python run_seo_bot.py
```

Automatically processes keywords from `kw.csv` with default settings.

### Background Agent Mode

For continuous automated processing:

```bash
# Run once
python background_agent.py --run-once

# Start background service
python background_agent.py

# Check status
python background_agent.py --status
```

### Manual Prismic Upload

Upload individual files to Prismic:

```bash
# Test mode (validates without uploading)
node prismic_uploader.js generated_content/my-keyword.json --skip-upload

# Actual upload
node prismic_uploader.js generated_content/my-keyword.json

# Batch upload all files
node prismic_uploader.js --batch

# Debug mode
node prismic_uploader.js generated_content/my-keyword.json --debug
```

## ⚙️ Configuration

### Background Agent Configuration

Edit `agent_config.yaml` to customize the background agent:

```yaml
# Processing settings
max_keywords_per_run: 3
concurrent_workers: 1
retry_attempts: 3
retry_delay: 60

# Scheduling
run_interval_hours: 24
run_at_hour: 2

# Rate limiting
rate_limit_delay: 15

# Email notifications
email_notifications: false
smtp_server: "smtp.gmail.com"
smtp_port: 587
notification_recipients:
  - "admin@yourdomain.com"
```

### Content Requirements

The system is configured to generate content that meets these SEO standards:
- **Word Count**: 2500-4000 words minimum
- **Meta Title**: Under 60 characters
- **Meta Description**: 150-160 characters
- **Internal Links**: 3-5 per article
- **External Links**: 2-3 to authoritative sources

## 📊 Generated Content Structure

### Files Created
For each keyword, the system creates:
- `{keyword}.json`: Metadata and Prismic-formatted content
- `{keyword}.md`: Human-readable markdown content
- `{keyword}.png`: Generated hero image

### Content Format
Generated blog posts include:
- SEO-optimized meta title and description
- Comprehensive article body with proper H2/H3 structure
- Naturally embedded internal and external links
- Industry-relevant hero image
- Keyword-focused content optimized for search intent

## 🔧 Prismic Setup

### Required Prismic Configuration

Your Prismic repository needs these slices:
- **TitleAndBody**: Main content slice with title, category, featured image, and markdown body
- **ProfileTim**: Author profile slice

### Slice Structure
The `TitleAndBody` slice should have these fields:
- `title`: Rich Text (H1)
- `category`: Text (for keyword)
- `featuredimage`: Image
- `markdownmainbody`: Rich Text (StructuredText with preformatted support)

## 📈 Monitoring & Logging

### Log Files
- `logs/agent_YYYYMMDD.log`: Daily log files with detailed processing information
- Console output: Real-time processing status

### Status Monitoring
```bash
# Check background agent status
python background_agent.py --status

# View recent logs
tail -f logs/agent_$(date +%Y%m%d).log
```

## 🚨 Troubleshooting

### Common Issues

#### "Rich text field must be an array" Error
**Solution**: This error has been fixed in the latest version. The system now properly formats markdown content as StructuredText arrays.

#### Rate Limiting Issues
**Solution**: Increase `rate_limit_delay` in `agent_config.yaml` or reduce `concurrent_workers`.

#### Missing Dependencies
```bash
# Python dependencies
pip install -r requirements.txt

# Node.js dependencies
npm install
```

#### API Key Issues
Verify your API keys in the `.env` file:
```bash
# Test Gemini API
python -c "import google.generativeai as genai; import os; genai.configure(api_key=os.getenv('GEMINI_API_KEY')); print('Gemini API: OK')"

# Test OpenAI API
python -c "import openai; import os; client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY')); print('OpenAI API: OK')"
```

#### Prismic Upload Failures
1. Verify `PRISMIC_API_KEY` is a write token (not read-only)
2. Check repository name in `prismic_uploader.js`
3. Ensure required slices exist in your Prismic repository
4. Use `--debug` flag for detailed error information

### Debug Mode
Enable detailed logging:
```bash
# Environment variable
export DEBUG=true

# Or add to .env file
echo "DEBUG=true" >> .env

# Run with debug output
node prismic_uploader.js generated_content/test.json --debug
```

## 📚 Architecture Overview

### System Components
1. **SEOContentGenerator**: Main Python class handling research and content generation
2. **PrismicUploader**: Node.js script for CMS integration
3. **BackgroundAgent**: Automated processing service
4. **Content Models**: Pydantic models for type safety and validation

### Processing Flow
1. Load keywords from CSV file
2. Check for existing content (avoid duplicates)
3. Research keyword using the configured research model (default: Gemini 3 Pro) with SERP analysis
4. Generate comprehensive blog post content
5. Create hero image using OpenAI
6. Validate and clean all links
7. Format content for Prismic CMS
8. Upload to Prismic with proper slice structure

### Data Models
The system uses strict Pydantic models for:
- Content requirements and validation
- Blog post structure
- Research data
- Prismic formatting
- Processing results

## 🤝 Contributing

### Development Setup
```bash
# Install with development dependencies
pip install -r requirements.txt
mypy --install-types

# Run type checking
mypy seo_content_generator.py

# Test single keyword
python seo_content_generator.py
```

### Code Quality
- **Type Hints**: All functions use proper type annotations
- **Error Handling**: Comprehensive exception handling with retries
- **Logging**: Detailed logging for debugging and monitoring
- **Validation**: Pydantic models ensure data integrity

## 📄 License

This project is part of the f7i.ai marketing system and is proprietary to Factory AI.

## 🆘 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review log files for detailed error information
3. Use debug mode for additional diagnostic information
4. Contact the development team with specific error messages and log excerpts

---

**Note**: This system is optimized for industrial maintenance and CMMS-related content generation. The AI models are specifically prompted for B2B industrial audiences and technical content.