"""
Content generation pipeline for "The State of AI in Manufacturing 2026" interactive microsite.

Uses Gemini 3 Pro for research and content generation, and Gemini 3 Pro Image Preview
for generating section illustrations.

Outputs:
  - f7i-public/app/learning/state-of-ai-in-manufacturing/_data/content.json
  - f7i-public/public/images/ai-manufacturing/*.png

Usage:
  python generate_ai_manufacturing_content.py [--content-only] [--images-only] [--section SECTION_ID]
"""

import json
import os
import sys
import time
import base64
import argparse
import logging
import datetime
from typing import Dict, Any, Optional, List, Tuple
from dotenv import load_dotenv

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    os.makedirs('logs', exist_ok=True)
    current_date = datetime.datetime.now().strftime('%Y%m%d')
    log_filename = f'logs/ai_manufacturing_{current_date}.log'

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("AI Manufacturing Content Generator started")
    logger.info("=" * 60)
    return logger

logger = setup_logging()

# ── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
F7I_PUBLIC = os.path.join(PROJECT_ROOT, 'f7i-public')

CONTENT_OUTPUT = os.path.join(
    F7I_PUBLIC, 'app', 'learning', 'state-of-ai-in-manufacturing', '_data', 'content.json'
)
IMAGE_OUTPUT_DIR = os.path.join(F7I_PUBLIC, 'public', 'images', 'ai-manufacturing')

# ── Gemini Client Setup ─────────────────────────────────────────────────────

import google.generativeai as genai  # type: ignore

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))  # type: ignore
gemini_model = genai.GenerativeModel('gemini-3-pro-preview')  # type: ignore

# Image generation client (newer SDK)
gemini_image_client = None
try:
    from google import genai as genai_new  # type: ignore
    gemini_image_client = genai_new.Client(api_key=os.getenv('GEMINI_API_KEY'))  # type: ignore
except ImportError:
    logger.warning("google.genai not available - image generation disabled")


# ── Gemini API Helpers ───────────────────────────────────────────────────────

def call_gemini(prompt: str, temperature: float = 0.3, max_tokens: int = 8000, timeout: int = 180) -> Optional[str]:
    """Call Gemini with retry logic for rate limiting and timeouts."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = gemini_model.generate_content(  # type: ignore
                prompt,
                generation_config=genai.types.GenerationConfig(  # type: ignore
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
                request_options={"timeout": timeout}
            )
            return response.text  # type: ignore
        except Exception as e:
            error_str = str(e).lower()
            is_retryable = any(kw in error_str for kw in ["429", "quota", "504", "deadline", "timeout"])
            if is_retryable and attempt < max_retries - 1:
                wait_time = min(30 * (attempt + 1), 90)
                logger.warning(f"Retryable error ({e}), waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                logger.error(f"Gemini API error: {e}")
                return None
    return None


def generate_image(prompt: str, filename: str) -> Optional[str]:
    """Generate an image using Gemini 3 Pro Image Preview."""
    if gemini_image_client is None:
        logger.error("Image client not available")
        return None

    try:
        from google import genai as genai_new  # type: ignore
    except ImportError:
        return None

    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Generating image: {filename} (attempt {attempt + 1})")
            response = gemini_image_client.models.generate_content(  # type: ignore
                model="gemini-3-pro-image-preview",
                contents=prompt,
                config=genai_new.types.GenerateContentConfig(  # type: ignore
                    response_modalities=['IMAGE'],
                    automatic_function_calling=genai_new.types.AutomaticFunctionCallingConfig(disable=True),  # type: ignore
                ),
            )

            if response.candidates and len(response.candidates) > 0:
                content = response.candidates[0].content
                if content and content.parts:
                    for part in content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.data:
                            os.makedirs(IMAGE_OUTPUT_DIR, exist_ok=True)
                            filepath = os.path.join(IMAGE_OUTPUT_DIR, filename)
                            image_bytes = part.inline_data.data if isinstance(part.inline_data.data, bytes) else base64.b64decode(part.inline_data.data)
                            with open(filepath, 'wb') as f:
                                f.write(image_bytes)
                            logger.info(f"Image saved: {filepath}")
                            return f"/images/ai-manufacturing/{filename}"

            logger.error(f"No image data in response for {filename}")
            return None

        except Exception as e:
            error_str = str(e).lower()
            is_retryable = any(kw in error_str for kw in ["429", "quota", "504", "deadline", "timeout"])
            if is_retryable and attempt < max_retries - 1:
                wait_time = min(30 * (attempt + 1), 60)
                logger.warning(f"Retryable image error ({e}), waiting {wait_time}s")
                time.sleep(wait_time)
            else:
                logger.error(f"Image generation error for {filename}: {e}")
                return None
    return None


# ── Section Content Generators ───────────────────────────────────────────────

SECTION_CONFIGS: Dict[str, Dict[str, Any]] = {
    "hero": {
        "prompt": """You are a manufacturing industry analyst writing a data-driven report on AI in manufacturing for 2026.

