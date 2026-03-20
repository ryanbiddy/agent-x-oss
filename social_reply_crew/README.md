# Social Reply Crew

A modular CrewAI + browser-use + SQLite workflow for authenticated X social listening, reply drafting, engagement tracking, and lightweight reinforcement via historical performance.

## What It Does

- Uses `browser-use` to inspect the authenticated user's `For You` timeline.
- Mines recent high-signal replies from a fixed list of inspirational X accounts.
- Stores posted replies in a local SQLite database and refreshes their engagement score from the user's `Replies` tab.
- Uses three CrewAI agents to turn browser data + historical engagement into 2 reply options per target post.
- Presents a terminal digest and optionally posts the selected reply back to X through browser DOM automation.

## Project Layout

```text
social_reply_crew/
  src/social_reply_crew/
    agents.py
    browser_tools.py
    config.py
    db.py
    digest.py
    exceptions.py
    main.py
    models.py
```

## Setup

1. Create a Python 3.11+ virtual environment.
2. Install the package:

   ```bash
   pip install -e .
   ```

3. Install browser runtimes:

   ```bash
   playwright install chromium
   ```

4. Copy `.env.example` to `.env` and fill in your keys and X credentials.
5. Prefer seeding `X_STORAGE_STATE` with an authenticated session. `browser-use` uses Playwright-compatible storage state JSON, so the file can be reused across runs.

## Usage

Run the full scout -> analyze -> draft -> post flow:

```bash
social-reply-crew run --refresh-first
```

Refresh reply engagement scores without drafting new replies:

```bash
social-reply-crew refresh-metrics
```

Run a recurring engagement refresh loop:

```bash
social-reply-crew watch-metrics --interval-minutes 30
```

## Notes

- The X automation is intentionally defensive and uses multiple selector fallbacks to survive moderate DOM changes.
- Posting relies on browser DOM interaction only. No X API calls are used.
- If X presents CAPTCHA or 2FA, seed `X_STORAGE_STATE` or use `X_USE_SYSTEM_CHROME=true` with a logged-in profile.
