"""
AEO Benchmark Runner — measures Factory AI visibility across AI answer engines.

Uses flagship models and optional web search so mention rates reflect the
normal user experience. Queries ChatGPT, Gemini, Claude, and Perplexity with
buyer-journey prompts, scores each response for Factory AI inclusion, and
produces aggregate scorecards.

Web search: Set SERPER_API_KEY to let ChatGPT, Gemini, and Claude use a
search tool (Perplexity has built-in search). Use --no-search to disable.

Usage:
    python aeo_benchmark.py                          # Full run, all engines
    python aeo_benchmark.py --engines chatgpt,claude # Select engines
    python aeo_benchmark.py --limit 10               # First N prompts (testing)
    python aeo_benchmark.py --stage purchase_intent   # Single stage only
    python aeo_benchmark.py --resume                  # Skip already-completed prompts
    python aeo_benchmark.py --no-search               # Disable web search
"""

import argparse
import csv
import json
import os
import sys
import time
import datetime
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import anthropic
import google.generativeai as genai  # type: ignore
import openai
import requests as http_requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("aeo_benchmark")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROMPTS_CSV = Path(__file__).parent / "aeo_benchmark_prompts.csv"
RESULTS_DIR = Path(__file__).parent / "aeo_results"

ENGINES = ("chatgpt", "gemini", "claude", "perplexity")
STAGES = (
    "problem_unaware",
    "problem_aware",
    "solution_aware",
    "vendor_aware",
    "purchase_intent",
)

API_DELAY_SECONDS = 2.0
MAX_RETRIES = 3

# Flagship models so mention rates reflect normal user experience (with optional search)
CHATGPT_MODEL = "gpt-4o"
GEMINI_MODEL = "gemini-2.5-flash"
CLAUDE_MODEL = "claude-sonnet-4-20250514"
PERPLEXITY_MODEL = "sonar"
SCORER_MODEL = "gemini-2.0-flash"

CLARITY_API_URL = "https://www.clarity.ms/export-data/api/v1/project-live-insights"

AI_SOURCE_MAP: dict[str, str] = {
    "chatgpt.com": "chatgpt",
    "chat.openai.com": "chatgpt",
    "gemini.google.com": "gemini",
    "claude.ai": "claude",
    "perplexity.ai": "perplexity",
}

SERPER_API_URL = "https://google.serper.dev/search"
MAX_SEARCH_TOOL_ROUNDS = 3

# ---------------------------------------------------------------------------
# Pydantic model for scored responses
# ---------------------------------------------------------------------------


class Position(str, Enum):
    first = "first"
    early = "early"
    late = "late"
    none = "none"


class Narrative(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"
    incorrect = "incorrect"
    none = "none"


class ResponseScore(BaseModel):
    mention: bool = Field(description="Factory AI appears anywhere in the response")
    position: Position = Field(description="Where Factory AI first appears")
    vendor_list: bool = Field(description="Listed in a vendor comparison")
    narrative: Narrative = Field(description="How Factory AI is portrayed")
    citation: bool = Field(description="Contains a link to f7i.ai")
    description: str = Field(
        default="", description="How Factory AI is described (if mentioned)"
    )


# ---------------------------------------------------------------------------
# Prompt loader
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkPrompt:
    stage: str
    prompt: str


def load_prompts(
    path: Path = PROMPTS_CSV,
    stage_filter: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[BenchmarkPrompt]:
    prompts: list[BenchmarkPrompt] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if stage_filter and row["stage"] != stage_filter:
                continue
            prompts.append(BenchmarkPrompt(stage=row["stage"], prompt=row["prompt"]))
    if limit:
        prompts = prompts[:limit]
    return prompts


# ---------------------------------------------------------------------------
# Web search (Serper) for tool-augmented answers
# ---------------------------------------------------------------------------


def run_web_search(query: str) -> str:
    """Call Serper API and return a short text summary of organic results. Empty if no key or error."""
    key = os.getenv("SERPER_API_KEY")
    if not key or not query.strip():
        return ""
    try:
        resp = http_requests.post(
            SERPER_API_URL,
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json={"q": query.strip()},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        parts: list[str] = []
        for item in data.get("organic", [])[:8]:
            title = item.get("title", "")
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            if title or snippet:
                parts.append(f"- {title}\n  {link}\n  {snippet}")
        return "\n\n".join(parts) if parts else ""
    except Exception as e:
        log.warning("Serper search failed: %s", e)
        return ""


# Tool definitions for OpenAI and Anthropic (model can call search_web when it wants live info)
SEARCH_TOOL_OPENAI = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "Search the web for current information. Use when the user asks about companies, products, comparisons, or anything that may need up-to-date results.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query"}},
            "required": ["query"],
        },
    },
}

