# Agent X OSS

> Open-source agents for founder and executive social.

Agent X OSS is a free, open-source collection of AI agents for founders, executives, and comms teams who want to build a stronger social presence without becoming full-time content creators.

These agents work with Claude Code, OpenAI Codex, or any LLM API.

---

## The 5 Agents

| Agent | What it does |
|---|---|
| Founder Post Agent | Turns messy thoughts into strong X/LinkedIn posts |
| Launch Comms Agent | Generates coordinated launch messaging from product notes |
| Technical-to-Human Agent | Translates dense updates into clear, shareable copy |
| Executive POV Agent | Surfaces your narrative angles and strong takes |
| Risk Check Agent | Flags tone issues, timing risks, and posting mistakes before you publish |

---

## Quick Start

### With Claude Code

```bash
git clone https://github.com/YOURUSERNAME/agent-x-oss
cd agent-x-oss
```

Then in Claude Code: use the system prompt in `agents/[agent-name]/system.md` as your system prompt, paste your input as the user message.

### With the API directly

Each agent folder has:
- `system.md` - the system prompt
- `input-format.md` - what to send
- `example.md` - a real input/output sample

### With Codex

Copy any agent's `system.md` into a Codex skill. Use the `input-format.md` as your task template.

---

## Repo Structure

```text
agent-x-oss/
  agents/
  docs/
  examples/
  templates/
```

Each folder is designed to be portable, readable, and easy to remix into your own workflows.

---

## Roadmap

Now: 5 core agents, MIT licensed, works with any LLM
Next: Hosted playground, voice profiles, agent chaining
Later: Agent X platform - social integrations, analytics, team workflows

Star this repo to follow the build.

---

## License

MIT License. Built by Ryan Biddy