Generate the HERO section for "The State of AI in Manufacturing 2026". This is targeted at a note/security printing manufacturer.

Output ONLY valid JSON (no markdown fences) in this exact format:
{
  "title": "The State of AI in Manufacturing",
  "year": "2026",
  "subtitle": "A concise subtitle (15-20 words) about AI reshaping the manufacturing value chain",
  "stats": [
    {"value": <number>, "suffix": "%", "prefix": "", "label": "short description of what this stat measures"},
    {"value": <number>, "suffix": "B", "prefix": "$", "label": "short description"},
    {"value": <number>, "suffix": "%", "label": "short description"}
  ]
}

The 3 stats should be compelling, current 2026 figures about:
1. AI adoption rate in manufacturing
2. Market size of AI in manufacturing
3. Operational improvement metric (downtime reduction, efficiency gain, etc.)

Use real, verifiable 2026 statistics where possible. Be specific, not generic.""",
    },

    "landscape": {
        "prompt": """You are a manufacturing industry analyst. Write the LANDSCAPE overview section for "The State of AI in Manufacturing 2026".

This is for an interactive microsite aimed at a note/security printing manufacturer.

Output ONLY valid JSON (no markdown fences):
{
  "headline": "A compelling 6-8 word headline about where AI stands in manufacturing",
  "paragraphs": [
    "First paragraph (80-100 words): The big picture — AI has moved from pilots to production in manufacturing. Specific adoption numbers, which sectors lead.",
    "Second paragraph (80-100 words): What's changed — the shift from narrow automation to intelligent systems that learn and adapt. The convergence of cheaper sensors, better models, and edge compute.",
    "Third paragraph (80-100 words): The value chain perspective — AI is no longer just for predictive maintenance. It spans procurement, production, quality, logistics, and workforce. The shift to whole-chain intelligence."
  ],
  "pullQuote": "A striking one-sentence quote or insight about AI in manufacturing 2026"
}""",
    },

    "physical": {
        "prompt": """Write content about the PHYSICAL LAYER of AI in manufacturing (sensors, computer vision, edge computing, IoT) for 2026.

Include specific relevance to print manufacturing: ink viscosity sensors, substrate defect detection cameras, color consistency monitoring, environmental sensors for humidity/temperature control in printing.

Output ONLY valid JSON (no markdown fences):
{
  "title": "The Physical Layer",
  "subtitle": "Sensors, Computer Vision & Edge Intelligence",
  "description": "2-3 paragraphs (250-300 words total) covering: sensor proliferation and cost reduction, computer vision for quality inspection, edge computing for real-time decisions, IoT mesh networks on the factory floor. Include specific examples for print manufacturing.",
  "keyPoints": [
    {"title": "short title", "detail": "1-2 sentence explanation with specific example or stat"},
    {"title": "short title", "detail": "..."},
    {"title": "short title", "detail": "..."},
    {"title": "short title", "detail": "..."}
  ],
  "stats": [
    {"value": <number>, "suffix": "%", "label": "relevant stat about physical layer AI"},
    {"value": <number>, "suffix": "x", "label": "another relevant stat"}
  ],
  "printRelevance": "A 2-3 sentence note on why this layer matters specifically for note/security printing operations"
}""",
    },

    "robotics": {
        "prompt": """Write content about the ROBOTICS & AUTOMATION LAYER of AI in manufacturing for 2026.

CRITICAL TOPICS TO COVER:
1. Reinforcement learning for "copycat" robots — robots trained by human demonstration that can perform MULTIPLE tasks, easily reconfigured (vs. traditional single-purpose robots)
2. World models and simulation — digital rehearsal of robot behavior before physical deployment, sim-to-real transfer
3. Collaborative robots (cobots) working alongside humans
4. The paradigm shift from hard-coded, single-task automation to adaptable, multi-task robotic systems

