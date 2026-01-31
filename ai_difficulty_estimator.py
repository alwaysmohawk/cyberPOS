"""
AI-Powered Task Difficulty Estimator
Uses Claude API to intelligently estimate task difficulty and time
"""

import os
from pathlib import Path
from anthropic import Anthropic

# Load .env from project directory if key isn't already set
if not os.environ.get("ANTHROPIC_API_KEY"):
    _env_path = Path(__file__).resolve().parent / ".env"
    if _env_path.exists():
        for _line in _env_path.read_text().splitlines():
            if _line.startswith("ANTHROPIC_API_KEY="):
                os.environ["ANTHROPIC_API_KEY"] = _line.split("=", 1)[1].strip()
                break

# Configuration
API_KEY_ENV = "ANTHROPIC_API_KEY"
MODEL = "claude-3-haiku-20240307"

def estimate_task_difficulty_ai(task_title: str, task_notes: str = "") -> tuple[int, int]:
    """
    Use Claude API to estimate task difficulty and time

    Args:
        task_title: The task title/name
        task_notes: Optional task notes/description

    Returns:
        tuple: (difficulty_level (0-5), estimated_minutes)
    """

    # Check for API key
    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        print(f"Warning: {API_KEY_ENV} not set. Using fallback estimation.")
        return _fallback_estimation(task_title, task_notes)

    try:
        client = Anthropic(api_key=api_key)

        # Construct the full task description
        full_task = task_title
        if task_notes:
            full_task += f"\n\nNotes: {task_notes}"

        # Create the prompt
        prompt = f"""Analyze this task and estimate its difficulty and time requirement.

Task: {full_task}

Provide ONLY a JSON response in this exact format (no markdown, no explanation):
{{"difficulty": <0-5>, "minutes": <number>}}

Difficulty scale (0-5):
0 = TRIVIAL (instant, automatic habits like "brush teeth", "take vitamin", "check email")
1 = VERY LIGHT (quick simple tasks like "take out trash", "make bed", "water plants")
2 = LIGHT (routine tasks like "do laundry", "wash dishes", "quick call")
3 = MODERATE (tasks requiring thought or multiple steps like "clean kitchen", "grocery shopping", "pay bills")
4 = HEAVY (complex or time-consuming tasks like "research topic", "write document", "organize closet")
5 = VERY HEAVY (major projects or mentally demanding work like "debug production issue", "plan project", "deep research")

Estimate realistic time in minutes based on the task complexity."""

        # Call Claude API
        message = client.messages.create(
            model=MODEL,
            max_tokens=100,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Parse the response
        response_text = message.content[0].text.strip()

        # Parse JSON response
        import json
        try:
            result = json.loads(response_text)
            difficulty = max(0, min(5, result.get("difficulty", 3)))  # Clamp to 0-5
            minutes = max(1, result.get("minutes", 15))  # At least 1 minute
            return (difficulty, minutes)
        except json.JSONDecodeError:
            print(f"Warning: Could not parse AI response: {response_text}")
            return _fallback_estimation(task_title, task_notes)

    except Exception as e:
        print(f"Warning: AI estimation failed ({e}). Using fallback.")
        return _fallback_estimation(task_title, task_notes)

def _fallback_estimation(task_title: str, task_notes: str = "") -> tuple[int, int]:
    """
    Fallback estimation when AI is not available
    Uses simple heuristics based on length and keywords
    """
    title_len = len(task_title)
    has_notes = len(task_notes) > 0

    # Keyword-based hints
    trivial_keywords = ["brush", "vitamin", "pill", "medication"]
    very_light_keywords = ["trash", "bed", "water"]
    light_keywords = ["laundry", "dishes", "call", "email"]
    heavy_keywords = ["research", "build", "create", "design", "plan", "write", "organize"]
    very_heavy_keywords = ["debug", "fix", "install", "configure", "project"]

    title_lower = task_title.lower()

    # Check for keywords
    is_trivial = any(kw in title_lower for kw in trivial_keywords)
    is_very_light = any(kw in title_lower for kw in very_light_keywords)
    is_light = any(kw in title_lower for kw in light_keywords)
    is_heavy = any(kw in title_lower for kw in heavy_keywords)
    is_very_heavy = any(kw in title_lower for kw in very_heavy_keywords)

    if is_trivial and title_len < 20:
        difficulty = 0
        minutes = 2
    elif is_very_heavy or title_len > 60:
        difficulty = 5
        minutes = 120
    elif is_heavy or title_len > 40:
        difficulty = 4
        minutes = 60
    elif is_light and title_len < 30:
        difficulty = 2
        minutes = 15
    elif is_very_light and title_len < 20:
        difficulty = 1
        minutes = 5
    else:
        difficulty = 3
        minutes = 30

    # Adjust for notes
    if has_notes:
        difficulty = min(5, difficulty + 1)
        minutes += 15

    return (difficulty, minutes)

def batch_estimate_tasks(tasks: list[dict]) -> list[tuple[str, int, int]]:
    """
    Estimate difficulty for multiple tasks

    Args:
        tasks: List of task dicts with 'title' and optional 'notes'

    Returns:
        List of tuples: (title, difficulty, minutes)
    """
    results = []

    for task in tasks:
        title = task.get('title', '')
        notes = task.get('notes', '')

        difficulty, minutes = estimate_task_difficulty_ai(title, notes)
        results.append((title, difficulty, minutes))

    return results

if __name__ == "__main__":
    # Test the estimator
    test_tasks = [
        {"title": "take out recycling"},
        {"title": "research quantum computing applications"},
        {"title": "clean kitchen counters"},
        {"title": "debug authentication bug in production"},
        {"title": "call dentist"},
    ]

    print("Testing AI Difficulty Estimator...")
    print("=" * 60)

    if not os.environ.get(API_KEY_ENV):
        print(f"\nNote: {API_KEY_ENV} not set. Using fallback estimation.\n")

    results = batch_estimate_tasks(test_tasks)

    for title, difficulty, minutes in results:
        diff_labels = ["TRIVIAL", "VERY LIGHT", "LIGHT", "MODERATE", "HEAVY", "VERY HEAVY"]
        diff_label = diff_labels[difficulty]
        print(f"[{difficulty}] {title}")
        print(f"    → {diff_label} | ~{minutes} minutes")
        print()