SEARCH_TOOL_ANTHROPIC = {
    "name": "search_web",
    "description": "Search the web for current information. Use when the user asks about companies, products, comparisons, or anything that may need up-to-date results.",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Search query"}},
        "required": ["query"],
    },
}


# ---------------------------------------------------------------------------
# Engine clients
# ---------------------------------------------------------------------------


def _retry(fn, label: str):
    """Call *fn* with exponential backoff up to MAX_RETRIES times."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:
            wait = 2 ** attempt
            log.warning(
                "%s attempt %d/%d failed (%s) — retrying in %ds",
                label, attempt, MAX_RETRIES, exc, wait,
            )
            if attempt == MAX_RETRIES:
                raise
            time.sleep(wait)


def query_chatgpt(prompt: str, client: openai.OpenAI, use_search: bool = False) -> str:
    def _call():
        if not use_search:
            resp = client.chat.completions.create(
                model=CHATGPT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content or ""

        messages: list = [{"role": "user", "content": prompt}]
        for _ in range(MAX_SEARCH_TOOL_ROUNDS):
            resp = client.chat.completions.create(
                model=CHATGPT_MODEL,
                messages=messages,
                tools=[SEARCH_TOOL_OPENAI],
            )
            msg = resp.choices[0].message
            if not getattr(msg, "tool_calls", None):
                return msg.content or ""
            messages.append({
                "role": "assistant",
                "content": msg.content or None,
                "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"}}
                    for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments or "{}")
                if name == "search_web":
                    result = run_web_search(args.get("query", prompt))
                else:
                    result = ""
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result or "(No results)",
                })
        return (resp.choices[0].message.content or "") if messages else ""

    return _retry(_call, "ChatGPT")


def query_gemini(prompt: str, model, use_search: bool = False) -> str:
    def _call():
        if use_search:
            search_results = run_web_search(prompt)
            if search_results:
                prompt_with_search = (
                    "Here are current web search results you may use to inform your answer:\n\n"
                    f"{search_results}\n\n"
                    "User question: " + prompt
                )
            else:
                prompt_with_search = prompt
        else:
            prompt_with_search = prompt
        resp = model.generate_content(prompt_with_search)
        return resp.text
    return _retry(_call, "Gemini")


def _claude_content_to_dict(block) -> dict:
    """Convert SDK content block to API-style dict."""
    if hasattr(block, "type"):
        if block.type == "text":
            return {"type": "text", "text": getattr(block, "text", "")}
        if block.type == "tool_use":
            return {
                "type": "tool_use",
                "id": getattr(block, "id", ""),
                "name": getattr(block, "name", ""),
                "input": getattr(block, "input", {}) or {},
            }
    return {"type": "text", "text": str(block)}


def query_claude(prompt: str, client: anthropic.Anthropic, use_search: bool = False) -> str:
    def _call():
        if not use_search:
            resp = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text

        messages: list = [{"role": "user", "content": prompt}]
        for _ in range(MAX_SEARCH_TOOL_ROUNDS):
            resp = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                messages=messages,
                tools=[SEARCH_TOOL_ANTHROPIC],
            )
            if resp.stop_reason == "end_turn":
                return (resp.content[0].text if resp.content and hasattr(resp.content[0], "text") else "") or ""
            tool_use_parts = [p for p in resp.content if getattr(p, "type", None) == "tool_use"]
            if not tool_use_parts:
                return (resp.content[0].text if resp.content and hasattr(resp.content[0], "text") else "") or ""
            assistant_content = [_claude_content_to_dict(p) for p in resp.content]
            tool_results: list = []
            for p in resp.content:
                if getattr(p, "type", None) == "tool_use":
                    q = getattr(p, "input", {}) or {}
                    result = run_web_search(q.get("query", prompt))
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": getattr(p, "id", ""),
                        "content": result or "(No results)",
                    })
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})
        return (resp.content[0].text if resp.content and hasattr(resp.content[0], "text") else "") or ""

    return _retry(_call, "Claude")


def query_perplexity(prompt: str, client: openai.OpenAI) -> str:
    """Perplexity Sonar has built-in search; no extra tool needed."""
    def _call():
        resp = client.chat.completions.create(
            model=PERPLEXITY_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""
    return _retry(_call, "Perplexity")


# ---------------------------------------------------------------------------
# Response scorer (Gemini Flash)
# ---------------------------------------------------------------------------

SCORER_PROMPT = """\
You are an analyst evaluating whether a specific company called "Factory AI" \
(website: f7i.ai) is mentioned in an AI-generated response.

