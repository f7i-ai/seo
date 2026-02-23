"""
AEO Benchmark Runner — measures Factory AI visibility across AI answer engines.

Uses flagship models and optional web search so mention rates reflect the
normal user experience. Queries ChatGPT, Gemini, Claude, and Perplexity with
buyer-journey prompts, scores each response for Factory AI inclusion, and
produces aggregate scorecards.

All engines run in parallel with configurable per-engine concurrency.
Defaults: chatgpt=8, gemini=8, claude=4, perplexity=4 workers.
Rate-limit errors (429/529) trigger aggressive exponential backoff with jitter.

Web search: Enabled by default. Each engine uses its native search:
ChatGPT (web_search_preview), Gemini (Google Search grounding), Claude
(web_search tool), Perplexity (built-in). Use --no-search to disable.

Trend tracking: Each run auto-compares against the prior day and ~7 days ago
(when available), showing percentage-point deltas for engine scores and absolute
deltas for Clarity traffic. A trends.csv is written alongside the scorecard for
time-series analysis.

Usage:
    python aeo_benchmark.py                          # Full run, all engines (parallel)
    python aeo_benchmark.py --engines chatgpt,claude # Select engines
    python aeo_benchmark.py --limit 10               # First N prompts (testing)
    python aeo_benchmark.py --stage purchase_intent   # Single stage only
    python aeo_benchmark.py --resume                  # Skip already-completed prompts
    python aeo_benchmark.py --no-search               # Disable web search
    python aeo_benchmark.py --workers 2               # Override workers for all engines
    ENGINE_WORKERS_CHATGPT=10 python aeo_benchmark.py # Per-engine override via env
"""

import argparse
import csv
import json
import os
import sys
import time
import datetime
import logging
import threading
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import anthropic
from google import genai  # type: ignore
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

API_DELAY_SECONDS = 0.5  # minimum delay between requests within a worker
MAX_RETRIES = 6

# Per-engine concurrency defaults — conservative to stay within rate limits.
# Override via --workers (applies to all) or env ENGINE_WORKERS_CHATGPT=10 etc.
ENGINE_WORKERS = {
    "chatgpt": 8,     # GPT-4o: ~500 RPM on most tiers
    "gemini": 8,      # Gemini 2.5 Flash: high RPM
    "claude": 4,      # Claude Sonnet: ~50 RPM
    "perplexity": 4,  # Sonar: ~50 RPM
}
SCORER_WORKERS = 10  # Gemini 2.0 Flash for scoring: very high RPM

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

SERPER_API_URL = "https://google.serper.dev/search"  # kept for run_web_search (Clarity/other uses)

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


# ---------------------------------------------------------------------------
# Engine clients
# ---------------------------------------------------------------------------


def _is_rate_limit_error(exc: Exception) -> bool:
    """Detect rate-limit (429) or overloaded (529) errors across providers."""
    msg = str(exc).lower()
    if "429" in str(exc) or "rate" in msg or "quota" in msg or "overloaded" in msg:
        return True
    if "529" in str(exc):
        return True
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status in (429, 529):
        return True
    return False


