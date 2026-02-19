"""
AEO Benchmark Runner — measures Factory AI visibility across AI answer engines.

Queries ChatGPT, Gemini, and Perplexity with a set of buyer-journey prompts,
scores each response for Factory AI inclusion, and produces aggregate scorecards.

Usage:
    python aeo_benchmark.py                          # Full run, all engines
    python aeo_benchmark.py --engines chatgpt,gemini # Select engines
    python aeo_benchmark.py --limit 10               # First N prompts (testing)
    python aeo_benchmark.py --stage purchase_intent   # Single stage only
    python aeo_benchmark.py --resume                  # Skip already-completed prompts
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

import google.generativeai as genai  # type: ignore
import openai
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

ENGINES = ("chatgpt", "gemini", "perplexity")
STAGES = (
    "problem_unaware",
    "problem_aware",
    "solution_aware",
    "vendor_aware",
    "purchase_intent",
)

API_DELAY_SECONDS = 2.0
MAX_RETRIES = 3

CHATGPT_MODEL = "gpt-4o"
GEMINI_MODEL = "gemini-2.5-flash"
PERPLEXITY_MODEL = "sonar"
SCORER_MODEL = "gemini-2.0-flash"

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


def query_chatgpt(prompt: str, client: openai.OpenAI) -> str:
    def _call():
        resp = client.chat.completions.create(
            model=CHATGPT_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""
    return _retry(_call, "ChatGPT")


def query_gemini(prompt: str, model) -> str:
    def _call():
        resp = model.generate_content(prompt)
        return resp.text
    return _retry(_call, "Gemini")


def query_perplexity(prompt: str, client: openai.OpenAI) -> str:
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


def write_summary_md(path: Path, engine_sc: list[dict], stage_sc: list[dict], rows: list[dict]) -> None:
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

    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def print_summary(engine_sc: list[dict], rows: list[dict]) -> None:
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
) -> None:
    prompts = load_prompts(stage_filter=stage_filter, limit=limit)
    if not prompts:
        log.error("No prompts loaded — check %s", PROMPTS_CSV)
        sys.exit(1)

    log.info("Loaded %d prompts across stages: %s", len(prompts), ", ".join(sorted({p.stage for p in prompts})))

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

            # Query engine
            try:
                if eng == "chatgpt":
                    response_text = query_chatgpt(bp.prompt, clients["chatgpt"])
                elif eng == "gemini":
                    response_text = query_gemini(bp.prompt, clients["gemini"])
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

    # Build scorecards
    if not jsonl_path(d).exists():
        log.warning("No results to summarise")
        return

    rows = load_all_results(d)
    engine_sc, stage_sc = compute_scorecards(rows)

    write_scorecard_csv(d / "scorecard.csv", engine_sc)
    write_scorecard_csv(d / "scorecard_by_stage.csv", stage_sc)
    write_summary_md(d / "summary.md", engine_sc, stage_sc, rows)

    log.info("Results written to %s", d)
    print_summary(engine_sc, rows)


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
    args = parser.parse_args()

    selected_engines = [e.strip().lower() for e in args.engines.split(",")]
    for e in selected_engines:
        if e not in ENGINES:
            parser.error(f"Unknown engine: {e}. Choose from {ENGINES}")

    run_benchmark(
        engines=selected_engines,
        stage_filter=args.stage,
        limit=args.limit,
        resume=args.resume,
    )


if __name__ == "__main__":
    main()