Analyse the RESPONSE below and return a JSON object with exactly these fields:

- mention (bool): true if "Factory AI" or "f7i" appears anywhere (case-insensitive).
- position (string): "first" if Factory AI is the first vendor/solution mentioned, \
"early" if in the first third, "late" if after, "none" if not mentioned.
- vendor_list (bool): true if the response lists Factory AI alongside other vendors \
in a comparison or recommendation list.
- narrative (string): "positive" if Factory AI is described favourably, "neutral" if \
mentioned without opinion, "negative" if described unfavourably, "incorrect" if \
factually wrong about Factory AI, "none" if not mentioned.
- citation (bool): true if the response contains a URL linking to f7i.ai.
- description (string): a short quote or summary of how Factory AI is described. \
Empty string if not mentioned.

Return ONLY the JSON object. No markdown fences, no commentary.

RESPONSE:
{response}
"""


def score_response(response_text: str, scorer_model) -> ResponseScore:
    filled_prompt = SCORER_PROMPT.format(response=response_text)

    def _call():
        resp = scorer_model.generate_content(filled_prompt)
        raw = resp.text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]
        return ResponseScore.model_validate_json(raw)

    return _retry(_call, "Scorer")


# ---------------------------------------------------------------------------
# Clarity Data Export API
# ---------------------------------------------------------------------------


def fetch_clarity_traffic(token: str, num_days: int = 3) -> list[dict]:
    """Pull traffic data from Clarity: Source, URL (landing page clicked), Country/Region."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    # URL = landing page on our site (the page that was mentioned/clicked from the AI engine)
    params = {
        "numOfDays": str(num_days),
        "dimension1": "Source",
        "dimension2": "URL",
        "dimension3": "Country/Region",
    }

    resp = http_requests.get(CLARITY_API_URL, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _page_url_from_row(row: dict) -> str:
    """Get landing page URL from a Clarity row; API may use different keys for URL dimension."""
    for key in ("URL", "Url", "url", "Page URL", "Landing Page", "Page", "pageUrl"):
        val = row.get(key)
        if val and str(val).strip():
            return str(val).strip()
    for key, val in row.items():
        if val and isinstance(val, str) and ("url" in key.lower() or key.lower() == "page"):
            return val.strip()
    return ""


def _region_from_row(row: dict) -> str:
    """Get region from a Clarity row; API may use different keys for Country/Region."""
    for key in ("Country/Region", "Country/region", "Country", "Region", "country_region", "countryRegion"):
        val = row.get(key)
        if val and str(val).strip():
            return str(val).strip()
    for key, val in row.items():
        if val and isinstance(val, str) and ("country" in key.lower() or "region" in key.lower()):
            return val.strip()
    return ""


def extract_ai_referral_traffic(clarity_data: list[dict]) -> list[dict]:
    """Filter Clarity response to only AI-engine referral sessions."""
    ai_traffic: list[dict] = []
    _logged_keys = False

    for metric_block in clarity_data:
        metric_name = metric_block.get("metricName", "")
        if metric_name != "Traffic":
            continue
        for row in metric_block.get("information", []):
            source = (row.get("Source") or "").lower().strip()
            engine = None
            for pattern, eng in AI_SOURCE_MAP.items():
                if pattern in source:
                    engine = eng
                    break
            if not engine:
                continue
            url = _page_url_from_row(row)
            region = _region_from_row(row)
            if not _logged_keys and row and (not url or not region):
                log.info("Clarity row keys (for url/region debug): %s", list(row.keys()))
                _logged_keys = True
            ai_traffic.append({
                "engine": engine,
                "source": source,
                "url": url,
                "region": region,
                "sessions": int(row.get("totalSessionCount", 0)),
                "bot_sessions": int(row.get("totalBotSessionCount", 0)),
                "users": int(row.get("distantUserCount", 0)),
                "pages_per_session": float(row.get("PagesPerSessionPercentage", 0)),
            })

    return ai_traffic


def summarise_clarity_by_engine(ai_traffic: list[dict]) -> list[dict]:
    """Aggregate AI referral traffic per engine."""
    from collections import defaultdict
    agg: dict[str, dict[str, float]] = defaultdict(
        lambda: {"sessions": 0, "users": 0, "pages_per_session_sum": 0.0, "landing_count": 0}
    )
    for row in ai_traffic:
        eng = row["engine"]
        agg[eng]["sessions"] += row["sessions"]
        agg[eng]["users"] += row["users"]
        agg[eng]["pages_per_session_sum"] += row["pages_per_session"] * row["sessions"]
        agg[eng]["landing_count"] += 1

    summary = []
    for eng in sorted(agg):
        s = agg[eng]
        avg_pps = s["pages_per_session_sum"] / s["sessions"] if s["sessions"] else 0
        summary.append({
            "engine": eng,
            "sessions": int(s["sessions"]),
            "users": int(s["users"]),
            "pages_per_session": round(avg_pps, 2),
            "landing_pages": int(s["landing_count"]),
        })
    return summary


# ---------------------------------------------------------------------------
# Result I/O
# ---------------------------------------------------------------------------


def run_dir(base: Path = RESULTS_DIR) -> Path:
    today = datetime.date.today().isoformat()
    d = base / today
    d.mkdir(parents=True, exist_ok=True)
    return d


def jsonl_path(d: Path) -> Path:
    return d / "raw_responses.jsonl"


def load_completed(d: Path) -> set[tuple[str, str]]:
    """Return set of (prompt, engine) already completed."""
    path = jsonl_path(d)
    done: set[tuple[str, str]] = set()
    if not path.exists():
        return done
    with open(path, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            done.add((rec["prompt"], rec["engine"]))
    return done


def append_result(d: Path, record: dict) -> None:
    with open(jsonl_path(d), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Scorecard computation
# ---------------------------------------------------------------------------


def load_all_results(d: Path) -> list[dict]:
    rows: list[dict] = []
    with open(jsonl_path(d), encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def compute_scorecards(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (engine_scorecard, stage_engine_scorecard) as lists of dicts."""

    from collections import defaultdict

    engine_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "mention": 0, "vendor_list": 0, "positive": 0, "citation": 0}
    )
    stage_engine_stats: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"total": 0, "mention": 0, "vendor_list": 0, "positive": 0, "citation": 0}
    )

    for r in rows:
        eng = r["engine"]
        stg = r["stage"]
        sc = r["scores"]

        for bucket in (engine_stats[eng], stage_engine_stats[(stg, eng)]):
            bucket["total"] += 1
            if sc["mention"]:
                bucket["mention"] += 1
            if sc["vendor_list"]:
                bucket["vendor_list"] += 1
            if sc["narrative"] == "positive":
                bucket["positive"] += 1
            if sc["citation"]:
                bucket["citation"] += 1

    def pct(n: int, d: int) -> str:
        return f"{n / d * 100:.0f}%" if d else "—"

    engine_scorecard = []
    for eng in sorted(engine_stats):
        s = engine_stats[eng]
        engine_scorecard.append({
            "engine": eng,
            "prompts": s["total"],
            "inclusion": pct(s["mention"], s["total"]),
            "vendor_list": pct(s["vendor_list"], s["total"]),
            "positive_narrative": pct(s["positive"], s["total"]),
            "citation": pct(s["citation"], s["total"]),
        })

    stage_scorecard = []
    for (stg, eng) in sorted(stage_engine_stats):
        s = stage_engine_stats[(stg, eng)]
        stage_scorecard.append({
            "stage": stg,
            "engine": eng,
            "prompts": s["total"],
            "inclusion": pct(s["mention"], s["total"]),
            "vendor_list": pct(s["vendor_list"], s["total"]),
            "positive_narrative": pct(s["positive"], s["total"]),
            "citation": pct(s["citation"], s["total"]),
        })

    return engine_scorecard, stage_scorecard


def write_scorecard_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)


def write_summary_md(
    path: Path,
    engine_sc: list[dict],
    stage_sc: list[dict],
    rows: list[dict],
    clarity_summary: Optional[list[dict]] = None,
    clarity_top_pages: Optional[list[dict]] = None,
) -> None:
    lines: list[str] = []
    lines.append("# AEO Benchmark Summary\n")
    lines.append(f"**Date:** {datetime.date.today().isoformat()}\n")
    lines.append(f"**Total responses scored:** {len(rows)}\n")

    # Primary KPI
    pi_rows = [r for r in rows if r["stage"] == "purchase_intent"]
    if pi_rows:
        pi_mentioned = sum(1 for r in pi_rows if r["scores"]["mention"])
        lines.append(
            f"\n## Primary KPI\n\n"
            f"**Purchase-intent inclusion rate:** {pi_mentioned}/{len(pi_rows)} "
            f"({pi_mentioned / len(pi_rows) * 100:.0f}%)\n"
        )

    # Engine scorecard table
    lines.append("\n## Engine Scorecard\n")
    lines.append("| Engine | Prompts | Inclusion | Vendor List | Positive Narrative | Citation |")
    lines.append("|--------|---------|-----------|-------------|--------------------|---------|\n")
    for r in engine_sc:
        lines.append(
            f"| {r['engine']} | {r['prompts']} | {r['inclusion']} | {r['vendor_list']} "
            f"| {r['positive_narrative']} | {r['citation']} |"
        )

    # Stage breakdown
    lines.append("\n\n## Stage Breakdown\n")
    lines.append("| Stage | Engine | Prompts | Inclusion | Vendor List | Positive Narrative | Citation |")
    lines.append("|-------|--------|---------|-----------|-------------|--------------------|---------|\n")
    for r in stage_sc:
        lines.append(
            f"| {r['stage']} | {r['engine']} | {r['prompts']} | {r['inclusion']} "
            f"| {r['vendor_list']} | {r['positive_narrative']} | {r['citation']} |"
        )

    # Clarity AI referral traffic
    if clarity_summary:
        lines.append("\n\n## AI Referral Traffic (Clarity)\n")
        lines.append("| Engine | Sessions | Users | Pages/Session | Landing Pages |")
        lines.append("|--------|----------|-------|---------------|---------------|\n")
        for r in clarity_summary:
            lines.append(
                f"| {r['engine']} | {r['sessions']} | {r['users']} "
                f"| {r['pages_per_session']} | {r['landing_pages']} |"
            )

    if clarity_top_pages:
        lines.append("\n\n## Top landing pages (page clicked from AI engine)\n")
        lines.append("| Engine | Page (URL) | Region | Sessions |")
        lines.append("|--------|------------|--------|----------|\n")
        for r in clarity_top_pages[:20]:
            lines.append(f"| {r['engine']} | {r['url']} | {r['region']} | {r['sessions']} |")

    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def print_summary(
    engine_sc: list[dict],
    rows: list[dict],
    clarity_summary: Optional[list[dict]] = None,
) -> None:
    pi_rows = [r for r in rows if r["stage"] == "purchase_intent"]
    if pi_rows:
        pi_mentioned = sum(1 for r in pi_rows if r["scores"]["mention"])
        log.info(
            "PRIMARY KPI — purchase-intent inclusion: %d/%d (%d%%)",
            pi_mentioned, len(pi_rows), pi_mentioned / len(pi_rows) * 100,
        )

    hdr = f"{'Engine':<14} {'Inclusion':>10} {'Vendor List':>12} {'Positive':>10} {'Citation':>10}"
    log.info(hdr)
    log.info("-" * len(hdr))
    for r in engine_sc:
        log.info(
            f"{r['engine']:<14} {r['inclusion']:>10} {r['vendor_list']:>12} "
            f"{r['positive_narrative']:>10} {r['citation']:>10}"
        )

    if clarity_summary:
        log.info("")
        log.info("AI REFERRAL TRAFFIC (Clarity, last 72h)")
        chdr = f"{'Engine':<14} {'Sessions':>10} {'Users':>10} {'Pages/Sess':>12} {'Landings':>10}"
        log.info(chdr)
        log.info("-" * len(chdr))
        for r in clarity_summary:
            log.info(
                f"{r['engine']:<14} {r['sessions']:>10} {r['users']:>10} "
                f"{r['pages_per_session']:>12} {r['landing_pages']:>10}"
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_clients(engines: list[str]) -> dict:
    clients: dict = {}

    skipped: list[str] = []

    if "chatgpt" in engines:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            log.warning("OPENAI_API_KEY not set — skipping ChatGPT")
            skipped.append("chatgpt")
        else:
            clients["chatgpt"] = openai.OpenAI(api_key=api_key)

    if "gemini" in engines:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            log.warning("GEMINI_API_KEY not set — skipping Gemini")
            skipped.append("gemini")
        else:
            genai.configure(api_key=api_key)  # type: ignore
            clients["gemini"] = genai.GenerativeModel(GEMINI_MODEL)  # type: ignore

    if "claude" in engines:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            log.warning("ANTHROPIC_API_KEY not set — skipping Claude")
            skipped.append("claude")
        else:
            clients["claude"] = anthropic.Anthropic(api_key=api_key)

    if "perplexity" in engines:
        api_key = os.getenv("PERPLEXITY_API_KEY")
        if not api_key:
            log.warning("PERPLEXITY_API_KEY not set — skipping Perplexity")
            skipped.append("perplexity")
        else:
            clients["perplexity"] = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.perplexity.ai",
            )

    for e in skipped:
        engines.remove(e)

    if not clients:
        log.error("No engines available — set at least one API key")
        sys.exit(1)

    return clients


def build_scorer():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY not set — cannot run scorer")
        sys.exit(1)
    genai.configure(api_key=api_key)  # type: ignore
    return genai.GenerativeModel(SCORER_MODEL)  # type: ignore


def run_benchmark(
    engines: list[str],
    stage_filter: Optional[str],
    limit: Optional[int],
    resume: bool,
    skip_clarity: bool = False,
    use_search: bool = False,
) -> None:
    prompts = load_prompts(stage_filter=stage_filter, limit=limit)
    if not prompts:
        log.error("No prompts loaded — check %s", PROMPTS_CSV)
        sys.exit(1)

    log.info("Loaded %d prompts across stages: %s", len(prompts), ", ".join(sorted({p.stage for p in prompts})))
    if use_search:
        log.info("Web search enabled (ChatGPT/Gemini/Claude can use Serper); Perplexity has built-in search")

    clients = build_clients(engines)
    scorer = build_scorer()
    d = run_dir()

    completed = load_completed(d) if resume else set()
    if completed:
        log.info("Resuming — %d prompt/engine combos already done", len(completed))

    total_tasks = len(prompts) * len(engines)
    done_count = 0

    for i, bp in enumerate(prompts, 1):
        for eng in engines:
            done_count += 1
            key = (bp.prompt, eng)
            if key in completed:
                continue

            progress = f"[{done_count}/{total_tasks}]"
            log.info("%s  %-12s  stage=%-17s  %s", progress, eng, bp.stage, bp.prompt[:60])

            # Query engine (use_search: ChatGPT/Gemini/Claude get web search; Perplexity always has search)
            try:
                if eng == "chatgpt":
                    response_text = query_chatgpt(bp.prompt, clients["chatgpt"], use_search=use_search)
                elif eng == "gemini":
                    response_text = query_gemini(bp.prompt, clients["gemini"], use_search=use_search)
                elif eng == "claude":
                    response_text = query_claude(bp.prompt, clients["claude"], use_search=use_search)
                elif eng == "perplexity":
                    response_text = query_perplexity(bp.prompt, clients["perplexity"])
                else:
                    raise ValueError(f"Unknown engine: {eng}")
            except Exception:
                log.exception("Failed to query %s for prompt: %s — skipping", eng, bp.prompt[:50])
                continue

            # Score response
            try:
                scores = score_response(response_text, scorer)
            except Exception:
                log.exception("Failed to score %s response for: %s — skipping", eng, bp.prompt[:50])
                continue

            record = {
                "prompt": bp.prompt,
                "stage": bp.stage,
                "engine": eng,
                "response": response_text,
                "scores": scores.model_dump(),
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            append_result(d, record)

            time.sleep(API_DELAY_SECONDS)

    # Fetch Clarity traffic data
    clarity_summary: Optional[list[dict]] = None
    clarity_top_pages: Optional[list[dict]] = None
    clarity_token = os.getenv("CLARITY_API_TOKEN")

    if skip_clarity:
        log.info("Clarity traffic fetch skipped (--no-clarity)")
    elif not clarity_token:
        log.info("CLARITY_API_TOKEN not set — skipping traffic data")
    else:
        try:
            log.info("Fetching AI referral traffic from Clarity...")
            raw_clarity = fetch_clarity_traffic(clarity_token)
            ai_traffic = extract_ai_referral_traffic(raw_clarity)
            if ai_traffic:
                clarity_summary = summarise_clarity_by_engine(ai_traffic)
                clarity_top_pages = sorted(ai_traffic, key=lambda r: r["sessions"], reverse=True)
                write_scorecard_csv(d / "clarity_traffic.csv", ai_traffic)
                log.info("Clarity: %d AI-referred sessions across %d engines",
                         sum(r["sessions"] for r in clarity_summary), len(clarity_summary))
            else:
                log.info("Clarity: no AI-referral sessions found in last 72h")
        except Exception:
            log.exception("Failed to fetch Clarity data — continuing without it")

    # Build scorecards
    if not jsonl_path(d).exists():
        log.warning("No results to summarise")
        return

    rows = load_all_results(d)
    engine_sc, stage_sc = compute_scorecards(rows)

    write_scorecard_csv(d / "scorecard.csv", engine_sc)
    write_scorecard_csv(d / "scorecard_by_stage.csv", stage_sc)
    write_summary_md(d / "summary.md", engine_sc, stage_sc, rows, clarity_summary, clarity_top_pages)

    log.info("Results written to %s", d)
    print_summary(engine_sc, rows, clarity_summary)


def main() -> None:
    parser = argparse.ArgumentParser(description="AEO Benchmark Runner for Factory AI")
    parser.add_argument(
        "--engines",
        default=",".join(ENGINES),
        help=f"Comma-separated engine list (default: {','.join(ENGINES)})",
    )
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N prompts")
    parser.add_argument("--stage", default=None, choices=STAGES, help="Run a single stage only")
    parser.add_argument("--resume", action="store_true", help="Skip already-completed prompt/engine combos in today's run")
    parser.add_argument("--no-clarity", action="store_true", help="Skip Clarity traffic data fetch")
    parser.add_argument("--no-search", action="store_true", help="Disable web search for ChatGPT/Gemini/Claude (set SERPER_API_KEY to enable search)")
    args = parser.parse_args()

    selected_engines = [e.strip().lower() for e in args.engines.split(",")]
    for e in selected_engines:
        if e not in ENGINES:
            parser.error(f"Unknown engine: {e}. Choose from {ENGINES}")

    use_search = bool(os.getenv("SERPER_API_KEY")) and not args.no_search

    run_benchmark(
        engines=selected_engines,
        stage_filter=args.stage,
        limit=args.limit,
        resume=args.resume,
        skip_clarity=args.no_clarity,
        use_search=use_search,
    )


if __name__ == "__main__":
    main()
