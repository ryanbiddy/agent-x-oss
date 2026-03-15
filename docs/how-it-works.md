# How Agent X OSS Works

Agent X OSS is a prompt library, not a hosted app.

Each agent is a focused system prompt designed for one communications job. You pair that prompt with a real input, run it in your preferred model, and then edit the result like a human operator.

## Core idea

Most AI writing tools try to do everything. These agents do one job each:
- shaping messy founder thoughts into strong posts
- turning launch notes into a coordinated launch package
- translating technical updates into human language
- surfacing an executive's true point of view
- reviewing a draft before it goes live

That narrower scope makes the output more usable and easier to trust.

## Anatomy of an agent

Every agent folder includes:
- `system.md` - the system prompt you load into your model
- `input-format.md` - the easiest way to structure the user message
- `example.md` - a sample input/output pair to show the intended behavior

## Recommended workflow

1. Pick the agent that matches the job.
2. Copy `system.md` into your tool as the system prompt.
3. Use `input-format.md` to shape your user message.
4. Run the model.
5. Edit the result for accuracy, taste, and timing.

## Agent chaining

You can also run agents in sequence. Example:
- Start with Executive POV Agent to find the strongest angle.
- Pass that output into Founder Post Agent to draft the post.
- Run the final draft through Risk Check Agent before publishing.

## Best practices

- Use raw, specific inputs. Messy notes are better than polished blurbs.
- Keep one clear objective per run.
- Treat outputs as strong drafts, not auto-publish copy.
- Preserve the human voice. The point is leverage, not impersonation.