Output ONLY valid JSON (no markdown fences):
{
  "title": "The Robotics Layer",
  "subtitle": "Adaptive Machines That Learn, Simulate & Collaborate",
  "description": "3-4 paragraphs (350-400 words total) covering: RL-trained copycat robots that learn from demonstration, world models enabling simulation before deployment, cobots, and the shift from rigid to flexible automation. Use specific vendor/research examples where possible (e.g. Google DeepMind robotics, NVIDIA Isaac, Covariant, Figure AI).",
  "keyPoints": [
    {"title": "Copycat Robots", "detail": "How RL enables robots to learn from human demonstration and handle multiple tasks — specific examples and what this means for reconfigurability"},
    {"title": "World Models & Simulation", "detail": "How digital twins and world models let manufacturers rehearse robot behavior virtually before deploying physically"},
    {"title": "Collaborative Intelligence", "detail": "How cobots with AI perception work alongside human operators safely"},
    {"title": "Multi-Task Flexibility", "detail": "The economics and operational advantage of robots that can be reconfigured in hours, not months"}
  ],
  "stats": [
    {"value": <number>, "suffix": "%", "label": "stat about robotics AI adoption or improvement"},
    {"value": <number>, "suffix": "x", "label": "another relevant stat"}
  ],
  "printRelevance": "2-3 sentences on how adaptive robotics applies to print manufacturing — material handling, press changeovers, packaging, quality sampling"
}""",
    },

    "integration": {
        "prompt": """Write content about the INTEGRATION & MIDDLEWARE LAYER of AI in manufacturing for 2026.

Cover: MES/ERP integration, digital twins, data platforms bridging OT and IT, unified data fabrics, how middleware enables AI insights to flow between systems.

Output ONLY valid JSON (no markdown fences):
{
  "title": "The Integration Layer",
  "subtitle": "Connecting OT, IT & the Intelligent Data Fabric",
  "description": "2-3 paragraphs (250-300 words total) on: the OT/IT convergence challenge, how data platforms and middleware create unified views, digital twins for process optimization, the role of APIs and event-driven architectures in manufacturing.",
  "keyPoints": [
    {"title": "short title", "detail": "1-2 sentence explanation"},
    {"title": "short title", "detail": "..."},
    {"title": "short title", "detail": "..."},
    {"title": "short title", "detail": "..."}
  ],
  "stats": [
    {"value": <number>, "suffix": "%", "label": "stat about integration/middleware"},
    {"value": <number>, "suffix": "x", "label": "another stat"}
  ],
  "printRelevance": "2-3 sentences on integration challenges specific to print manufacturing"
}""",
    },

    "agents": {
        "prompt": """Write content about the AI AGENTS & INTELLIGENCE LAYER in manufacturing for 2026.

Cover: LLM-powered operational agents, autonomous decision-making systems, multi-agent orchestration, natural language interfaces for shop floor queries, AI copilots for engineers and operators.

Output ONLY valid JSON (no markdown fences):
{
  "title": "The Agents Layer",
  "subtitle": "Autonomous Decision-Making & LLM-Powered Operations",
  "description": "2-3 paragraphs (250-300 words total) on: how LLM-based agents are being deployed in manufacturing, multi-agent systems coordinating decisions, natural language interfaces replacing complex dashboards, the spectrum from copilot to autonomous agent.",
  "keyPoints": [
    {"title": "short title", "detail": "1-2 sentence explanation"},
    {"title": "short title", "detail": "..."},
    {"title": "short title", "detail": "..."},
    {"title": "short title", "detail": "..."}
  ],
  "stats": [
    {"value": <number>, "suffix": "%", "label": "stat about AI agents in manufacturing"},
    {"value": <number>, "suffix": "x", "label": "another stat"}
  ],
  "printRelevance": "2-3 sentences on how AI agents could transform print manufacturing operations"
}""",
    },

    "useCases": {
        "prompt": """Generate 6 compelling AI USE CASES across the manufacturing value chain for 2026. These should span the ENTIRE chain, not just maintenance.

