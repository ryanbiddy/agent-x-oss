# Contributing to Agent X OSS

## What we accept

### Prompt agents

New agents should include:

- `system.md`
- `input-format.md`
- `example.md`

They should serve a real founder, operator, executive, or comms use case.

### Improvements to existing agents

Open a PR with:

- what changed
- why it changed
- a before and after example when possible

### Automation app contributions

Code contributions to `social_reply_crew/` are welcome, especially:

- browser selector hardening
- auth and session handling improvements
- SQLite memory improvements
- better digest UX
- tests and setup docs

### Examples and docs

New examples, walkthroughs, and setup fixes are all useful.

## What we don't accept

- generic copywriting wrappers with no clear use case
- low-effort or fake examples
- system prompts that are basically "be a good writer"
- automation changes that remove the human review step before posting

## PR format

Title examples:

- `[agent] improve founder post framing`
- `[app] harden X reply metric scraping`
- `[docs] expand setup instructions`

Body:

Use 2-5 sentences on what changed, why it matters, and how it was tested.
