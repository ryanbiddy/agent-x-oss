from __future__ import annotations

import os

import anthropic

from social_reply_crew.agents import get_anti_ai_rules
from social_reply_crew.interaction_history import format_context_card
from social_reply_crew.memory_store import load_memory_context
from social_reply_crew.models import ReplyDigest, ReplyOption, ReplyRecommendation, SelectedReply
from social_reply_crew.voice_intake import get_voice_context_for_prompt

TUNE_OPTIONS = {
    "f": "Make this reply noticeably funnier. Add dry wit or a well-placed observation. Keep it short.",
    "t": "Make this more technically specific. Add a concrete tool name, number, or implementation detail.",
    "s": "Trim to under 180 characters while keeping the core point. Cut everything non-essential.",
    "p": "Reframe using a personal experience or specific observation. Start with 'When I' or reference something concrete you've done.",
    "b": "Take a stronger, more contrarian position. Push back on an assumption in the original tweet.",
    "r": "Complete rewrite - different angle entirely. Don't use any words from the previous version.",
}


def present_digest_and_collect_choices(
    digest: ReplyDigest,
    voice_context: str | None = None,
) -> list[SelectedReply]:
    print("\n" + "=" * 88)
    print("SOCIAL REPLY DIGEST")
    print("=" * 88)
    print(digest.global_guidance.strip())

    resolved_voice_context = voice_context or get_voice_context_for_prompt(load_memory_context())

    selections: list[SelectedReply] = []
    for index, recommendation in enumerate(digest.recommendations, start=1):
        print("\n" + "-" * 88)
        print(f"Post {index}: {recommendation.author}")
        print(
            format_context_card(
                handle=recommendation.author_handle or recommendation.author,
                user_context=recommendation.user_context,
                interaction=recommendation.interaction,
                tweet_score=float(recommendation.score or 0),
                why_surfaced=recommendation.why_surfaced or "High focus match",
            )
        )
        print(f"Link: {recommendation.post_url}")
        print("Original:")
        print(recommendation.original_text.strip())

        for option_index, option in enumerate(recommendation.options, start=1):
            print(f"\nOption {option_index} - {option.style_label}")
            option.reply_text = validate_and_display_reply(option.reply_text.strip(), option_index)
            print(f"Why: {option.rationale.strip()}")

        chosen_option = _prompt_for_choice(recommendation, resolved_voice_context)
        selections.append(
            SelectedReply(
                recommendation=recommendation,
                chosen_option=chosen_option,
            )
        )

    return selections


def validate_and_display_reply(reply_text: str, option_num: int) -> str:
    """Validate reply length and display with appropriate warnings."""
    char_count = len(reply_text)

    if char_count > 280:
        trimmed = _trim_to_limit(reply_text, 280)
        print(f"\nOption {option_num} WARNING {char_count} chars - OVER 280 LIMIT")
        print(f"  Original: {reply_text}")
        print(f"  Trimmed:  {trimmed} ({len(trimmed)} chars)")
        print("  [Using trimmed version by default]")
        return trimmed
    if char_count > 240:
        print(f"\nOption {option_num} WARNING {char_count}/280 chars")
        print(f"  {reply_text}")
        return reply_text

    print(f"\nOption {option_num} OK {char_count}/280 chars")
    print(f"  {reply_text}")
    return reply_text


def _trim_to_limit(text: str, limit: int) -> str:
    """Trim text to character limit, breaking at word boundaries."""
    if len(text) <= limit:
        return text
    trimmed = text[: limit - 3]
    last_space = trimmed.rfind(" ")
    if last_space > limit - 30:
        trimmed = trimmed[:last_space]
    return trimmed.rstrip() + "..."


def get_refined_reply(
    original_tweet: str,
    current_reply: str,
    modifier: str,
    voice_context: str,
) -> str:
    """Re-generate a reply with a specific modifier applied."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    instruction = TUNE_OPTIONS.get(modifier, "Improve this reply.")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        system=(
            "You are rewriting a social media reply with a specific instruction.\n"
            f"{voice_context}\n"
            f"{get_anti_ai_rules()}\n"
            "Keep it under 250 characters unless the instruction says otherwise."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f'Original tweet: "{original_tweet}"\n\n'
                    f'Current reply: "{current_reply}"\n\n'
                    f"Instruction: {instruction}\n\n"
                    "Return ONLY the new reply text. No explanation."
                ),
            }
        ],
    )
    refined = response.content[0].text.strip()
    return _trim_to_limit(refined, 280) if len(refined) > 280 else refined


def _prompt_for_choice(
    recommendation: ReplyRecommendation,
    voice_context: str,
) -> ReplyOption | None:
    while True:
        try:
            print("\nChoose: [1] Option 1  [2] Option 2  [k] Skip")
            print("Refine: [f] Funnier  [t] Technical  [s] Shorter  [p] Personal  [b] Bolder  [r] Rewrite")
            raw_value = input("> ").strip().lower()
        except EOFError:
            return None

        if raw_value in {"1", "2"}:
            return recommendation.options[int(raw_value) - 1]
        if raw_value in {"k", "skip"}:
            return None
        if raw_value in TUNE_OPTIONS:
            option_number = input("Refine option 1 or 2? ").strip()
            if option_number not in {"1", "2"}:
                print("Please enter 1 or 2.")
                continue
            base_option = recommendation.options[int(option_number) - 1]
            try:
                refined = get_refined_reply(
                    original_tweet=recommendation.original_text,
                    current_reply=base_option.reply_text,
                    modifier=raw_value,
                    voice_context=voice_context,
                )
            except Exception as exc:
                print(f"Refinement failed: {exc}")
                continue

            refined = validate_and_display_reply(refined, int(option_number))
            print(f"\nRefined draft:\n  {refined}")
            confirm = input("Use this? [y/n]: ").strip().lower()
            if confirm == "y":
                return ReplyOption(
                    style_label=f"{base_option.style_label} / refined",
                    reply_text=refined,
                    rationale=f"Refined with instruction: {TUNE_OPTIONS[raw_value]}",
                )
            continue

        print("Please enter 1, 2, k, skip, or a refine key.")