Output ONLY valid JSON (no markdown fences):
{
  "headline": "AI Across the Value Chain",
  "subtitle": "From raw materials to finished goods, intelligence at every step",
  "cases": [
    {
      "id": "procurement",
      "title": "Smart Procurement & Supply Chain",
      "description": "3-4 sentences on how AI optimizes procurement, demand forecasting, supplier risk assessment",
      "impact": "A specific metric or outcome",
      "icon": "supply"
    },
    {
      "id": "quality",
      "title": "Quality Control & Inspection",
      "description": "...",
      "impact": "...",
      "icon": "quality"
    },
    {
      "id": "maintenance",
      "title": "Predictive Maintenance",
      "description": "...",
      "impact": "...",
      "icon": "maintenance"
    },
    {
      "id": "production",
      "title": "Production Optimization",
      "description": "...",
      "impact": "...",
      "icon": "production"
    },
    {
      "id": "logistics",
      "title": "Logistics & Warehousing",
      "description": "...",
      "impact": "...",
      "icon": "logistics"
    },
    {
      "id": "energy",
      "title": "Energy & Sustainability",
      "description": "...",
      "impact": "...",
      "icon": "energy"
    }
  ]
}""",
    },

    "people": {
        "prompt": """Describe how AI changes the daily work of 5 different ROLES in a manufacturing plant in 2026.

Output ONLY valid JSON (no markdown fences):
{
  "headline": "The People Behind the Machines",
  "subtitle": "How AI augments every role on the factory floor",
  "roles": [
    {
      "title": "Plant Manager",
      "before": "1-2 sentences describing their work BEFORE AI",
      "after": "1-2 sentences describing their work WITH AI in 2026",
      "keyChange": "One sentence capturing the biggest shift"
    },
    {
      "title": "Maintenance Technician",
      "before": "...",
      "after": "...",
      "keyChange": "..."
    },
    {
      "title": "Quality Engineer",
      "before": "...",
      "after": "...",
      "keyChange": "..."
    },
    {
      "title": "Supply Chain Analyst",
      "before": "...",
      "after": "...",
      "keyChange": "..."
    },
    {
      "title": "Machine Operator",
      "before": "...",
      "after": "...",
      "keyChange": "..."
    }
  ]
}""",
    },

    "printManufacturing": {
        "prompt": """Write a detailed section on how AI specifically applies to NOTE PRINTING / SECURITY PRINTING manufacturing in 2026.

This is the key section — the audience is a prospect who does note printing. Make it specific and insightful.

Cover: color consistency and spectral analysis, substrate defect detection, press optimization, supply chain for specialty inks and security papers, anti-counterfeiting AI, quality control for micro-printing and security features.

Output ONLY valid JSON (no markdown fences):
{
  "headline": "AI in Print Manufacturing",
  "subtitle": "Precision, Security & Intelligence for Modern Print Operations",
  "introduction": "2-3 sentences introducing why print manufacturing is uniquely positioned to benefit from AI",
  "applications": [
    {
      "title": "Color Consistency & Spectral Analysis",
      "description": "3-4 sentences on AI-driven color management, spectrophotometry, closed-loop color control",
      "impact": "Specific metric or outcome"
    },
    {
      "title": "Substrate & Defect Detection",
      "description": "3-4 sentences on computer vision for detecting printing defects, substrate flaws, registration errors",
      "impact": "..."
    },
    {
      "title": "Press Optimization & Predictive Setup",
      "description": "3-4 sentences on AI optimizing press parameters, reducing makeready time, predictive press maintenance",
      "impact": "..."
    },
    {
      "title": "Supply Chain Intelligence",
      "description": "3-4 sentences on managing specialty ink and paper procurement, demand forecasting for print runs",
      "impact": "..."
    }
  ],
  "closingInsight": "A compelling 2-sentence insight about the future of AI in print manufacturing"
}""",
    },

    "lookingAhead": {
        "prompt": """Write the CLOSING / LOOKING AHEAD section for "The State of AI in Manufacturing 2026".

This should inspire action and start a conversation, especially for a note printing manufacturer evaluating AI.

