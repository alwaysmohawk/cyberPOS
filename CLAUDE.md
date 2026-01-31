# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running Scripts

All scripts must run from `/root/cyberpos/` — the logo BMP is opened via relative path.

```bash
python3 morning_dispatch.py         # Morning briefing (tasks, weather, calendar)
python3 evening_dispatch.py         # Evening briefing (same structure, evening habits)
python3 nighttime_dispatch.py       # Night checklist + tomorrow's forecast
python3 onePer.py                   # One receipt per task (with QR codes)
python3 allTasks.py                 # Single-page task summary
python3 task_server.py              # Flask QR completion server (port 5000)
python3 google_tasks_helper.py      # Test Google API auth standalone
python3 ai_difficulty_estimator.py  # Test difficulty estimation standalone
```

Scripts that fetch tasks (morning, evening, onePer, allTasks) need `ANTHROPIC_API_KEY` set for AI difficulty scoring. It's baked into the systemd service files for scheduled runs. Nighttime and task_server don't need it.

## Architecture

**google_tasks_helper.py** is the shared hub. A single OAuth token (`token.pickle`) covers both Tasks and Calendar scopes. Key functions:
- `get_tasks_with_ids(max_results)` → `[(task_id, tasklist_id, title, difficulty), ...]`
- `get_calendar_events(max_events, days_offset)` → `[(time_str, title, is_all_day), ...]` — `days_offset=1` fetches tomorrow (used by nighttime_dispatch)
- `complete_task(task_id, tasklist_id)` → bool (called by task_server on QR scan)
- `estimate_difficulty(task)` → delegates to ai_difficulty_estimator

**ai_difficulty_estimator.py** scores tasks 0–5 via Claude Haiku. Falls back to keyword heuristics if no API key. Model is pinned to `claude-3-haiku-20240307` — do not use `-latest`, it 404s with this key.

**weather.py** — shared weather fetching. `get_weather()` returns current conditions (used by morning/evening); `get_tomorrow_weather()` returns tomorrow's daily forecast via Open-Meteo's `daily` endpoint (used by nighttime). Both share `WEATHER_CODES` and `wind_dir()`.

**printer.py** — shared printer connection and receipt formatting. Owns the `Network` instance (`p`), ESC/POS helpers (`raw`, `invert`), separator constants (`MAJOR`/`MINOR`), logo printing (`print_logo`), and receipt text utilities (`diff_ascii`, `line_item`, `wrap_task`). All dispatch and receipt scripts import from here.

**task_server.py** — Flask on port 5000, handles `/complete/<tasklist_id>/<task_id>` from QR scans on printed receipts. Runs as a persistent systemd service.

## Scheduling (systemd)

```
cyberpos-morning.timer  → 07:30 → morning_dispatch.py  (has ANTHROPIC_API_KEY)
cyberpos-evening.timer  → 17:00 → evening_dispatch.py  (has ANTHROPIC_API_KEY)
cyberpos-night.timer    → 23:00 → nighttime_dispatch.py (no key needed)
task-server.service     → always on (Flask, port 5000)
```

All unit files live in `/etc/systemd/system/`. After editing any of them:
```bash
systemctl daemon-reload
systemctl restart cyberpos-<name>.timer   # or .service
systemctl list-timers | grep cyberpos     # verify next fire times
journalctl -u cyberpos-morning.service -n 20  # check logs
```

## Network

- Printer: `192.168.88.154:9100` (ESC/POS thermal, 48-column width)
- Task completion server: `192.168.88.130:5000`
- QR codes on receipts encode: `http://192.168.88.130:5000/complete/{tasklist_id}/{task_id}?name={task_name}`

## Secrets — do not commit

The following files contain secrets and are gitignored. They must never be staged or committed:

- `.env` — `ANTHROPIC_API_KEY`. Created manually; `ai_difficulty_estimator.py` loads it at runtime.
- `credentials.json` — Google OAuth client secret. Place manually from Google Cloud Console.
- `token.pickle` — cached Google OAuth token. Regenerated automatically on first run after deletion.

Before any `git add`, verify with `git status` that none of these appear. If one shows up as staged, remove it with `git reset HEAD <file>`. If a secret has already been pushed, rotate it immediately — the damage is done regardless of whether it's later removed from history.

## Gotchas

- **Google scope changes:** If you add a scope to `SCOPES` in google_tasks_helper.py, delete `token.pickle` to force a fresh OAuth flow. The cached token won't have new scopes.
- **Model pin:** Use `claude-3-haiku-20240307` only. The `-latest` suffix 404s.
- **Shared modules:** Weather and printer logic live in `weather.py` and `printer.py`. All dispatch/receipt scripts import from these — edit once, it applies everywhere.
- **GitHub:** Credential store is configured at `~/.git-credentials`. Push with `git push` — no password prompt needed.