def _retry(fn, label: str):
    """Call *fn* with jittered exponential backoff up to MAX_RETRIES times.

    Rate-limit errors (429/529) get much longer back-off than other transient errors.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt == MAX_RETRIES:
                raise
            if _is_rate_limit_error(exc):
                base = min(8 * (2 ** attempt), 120)
            else:
                base = 2 ** attempt
            jitter = random.uniform(0, base * 0.3)
            wait = base + jitter
            log.warning(
                "%s attempt %d/%d failed (%s) — retrying in %.1fs",
                label, attempt, MAX_RETRIES, exc, wait,
            )
            time.sleep(wait)


def query_chatgpt(prompt: str, client: openai.OpenAI, use_search: bool = False) -> str:
    """Query ChatGPT. When use_search=True, uses the native web_search_preview tool
    via the Responses API — no Serper dependency."""
    def _call():
        if not use_search:
            resp = client.chat.completions.create(
                model=CHATGPT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content or ""

        resp = client.responses.create(
            model=CHATGPT_MODEL,
            tools=[{"type": "web_search_preview"}],
            input=prompt,
        )
        return resp.output_text or ""

    return _retry(_call, "ChatGPT")


def query_gemini(prompt: str, client: genai.Client, model_name: str = GEMINI_MODEL, use_search: bool = False) -> str:  # type: ignore
    """Query Gemini. When use_search=True, uses native Google Search grounding
    — no Serper dependency."""
    def _call():
        config = None
        if use_search:
            config = genai.types.GenerateContentConfig(  # type: ignore
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())],  # type: ignore
            )
        resp = client.models.generate_content(model=model_name, contents=prompt, config=config)  # type: ignore
        return resp.text
    return _retry(_call, "Gemini")


def query_claude(prompt: str, client: anthropic.Anthropic, use_search: bool = False) -> str:
    """Query Claude. When use_search=True, uses Anthropic's built-in web search tool
    — no Serper dependency."""
    def _call():
        if not use_search:
            resp = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text

        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
        )
        text_parts = [
            getattr(block, "text", "")
            for block in resp.content
            if getattr(block, "type", None) == "text"
        ]
        return "\n".join(text_parts).strip()

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


def score_response(response_text: str, scorer_client: genai.Client, scorer_model_name: str = SCORER_MODEL) -> ResponseScore:  # type: ignore
    filled_prompt = SCORER_PROMPT.format(response=response_text)

    def _call():
        resp = scorer_client.models.generate_content(model=scorer_model_name, contents=filled_prompt)  # type: ignore
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


_write_lock = threading.Lock()


def append_result(d: Path, record: dict) -> None:
    with _write_lock:
        with open(jsonl_path(d), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


class _ProgressCounter:
    """Thread-safe progress tracker."""
    def __init__(self, total: int):
        self.total = total
        self._done = 0
        self._lock = threading.Lock()

    def increment(self) -> int:
        with self._lock:
            self._done += 1
            return self._done

    @property
    def done(self) -> int:
        with self._lock:
            return self._done


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


# ---------------------------------------------------------------------------
# Historical trend computation
# ---------------------------------------------------------------------------


def _find_prior_run(base: Path, today: datetime.date, days_back_max: int = 30) -> Optional[Path]:
    """Find the most recent run directory before *today*."""
    for offset in range(1, days_back_max + 1):
        candidate = base / (today - datetime.timedelta(days=offset)).isoformat()
        if candidate.exists() and jsonl_path(candidate).exists():
            return candidate
    return None


def _find_run_near(base: Path, target: datetime.date, tolerance: int = 2) -> Optional[Path]:
    """Find a run within ±tolerance days of *target*."""
    for offset in range(0, tolerance + 1):
        for sign in (0, -1, 1):
            candidate = base / (target + datetime.timedelta(days=sign * offset)).isoformat()
            if candidate.exists() and jsonl_path(candidate).exists():
                return candidate
    return None


def _pct_val(pct_str: str) -> float:
    """Parse '6%' → 6.0, '—' → 0.0."""
    if not pct_str or pct_str == "—":
        return 0.0
    return float(pct_str.replace("%", ""))


def _delta_str(current: float, previous: float) -> str:
    """Format a delta like '+3pp' or '−2pp' (percentage point change)."""
    diff = current - previous
    if diff == 0:
        return "—"
    sign = "+" if diff > 0 else "−"
    return f"{sign}{abs(diff):.0f}pp"


def _load_engine_scorecard(d: Path) -> list[dict]:
    path = d / "scorecard.csv"
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_stage_scorecard(d: Path) -> list[dict]:
    path = d / "scorecard_by_stage.csv"
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_clarity_summary(d: Path) -> list[dict]:
    path = d / "clarity_traffic.csv"
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    from collections import defaultdict
    agg: dict[str, dict[str, float]] = defaultdict(
        lambda: {"sessions": 0, "users": 0, "landing_count": 0}
    )
    for r in rows:
        eng = r.get("engine", "")
        agg[eng]["sessions"] += int(r.get("sessions", 0))
        agg[eng]["users"] += int(r.get("users", 0))
        agg[eng]["landing_count"] += 1
    return [
        {"engine": eng, "sessions": int(s["sessions"]), "users": int(s["users"]),
         "landing_pages": int(s["landing_count"])}
        for eng, s in sorted(agg.items())
    ]


def _compute_pi_rate(d: Path) -> Optional[float]:
    """Compute purchase-intent inclusion rate % from raw results."""
    path = jsonl_path(d)
    if not path.exists():
        return None
    pi_total = 0
    pi_mentioned = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("stage") == "purchase_intent":
                pi_total += 1
                if r.get("scores", {}).get("mention"):
                    pi_mentioned += 1
    if pi_total == 0:
        return None
    return pi_mentioned / pi_total * 100


@dataclass
class TrendData:
    """Holds comparison data between current and prior runs."""
    prior_date: str
    prior_label: str  # "1d ago", "7d ago", etc.

    # Engine-level deltas: {engine: {metric: delta_str}}
    engine_deltas: dict[str, dict[str, str]]

    # Clarity deltas: {engine: {metric: delta_str}}
    clarity_deltas: dict[str, dict[str, str]]

    # Primary KPI delta
    pi_current: Optional[float]
    pi_prior: Optional[float]
    pi_delta: str


def compute_trends(
    base: Path,
    today: datetime.date,
    current_engine_sc: list[dict],
    current_clarity: Optional[list[dict]],
    current_pi_rate: Optional[float],
    label: str = "prev",
    prior_dir: Optional[Path] = None,
) -> Optional[TrendData]:
    """Compare today's scores against a prior run. Returns None if no prior data."""
    if prior_dir is None:
        return None

    prior_date = prior_dir.name

    # Engine scorecard deltas
    prior_engine_sc = _load_engine_scorecard(prior_dir)
    prior_by_eng = {r["engine"]: r for r in prior_engine_sc}
    engine_deltas: dict[str, dict[str, str]] = {}
    metrics = ("inclusion", "vendor_list", "positive_narrative", "citation")
    for r in current_engine_sc:
        eng = r["engine"]
        prev = prior_by_eng.get(eng)
        if not prev:
            engine_deltas[eng] = {m: "new" for m in metrics}
            continue
        engine_deltas[eng] = {
            m: _delta_str(_pct_val(r[m]), _pct_val(prev[m]))
            for m in metrics
        }

    # Clarity deltas
    clarity_deltas: dict[str, dict[str, str]] = {}
    if current_clarity:
        prior_clarity = _load_clarity_summary(prior_dir)
        prior_cl_by_eng = {r["engine"]: r for r in prior_clarity}
        for r in current_clarity:
            eng = r["engine"]
            prev = prior_cl_by_eng.get(eng)
            if not prev:
                clarity_deltas[eng] = {"sessions": "new", "users": "new", "landing_pages": "new"}
                continue
            for m in ("sessions", "users", "landing_pages"):
                cur_v = int(r.get(m, 0))
                prev_v = int(prev.get(m, 0))
                diff = cur_v - prev_v
                if diff == 0:
                    delta = "—"
                else:
                    sign = "+" if diff > 0 else "−"
                    delta = f"{sign}{abs(diff)}"
                clarity_deltas.setdefault(eng, {})[m] = delta

    # Primary KPI delta
    prior_pi = _compute_pi_rate(prior_dir)
    pi_delta = "—"
    if current_pi_rate is not None and prior_pi is not None:
        pi_delta = _delta_str(current_pi_rate, prior_pi)

    return TrendData(
        prior_date=prior_date,
        prior_label=label,
        engine_deltas=engine_deltas,
        clarity_deltas=clarity_deltas,
        pi_current=current_pi_rate,
        pi_prior=prior_pi,
        pi_delta=pi_delta,
    )


