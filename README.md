# Agent X OSS

> Open-source social agents and automation for founders, operators, and comms teams.

Agent X OSS is a free, open-source repo for AI-assisted social workflows. It includes prompt-first agents for writing and review, plus a runnable Python automation app for authenticated X social listening and reply drafting.

The goal is simple: help people build stronger social presence and faster feedback loops without turning into full-time content operators.

## What's In The Repo

### Prompt Agents

| Agent | What it does |
|---|---|
| Founder Post Agent | Turns messy thoughts into strong X or LinkedIn posts |
| Launch Comms Agent | Generates coordinated launch messaging from product notes |
| Technical-to-Human Agent | Translates dense updates into clear, shareable copy |
| Executive POV Agent | Surfaces your narrative angles and strongest takes |
| Risk Check Agent | Flags tone issues, timing risks, and posting mistakes before you publish |

### Automation App

`social_reply_crew/` is a modular Python app built with CrewAI, browser-use, Playwright, and SQLite. It can:

- read the authenticated X `For You` timeline
- analyze reply tone from inspirational accounts
- learn from historical engagement stored locally
- draft two reply options per post
- present a terminal digest for human selection
- post the selected reply through browser DOM automation

## Quick Start

### Clone The Repo

```bash
git clone https://github.com/ryanbiddy/agent-x-oss
cd agent-x-oss
```

### Use The Prompt Agents

Each agent folder includes:

- `system.md` for the system prompt
- `input-format.md` for the recommended task shape
- `example.md` for a real example

These can be used in Claude Code, Codex, ChatGPT projects, or directly through an API workflow.

### Run The X Automation App

```bash
cd social_reply_crew
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
playwright install chromium
copy .env.example .env
social-reply-crew run --refresh-first
```

The app README has the full setup and environment details.

## Repo Structure

```text
agent-x-oss/
  agents/
  docs/
  examples/
  social_reply_crew/
  templates/
```

## Who This Is For

- founders who have strong ideas but inconsistent output
- operators who want a tighter social research and engagement loop
- comms teams who want reusable prompt assets instead of generic copy tools
- builders experimenting with browser-native social automation without the official X API

## Roadmap

### Now

- 5 core prompt agents
- modular X reply automation app in `social_reply_crew`
- MIT licensed repo that works with standard LLM tooling

### Next

- stronger documentation for agent chaining and workflows
- more examples and contributed agents
- hardening the X automation flow with more selectors and test coverage

### Later

- richer analytics and feedback loops
- more reusable automation packages
- collaboration, guardrails, and approval workflows

## License

MIT License. Built by Ryan Biddy.
