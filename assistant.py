"""
cyberPOS assistant: Claude-powered quick capture and task breakdown.
Both degrade gracefully: if the API is unavailable, capture saves the raw text as a task
and breakdown returns nothing (the UI says so).
"""

import json
import re
from datetime import date

import anthropic

# Importing the estimator loads ANTHROPIC_API_KEY from .env if it isn't already set
import ai_difficulty_estimator  # noqa: F401

MODEL = "claude-opus-5-5"


def _ask(prompt, max_tokens=2048):
    """One short JSON-returning call. Returns the parsed object, or raises."""
    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        betas=["server-side-fallback-2026-07-01"],
        messages=[{"role": "user", "content": prompt}],
        extra_body={"output_config": {"effort": "low"}, "fallbacks": "default"},
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("request declined")
    text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text").strip()
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError(f"no JSON in response: {text[:200]}")
    return json.loads(match.group(0))


def parse_capture(text, list_titles):
    """
    Turn a quick brain-dump line into a task.

    Returns:
        dict with title, notes, due ('YYYY-MM-DD' or None), priority (1-3), list (title or None)
    """
    fallback = {"title": text.strip()[:200], "notes": "", "due": None, "priority": 2, "list": None}
    today = date.today()
    prompt = f"""Today is {today:%A %Y-%m-%d}. Turn this quick note into one to-do item.

Note: {text}

Available task lists: {json.dumps(list_titles)}

Reply with ONLY a JSON object, no markdown:
{{"title": "<short imperative title, keep the user's wording where possible>",
  "notes": "<extra detail from the note, or empty string>",
  "due": "<YYYY-MM-DD if the note implies a date or deadline, else null>",
  "priority": <1 if urgent/important, 3 if someday/low, else 2>,
  "list": "<one of the available list titles if it clearly fits one, else null>"}}"""
    try:
        data = _ask(prompt)
    except Exception as e:
        print(f"Capture parsing failed, saving raw text: {e}")
        return fallback
    out = dict(fallback)
    if isinstance(data.get("title"), str) and data["title"].strip():
        out["title"] = data["title"].strip()[:200]
    if isinstance(data.get("notes"), str):
        out["notes"] = data["notes"].strip()
    if isinstance(data.get("due"), str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["due"]):
        out["due"] = data["due"]
    if data.get("priority") in (1, 2, 3):
        out["priority"] = data["priority"]
    if data.get("list") in list_titles:
        out["list"] = data["list"]
    return out


def breakdown(title, notes=""):
    """
    Split a task that feels too big into 3-6 concrete steps; the first takes about 2 minutes.

    Returns:
        list of step titles (empty on failure)
    """
    prompt = f"""I have ADHD and this task feels too big to start:

Task: {title}
{f"Notes: {notes}" if notes else ""}

Break it into 3 to 6 concrete physical steps, in order. The FIRST step must be tiny and
take about 2 minutes, just enough to get started (for example "Put the laundry basket by
the door"). Each step is a short imperative phrase under 60 characters. No numbering.

Reply with ONLY a JSON object, no markdown: {{"steps": ["...", "..."]}}"""
    try:
        data = _ask(prompt)
        steps = [s.strip()[:120] for s in data.get("steps", []) if isinstance(s, str) and s.strip()]
        return steps[:6]
    except Exception as e:
        print(f"Breakdown failed: {e}")
        return []