def write_scorecard_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)


def write_trends_csv(
    path: Path,
    engine_sc: list[dict],
    clarity_summary: Optional[list[dict]],
    trends: list[TrendData],
) -> None:
    """Write a CSV capturing current values and deltas for easy time-series tracking."""
    rows_out: list[dict] = []
    today = datetime.date.today().isoformat()

    for r in engine_sc:
        eng = r["engine"]
        for m in ("inclusion", "vendor_list", "positive_narrative", "citation"):
            row: dict[str, str] = {
                "date": today,
                "source": "engine",
                "engine": eng,
                "metric": m,
                "value": r[m],
            }
            for t in trends:
                d = t.engine_deltas.get(eng, {})
                row[f"delta_{t.prior_label}"] = d.get(m, "—")
            rows_out.append(row)

    if clarity_summary:
        for r in clarity_summary:
            eng = r["engine"]
            for m in ("sessions", "users", "landing_pages"):
                row = {
                    "date": today,
                    "source": "clarity",
                    "engine": eng,
                    "metric": m,
                    "value": str(r.get(m, 0)),
                }
                for t in trends:
                    d = t.clarity_deltas.get(eng, {})
                    row[f"delta_{t.prior_label}"] = d.get(m, "—")
                rows_out.append(row)

    if rows_out:
        fieldnames = list(rows_out[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows_out)


def _trend_table_suffix(trends: list[TrendData], engine: str, metric: str) -> str:
    """Build compact delta annotations like ' (+3pp vs 1d, +5pp vs 7d)'."""
    parts = []
    for t in trends:
        d = t.engine_deltas.get(engine, {}).get(metric, "—")
        if d != "—":
            parts.append(f"{d} vs {t.prior_label}")
    return f" ({', '.join(parts)})" if parts else ""


def _clarity_trend_suffix(trends: list[TrendData], engine: str, metric: str) -> str:
    parts = []
    for t in trends:
        d = t.clarity_deltas.get(engine, {}).get(metric, "—")
        if d != "—":
            parts.append(f"{d} vs {t.prior_label}")
    return f" ({', '.join(parts)})" if parts else ""


def write_summary_md(
    path: Path,
    engine_sc: list[dict],
    stage_sc: list[dict],
    rows: list[dict],
    clarity_summary: Optional[list[dict]] = None,
    clarity_top_pages: Optional[list[dict]] = None,
    trends: Optional[list["TrendData"]] = None,
) -> None:
    if trends is None:
        trends = []

    lines: list[str] = []
    lines.append("# AEO Benchmark Summary\n")
    lines.append(f"**Date:** {datetime.date.today().isoformat()}\n")
    lines.append(f"**Total responses scored:** {len(rows)}\n")

    if trends:
        compared = ", ".join(f"{t.prior_date} ({t.prior_label})" for t in trends)
        lines.append(f"**Compared against:** {compared}\n")

    # Primary KPI
    pi_rows = [r for r in rows if r["stage"] == "purchase_intent"]
    if pi_rows:
        pi_mentioned = sum(1 for r in pi_rows if r["scores"]["mention"])
        pi_rate = pi_mentioned / len(pi_rows) * 100
        pi_deltas = " ".join(
            f"({t.pi_delta} vs {t.prior_label})" for t in trends if t.pi_delta != "—"
        )
        lines.append(
            f"\n## Primary KPI\n\n"
            f"**Purchase-intent inclusion rate:** {pi_mentioned}/{len(pi_rows)} "
            f"({pi_rate:.0f}%) {pi_deltas}\n"
        )

    # Engine scorecard table with trends
    if trends:
        lines.append("\n## Engine Scorecard\n")
        trend_cols = " | ".join(f"Δ {t.prior_label}" for t in trends)
        lines.append(f"| Engine | Prompts | Inclusion | Vendor List | Positive | Citation | {trend_cols} |")
        sep_cols = " | ".join("---" for _ in trends)
        lines.append(f"|--------|---------|-----------|-------------|----------|----------|{sep_cols}|")
        for r in engine_sc:
            eng = r["engine"]
            trend_cells = []
            for t in trends:
                d = t.engine_deltas.get(eng, {})
                cell = ", ".join(f"{m[:3]}:{d.get(m, '—')}" for m in
                               ("inclusion", "vendor_list", "positive_narrative", "citation")
                               if d.get(m, "—") != "—")
                trend_cells.append(cell or "—")
            trend_str = " | ".join(trend_cells)
            lines.append(
                f"| {eng} | {r['prompts']} | {r['inclusion']} | {r['vendor_list']} "
                f"| {r['positive_narrative']} | {r['citation']} | {trend_str} |"
            )
    else:
        lines.append("\n## Engine Scorecard\n")
        lines.append("| Engine | Prompts | Inclusion | Vendor List | Positive Narrative | Citation |")
        lines.append("|--------|---------|-----------|-------------|--------------------|------------|")
        for r in engine_sc:
            lines.append(
                f"| {r['engine']} | {r['prompts']} | {r['inclusion']} | {r['vendor_list']} "
                f"| {r['positive_narrative']} | {r['citation']} |"
            )

    # Stage breakdown
    lines.append("\n\n## Stage Breakdown\n")
    lines.append("| Stage | Engine | Prompts | Inclusion | Vendor List | Positive Narrative | Citation |")
    lines.append("|-------|--------|---------|-----------|-------------|--------------------|----------|")
    for r in stage_sc:
        lines.append(
            f"| {r['stage']} | {r['engine']} | {r['prompts']} | {r['inclusion']} "
            f"| {r['vendor_list']} | {r['positive_narrative']} | {r['citation']} |"
        )

    # Clarity AI referral traffic with trends
    if clarity_summary:
        lines.append("\n\n## AI Referral Traffic (Clarity)\n")
        if trends:
            trend_cols = " | ".join(f"Δ {t.prior_label}" for t in trends)
            lines.append(f"| Engine | Sessions | Users | Pages/Session | Landing Pages | {trend_cols} |")
            sep_cols = " | ".join("---" for _ in trends)
            lines.append(f"|--------|----------|-------|---------------|---------------|{sep_cols}|")
            for r in clarity_summary:
                eng = r["engine"]
                trend_cells = []
                for t in trends:
                    d = t.clarity_deltas.get(eng, {})
                    parts = []
                    for m in ("sessions", "users", "landing_pages"):
                        v = d.get(m, "—")
                        if v != "—":
                            parts.append(f"{m[:4]}:{v}")
                    trend_cells.append(", ".join(parts) or "—")
                trend_str = " | ".join(trend_cells)
                lines.append(
                    f"| {eng} | {r['sessions']} | {r['users']} "
                    f"| {r['pages_per_session']} | {r['landing_pages']} | {trend_str} |"
                )
        else:
            lines.append("| Engine | Sessions | Users | Pages/Session | Landing Pages |")
            lines.append("|--------|----------|-------|---------------|---------------|")
            for r in clarity_summary:
                lines.append(
                    f"| {r['engine']} | {r['sessions']} | {r['users']} "
                    f"| {r['pages_per_session']} | {r['landing_pages']} |"
                )

    if clarity_top_pages:
        lines.append("\n\n## Top landing pages (page clicked from AI engine)\n")
        lines.append("| Engine | Page (URL) | Region | Sessions |")
        lines.append("|--------|------------|--------|----------|")
        for r in clarity_top_pages[:20]:
            lines.append(f"| {r['engine']} | {r['url']} | {r['region']} | {r['sessions']} |")

    # Historical trend summary
    if trends:
        lines.append("\n\n## Trend History\n")
        lines.append("| Metric | Current | " + " | ".join(f"{t.prior_date}" for t in trends) + " |")
        lines.append("|--------|---------|" + " | ".join("---" for _ in trends) + " |")
        for eng in sorted(set(r["engine"] for r in engine_sc)):
            cur_sc = next((r for r in engine_sc if r["engine"] == eng), None)
            if not cur_sc:
                continue
            for m in ("inclusion", "vendor_list", "positive_narrative", "citation"):
                prior_vals = []
                for t in trends:
                    prior_sc = _load_engine_scorecard(Path(RESULTS_DIR) / t.prior_date)
                    prior_r = next((r for r in prior_sc if r["engine"] == eng), None)
                    prior_vals.append(prior_r[m] if prior_r else "—")
                lines.append(
                    f"| {eng}/{m} | {cur_sc[m]} | " + " | ".join(prior_vals) + " |"
                )

    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def print_summary(
    engine_sc: list[dict],
    rows: list[dict],
    clarity_summary: Optional[list[dict]] = None,
    trends: Optional[list["TrendData"]] = None,
) -> None:
    if trends is None:
        trends = []

    pi_rows = [r for r in rows if r["stage"] == "purchase_intent"]
    if pi_rows:
        pi_mentioned = sum(1 for r in pi_rows if r["scores"]["mention"])
        pi_rate = pi_mentioned / len(pi_rows) * 100
        delta_parts = [f"{t.pi_delta} vs {t.prior_label}" for t in trends if t.pi_delta != "—"]
        delta_str = f"  ({', '.join(delta_parts)})" if delta_parts else ""
        log.info(
            "PRIMARY KPI — purchase-intent inclusion: %d/%d (%d%%)%s",
            pi_mentioned, len(pi_rows), pi_rate, delta_str,
        )

    trend_col = "  Δ" if trends else ""
    hdr = f"{'Engine':<14} {'Inclusion':>10} {'Vendor List':>12} {'Positive':>10} {'Citation':>10}{trend_col}"
    log.info(hdr)
    log.info("-" * max(len(hdr), 60))
    for r in engine_sc:
        eng = r["engine"]
        delta_parts = []
        for t in trends:
            d = t.engine_deltas.get(eng, {})
            changes = [f"{m[:3]}:{d[m]}" for m in ("inclusion", "vendor_list", "positive_narrative", "citation")
                       if d.get(m, "—") != "—"]
            if changes:
                delta_parts.append(f"{', '.join(changes)} ({t.prior_label})")
        delta_str = f"  {'; '.join(delta_parts)}" if delta_parts else ""
        log.info(
            f"{eng:<14} {r['inclusion']:>10} {r['vendor_list']:>12} "
            f"{r['positive_narrative']:>10} {r['citation']:>10}{delta_str}"
        )

    if clarity_summary:
        log.info("")
        log.info("AI REFERRAL TRAFFIC (Clarity, last 72h)")
        chdr = f"{'Engine':<14} {'Sessions':>10} {'Users':>10} {'Pages/Sess':>12} {'Landings':>10}{trend_col}"
        log.info(chdr)
        log.info("-" * max(len(chdr), 60))
        for r in clarity_summary:
            eng = r["engine"]
            delta_parts = []
            for t in trends:
                d = t.clarity_deltas.get(eng, {})
                changes = [f"{m}:{d[m]}" for m in ("sessions", "users", "landing_pages")
                           if d.get(m, "—") != "—"]
                if changes:
                    delta_parts.append(f"{', '.join(changes)} ({t.prior_label})")
            delta_str = f"  {'; '.join(delta_parts)}" if delta_parts else ""
            log.info(
                f"{eng:<14} {r['sessions']:>10} {r['users']:>10} "
                f"{r['pages_per_session']:>12} {r['landing_pages']:>10}{delta_str}"
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
            clients["gemini"] = genai.Client(api_key=api_key)  # type: ignore

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


def build_scorer() -> genai.Client:  # type: ignore
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        log.error("GEMINI_API_KEY not set — cannot run scorer")
        sys.exit(1)
    return genai.Client(api_key=api_key)  # type: ignore


def _process_single_task(
    bp: BenchmarkPrompt,
    eng: str,
    clients: dict,
    scorer: "genai.Client",  # type: ignore
    d: Path,
    progress: _ProgressCounter,
    use_search: bool,
) -> None:
    """Query one engine for one prompt, score it, and write the result. Runs inside a thread."""
    tag = f"[{progress.done}/{progress.total}]"
    log.info("%s  %-12s  stage=%-17s  %s", tag, eng, bp.stage, bp.prompt[:60])

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
        progress.increment()
        return

    try:
        scores = score_response(response_text, scorer)
    except Exception:
        log.exception("Failed to score %s response for: %s — skipping", eng, bp.prompt[:50])
        progress.increment()
        return

    record = {
        "prompt": bp.prompt,
        "stage": bp.stage,
        "engine": eng,
        "response": response_text,
        "scores": scores.model_dump(),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    append_result(d, record)
    count = progress.increment()
    if count % 20 == 0 or count == progress.total:
        log.info("Progress: %d/%d tasks completed", count, progress.total)

    time.sleep(API_DELAY_SECONDS)


def run_benchmark(
    engines: list[str],
    stage_filter: Optional[str],
    limit: Optional[int],
    resume: bool,
    skip_clarity: bool = False,
    use_search: bool = False,
    workers_override: Optional[int] = None,
) -> None:
    prompts = load_prompts(stage_filter=stage_filter, limit=limit)
    if not prompts:
        log.error("No prompts loaded — check %s", PROMPTS_CSV)
        sys.exit(1)

    log.info("Loaded %d prompts across stages: %s", len(prompts), ", ".join(sorted({p.stage for p in prompts})))
    if use_search:
        log.info("Web search enabled — each engine uses its native search (no Serper dependency)")

    clients = build_clients(engines)
    scorer = build_scorer()
    d = run_dir()

    completed = load_completed(d) if resume else set()
    if completed:
        log.info("Resuming — %d prompt/engine combos already done", len(completed))

    # Build task list: (prompt, engine) pairs that need to run, grouped by engine
    engine_tasks: dict[str, list[BenchmarkPrompt]] = {eng: [] for eng in engines}
    for bp in prompts:
        for eng in engines:
            if (bp.prompt, eng) not in completed:
                engine_tasks[eng].append(bp)

    total_tasks = sum(len(tasks) for tasks in engine_tasks.values())
    if total_tasks == 0:
        log.info("All prompt/engine combos already completed — nothing to do")
    else:
        # Determine worker counts per engine
        engine_worker_counts: dict[str, int] = {}
        for eng in engines:
            if workers_override is not None:
                w = workers_override
            else:
                env_key = f"ENGINE_WORKERS_{eng.upper()}"
                w = int(os.getenv(env_key, str(ENGINE_WORKERS.get(eng, 4))))
            engine_worker_counts[eng] = max(1, w)

        log.info(
            "Parallelising %d tasks across %d engines: %s",
            total_tasks,
            len(engines),
            ", ".join(f"{eng}={engine_worker_counts[eng]}w×{len(engine_tasks[eng])}t" for eng in engines),
        )

        progress = _ProgressCounter(total_tasks)

        # One ThreadPoolExecutor per engine so each engine has its own concurrency limit.
        # All engine pools run simultaneously.
        engine_pools: list[ThreadPoolExecutor] = []
        all_futures = []

        try:
            for eng in engines:
                tasks = engine_tasks[eng]
                if not tasks:
                    continue
                w = engine_worker_counts[eng]
                pool = ThreadPoolExecutor(max_workers=w, thread_name_prefix=f"aeo-{eng}")
                engine_pools.append(pool)

                for bp in tasks:
                    fut = pool.submit(
                        _process_single_task,
                        bp, eng, clients, scorer, d, progress, use_search,
                    )
                    all_futures.append(fut)

            # Wait for all futures to complete and surface any unexpected exceptions
            for fut in as_completed(all_futures):
                exc = fut.exception()
                if exc is not None:
                    log.error("Unexpected error in worker: %s", exc)
        finally:
            for pool in engine_pools:
                pool.shutdown(wait=True)

        log.info("All %d tasks completed", progress.done)

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

    # Compute trends vs prior runs
    today = datetime.date.today()
    base = RESULTS_DIR
    pi_rate = None
    pi_rows = [r for r in rows if r["stage"] == "purchase_intent"]
    if pi_rows:
        pi_mentioned = sum(1 for r in pi_rows if r["scores"]["mention"])
        pi_rate = pi_mentioned / len(pi_rows) * 100

    trends: list[TrendData] = []
    prev_day = _find_prior_run(base, today)
    if prev_day:
        t = compute_trends(base, today, engine_sc, clarity_summary, pi_rate,
                           label="1d", prior_dir=prev_day)
        if t:
            trends.append(t)

    week_ago_target = today - datetime.timedelta(days=7)
    week_dir = _find_run_near(base, week_ago_target, tolerance=2)
    if week_dir and (not prev_day or week_dir != prev_day):
        t = compute_trends(base, today, engine_sc, clarity_summary, pi_rate,
                           label="7d", prior_dir=week_dir)
        if t:
            trends.append(t)

    if trends:
        log.info("Comparing against: %s", ", ".join(f"{t.prior_date} ({t.prior_label})" for t in trends))

    write_summary_md(d / "summary.md", engine_sc, stage_sc, rows, clarity_summary, clarity_top_pages, trends)
    write_trends_csv(d / "trends.csv", engine_sc, clarity_summary, trends)

    log.info("Results written to %s", d)
    print_summary(engine_sc, rows, clarity_summary, trends)


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
    parser.add_argument("--no-search", action="store_true", help="Disable native web search for all engines (test training-data-only responses)")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=(
            "Override worker count for ALL engines. "
            f"Defaults: {', '.join(f'{e}={w}' for e, w in ENGINE_WORKERS.items())}. "
            "Or set per-engine: ENGINE_WORKERS_CHATGPT=10 etc."
        ),
    )
    args = parser.parse_args()

    selected_engines = [e.strip().lower() for e in args.engines.split(",")]
    for e in selected_engines:
        if e not in ENGINES:
            parser.error(f"Unknown engine: {e}. Choose from {ENGINES}")

    use_search = not args.no_search

    run_benchmark(
        engines=selected_engines,
        stage_filter=args.stage,
        limit=args.limit,
        resume=args.resume,
        skip_clarity=args.no_clarity,
        use_search=use_search,
        workers_override=args.workers,
    )


if __name__ == "__main__":
    main()
