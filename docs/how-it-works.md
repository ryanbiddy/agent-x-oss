# How Agent X OSS Works

Agent X OSS now has two layers:

- prompt-first agents for structured writing and review tasks
- a runnable automation app for X social listening and reply execution

## Core idea

Most AI social tools are either too generic or too automated. This repo is meant to sit in the useful middle:

- prompts that are narrow enough to produce better output
- automation that still keeps a human in the loop before posting
- local memory so the system can learn from what actually performs

## Prompt agents

Each prompt agent is designed for one job:

- shaping messy founder thoughts into strong posts
- turning launch notes into a coordinated launch package
- translating technical updates into human language
- surfacing an executive's point of view
- reviewing a draft before it goes live

Every agent folder includes:

- `system.md` for the system prompt
- `input-format.md` for the recommended user input shape
- `example.md` for a sample input and output

Recommended workflow:

1. Pick the agent that matches the job.
2. Load `system.md` into your preferred tool.
3. Structure the input with `input-format.md`.
4. Run the model.
5. Edit for accuracy, taste, and timing.

## Automation app

`social_reply_crew/` is the first runnable app in the repo.

It uses:

- CrewAI for agent orchestration
- browser-use with Playwright for browser-native X automation
- SQLite for local reply memory and engagement tracking

The flow is:

1. Scout the authenticated `For You` timeline.
2. Read strong replies from inspirational accounts.
3. Pull historical performance rules from SQLite.
4. Draft two reply options per target post.
5. Show a terminal digest.
6. Wait for the human to choose or skip.
7. Post only the selected reply and store it locally for later learning.

## Agent chaining

You can chain the prompt agents together or combine them with the automation app.

Examples:

- Executive POV Agent -> Founder Post Agent -> Risk Check Agent
- social_reply_crew -> Risk Check Agent for a final human review pass

## Best practices

- Use raw, specific inputs. Messy notes beat polished blurbs.
- Keep one clear objective per run.
- Treat outputs as strong drafts, not autonomous truth.
- Keep a human in the loop for anything public-facing.
- Let historical performance influence style, but not override judgment.