Output ONLY valid JSON (no markdown fences):
{
  "headline": "What Comes Next",
  "paragraphs": [
    "First paragraph (60-80 words): The trajectory — where manufacturing AI is heading in the next 2-3 years",
    "Second paragraph (60-80 words): The imperative — why waiting is increasingly costly, the competitive gap widening"
  ],
  "callToAction": {
    "headline": "A compelling 6-8 word CTA headline",
    "description": "1-2 sentences inviting the reader to explore how these technologies apply to their operations",
    "buttonText": "Short CTA button text (3-5 words)"
  },
  "keyTakeaways": [
    "Takeaway 1 — one sentence",
    "Takeaway 2 — one sentence",
    "Takeaway 3 — one sentence"
  ]
}""",
    },
}


IMAGE_PROMPTS: Dict[str, Dict[str, str]] = {
    "physical-layer.jpg": {
        "prompt": "Professional photograph of a modern smart factory floor. Close-up of industrial IoT sensors and high-resolution machine vision cameras mounted above a production line, inspecting products at speed. LED status indicators glowing blue and green. Shallow depth of field focusing on the sensor array with a blurred factory background. Dramatic industrial lighting, moody and cinematic. Real-world manufacturing photography, not an illustration. No text overlays.",
    },
    "robotics-layer.jpg": {
        "prompt": "Professional photograph of a collaborative robot (cobot) arm working alongside a human technician on a factory floor. The robot is performing a precise assembly or pick-and-place task. The technician is nearby programming or monitoring via a tablet. Modern industrial environment with clean lighting. The photo should feel real and documentary, showing actual human-robot collaboration in manufacturing. No text overlays.",
    },
    "integration-layer.jpg": {
        "prompt": "Professional photograph of a modern factory control room or operations center. Multiple large screens displaying real-time dashboards, production data, SCADA interfaces, and digital twin visualizations. An engineer or operator is analyzing the data. Dark room illuminated by the glow of the screens. Feels high-tech and data-driven. Real-world industrial photography, not an illustration. No text overlays.",
    },
    "agents-layer.jpg": {
        "prompt": "Professional photograph of a plant manager or engineer using a tablet or laptop on a factory floor, with AI-powered analytics and natural language interface visible on screen. The factory background is slightly blurred showing heavy machinery and production equipment. The focus is on the person interacting with intelligent software. Natural industrial lighting with a modern, technological feel. No text overlays.",
    },
    "people-plant-manager.jpg": {
        "prompt": "Professional environmental portrait photograph of a confident plant manager in a modern manufacturing facility. The person is wearing a hard hat and high-visibility vest, standing in front of a large production floor visible through a glass window behind them. They are holding a tablet showing dashboard data. Natural warm industrial lighting. The photo is cropped as a medium close-up, waist up. Photorealistic, documentary style. Diverse subject. No text overlays.",
    },
    "people-maintenance-tech.jpg": {
        "prompt": "Professional environmental portrait photograph of a skilled maintenance technician working on industrial equipment in a factory. They are wearing safety glasses and work gloves, using a diagnostic tool or vibration sensor on a large machine. Dramatic side lighting from overhead industrial fixtures. Shallow depth of field with the technician sharp and background machinery softly blurred. Medium close-up composition. Photorealistic, documentary manufacturing photography. Diverse subject. No text overlays.",
    },
    "people-quality-engineer.jpg": {
        "prompt": "Professional environmental portrait photograph of a quality engineer in a clean, well-lit manufacturing lab or inspection area. They are wearing a lab coat and examining a product sample under a high-resolution camera or microscope setup with a monitor showing inspection data behind them. Cool, precise lighting. Photorealistic, documentary style. Medium close-up composition, waist up. Diverse subject. No text overlays.",
    },
    "people-supply-chain.jpg": {
        "prompt": "Professional environmental portrait photograph of a supply chain analyst in a modern office space within a manufacturing facility, with a warehouse or loading dock visible through windows behind them. Multiple monitors show supply chain dashboards, demand forecast charts, and logistics maps. The person is focused, analytical, working at their workstation. Cool blue-toned office lighting contrasting with warm warehouse light through windows. Medium close-up. Photorealistic. Diverse subject. No text overlays.",
    },
    "people-machine-operator.jpg": {
        "prompt": "Professional environmental portrait photograph of a skilled machine operator at the controls of a CNC machine or printing press in a modern factory. They are wearing safety equipment and focused on the control panel or touchscreen interface. The machine is partially visible, showing its industrial scale. Dramatic lighting from the machine's operating lights. Medium close-up showing hands on controls and face. Photorealistic, documentary manufacturing photography. Diverse subject. No text overlays.",
    },
}


# ── Value Chain (static, not LLM-generated) ──────────────────────────────────

VALUE_CHAIN_DATA = {
    "stages": [
        {"id": "supply", "label": "Supply Chain", "description": "Demand forecasting, supplier risk, procurement optimization"},
        {"id": "production", "label": "Production", "description": "Process control, scheduling, yield optimization"},
        {"id": "quality", "label": "Quality", "description": "Vision inspection, SPC analytics, defect prediction"},
        {"id": "maintenance", "label": "Maintenance", "description": "Predictive analytics, condition monitoring, work orders"},
        {"id": "logistics", "label": "Logistics", "description": "Warehouse automation, route optimization, inventory"},
    ]
}


# ── Main Pipeline ────────────────────────────────────────────────────────────

def generate_section_content(section_id: str) -> Optional[Dict[str, Any]]:
    """Generate content for a single section via Gemini."""
    config = SECTION_CONFIGS.get(section_id)
    if not config:
        logger.error(f"Unknown section: {section_id}")
        return None

    logger.info(f"Generating content for section: {section_id}")
    start = time.time()

    response_text = call_gemini(config["prompt"], temperature=0.35, max_tokens=4000)
    if not response_text:
        logger.error(f"No response for section: {section_id}")
        return None

    # Clean up response - strip markdown fences if present
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        # Remove opening fence
        first_newline = cleaned.index('\n')
        cleaned = cleaned[first_newline + 1:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    try:
        data = json.loads(cleaned)
        elapsed = time.time() - start
        logger.info(f"Section {section_id} generated in {elapsed:.1f}s")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error for {section_id}: {e}")
        logger.error(f"Response preview: {cleaned[:500]}")
        return None


def generate_all_content(sections: Optional[List[str]] = None) -> Dict[str, Any]:
    """Generate content for all (or specified) sections."""
    content: Dict[str, Any] = {}

    target_sections = sections or list(SECTION_CONFIGS.keys())

    for section_id in target_sections:
        data = generate_section_content(section_id)
        if data:
            content[section_id] = data
        else:
            logger.warning(f"Failed to generate {section_id}, using fallback")
            content[section_id] = {"error": f"Failed to generate {section_id}"}

        # Rate limiting between sections
        time.sleep(2)

    # Add static value chain data
    content["valueChain"] = VALUE_CHAIN_DATA

    return content


def generate_all_images(image_ids: Optional[List[str]] = None) -> Dict[str, Optional[str]]:
    """Generate all (or specified) images."""
    results: Dict[str, Optional[str]] = {}

    targets = {k: v for k, v in IMAGE_PROMPTS.items() if image_ids is None or k in image_ids}

    for filename, config in targets.items():
        path = generate_image(config["prompt"], filename)
        results[filename] = path
        time.sleep(3)  # Rate limiting for image generation

    return results


def save_content(content: Dict[str, Any]) -> str:
    """Save content JSON to the frontend data directory."""
    os.makedirs(os.path.dirname(CONTENT_OUTPUT), exist_ok=True)

    with open(CONTENT_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(content, f, indent=2, ensure_ascii=False)

    logger.info(f"Content saved to: {CONTENT_OUTPUT}")
    return CONTENT_OUTPUT


def main():
    parser = argparse.ArgumentParser(description="Generate AI Manufacturing microsite content")
    parser.add_argument('--content-only', action='store_true', help='Generate content JSON only, skip images')
    parser.add_argument('--images-only', action='store_true', help='Generate images only, skip content')
    parser.add_argument('--section', type=str, help='Generate a specific section only (e.g. "hero", "robotics")')
    parser.add_argument('--image', type=str, help='Generate a specific image only (e.g. "physical-layer.png")')
    args = parser.parse_args()

    if not os.getenv('GEMINI_API_KEY'):
        logger.error("GEMINI_API_KEY not set in environment")
        sys.exit(1)

    print("=" * 60)
    print("  AI Manufacturing 2026 - Content Generator")
    print("=" * 60)

    if not args.images_only:
        sections = [args.section] if args.section else None
        print(f"\n📝 Generating content{f' for section: {args.section}' if args.section else ' for all sections'}...")
        content = generate_all_content(sections)

        # If generating a single section, merge with existing content
        if args.section and os.path.exists(CONTENT_OUTPUT):
            with open(CONTENT_OUTPUT, 'r', encoding='utf-8') as f:
                existing = json.load(f)
            existing.update(content)
            content = existing

        filepath = save_content(content)
        print(f"✅ Content saved to: {filepath}")

    if not args.content_only:
        image_ids = [args.image] if args.image else None
        print(f"\n🎨 Generating images{f': {args.image}' if args.image else ' for all sections'}...")
        results = generate_all_images(image_ids)

        generated = sum(1 for v in results.values() if v)
        print(f"✅ Generated {generated}/{len(results)} images")

    print("\n🎉 Done!")


if __name__ == "__main__":
    main()
