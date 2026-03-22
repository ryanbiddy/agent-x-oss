from __future__ import annotations

"""
Voice Intake System
Runs once to build the user's voice fingerprint from their actual writing.
Scrapes their X posts and LinkedIn, asks about publications,
then builds a detailed style guide stored in MEMORY.md.
"""

import asyncio
import os
import re

import anthropic

from social_reply_crew.memory_store import MEMORY_PATH, ensure_memory_file


async def run_voice_intake(browser_service, x_handle: str) -> str:
    """
    Full voice intake flow:
    1. Scrape last 200 of user's own X posts
    2. Ask about LinkedIn URL
    3. Ask about publications/articles
    4. Run Claude analysis to build fingerprint
    5. Store in MEMORY.md Section 1
    """
    print("\n" + "=" * 60)
    print("VOICE INTAKE - Building your style fingerprint")
    print("This runs once and makes every reply sound like you.")
    print("=" * 60 + "\n")

    own_tweets: list[dict[str, str]] = []
    print(f"Scraping your recent posts from {x_handle}...")
    try:
        own_tweets = await browser_service.scrape_account_tweets_for_voice(x_handle, limit=200)
        print(f"  Collected {len(own_tweets)} posts")
    except Exception as exc:
        print(f"  Could not scrape X posts: {exc}")

    linkedin_text = ""
    linkedin_url = input("\nYour LinkedIn URL (press Enter to skip): ").strip()
    if linkedin_url:
        try:
            linkedin_text = await browser_service.scrape_linkedin_about(linkedin_url)
            print("  Collected LinkedIn profile")
        except Exception as exc:
            print(f"  Could not scrape LinkedIn: {exc}")

    publications_text = ""
    print("\nDo you have any articles, newsletters, or publications?")
    pub_input = input("Paste URLs separated by commas (or press Enter to skip): ").strip()
    if pub_input:
        urls = [item.strip() for item in pub_input.split(",") if item.strip()]
        for url in urls[:3]:
            try:
                text = await browser_service.scrape_page_text(url)
                publications_text += f"\n--- {url} ---\n{text[:2000]}\n"
                print(f"  Collected: {url}")
            except Exception as exc:
                print(f"  Could not scrape {url}: {exc}")

    print("\nAnalyzing your writing style...")
    fingerprint = await _build_voice_fingerprint(
        own_tweets=own_tweets,
        linkedin_text=linkedin_text,
        publications_text=publications_text,
        handle=x_handle,
    )

    _store_fingerprint(fingerprint)
    print("\nVoice fingerprint built and saved to MEMORY.md")
    print("\nHere's what the system learned about your writing:\n")
    print(fingerprint)
    print("\n" + "=" * 60 + "\n")
    return fingerprint


async def _build_voice_fingerprint(
    own_tweets: list[dict[str, str]],
    linkedin_text: str,
    publications_text: str,
    handle: str,
) -> str:
    """Use Claude to analyze writing samples and build a voice fingerprint."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    tweet_samples = "\n".join(tweet.get("text", "") for tweet in own_tweets[:100])

    prompt = f"""Analyze the writing style of {handle} based on their actual posts and writing.

THEIR TWEETS (sample of 100):
{tweet_samples[:8000]}

THEIR LINKEDIN:
{linkedin_text[:2000]}

THEIR PUBLICATIONS/ARTICLES:
{publications_text[:3000]}

Build a detailed voice fingerprint. Return ONLY this structured format, nothing else:

VOICE_FINGERPRINT:
  avg_sentence_length: [short/medium/long] ([X-Y words typically])
  humor_style: [dry/sarcastic/self-deprecating/none/deadpan/observational]
  technical_depth: [high/medium/low] - [one sentence description]
  signature_phrases: [list 3-5 actual phrases or words they use often]
  never_uses: [list 5-8 words/phrases they clearly avoid]
  structure_patterns: [how they typically open and close posts]
  question_style: [how they ask questions if at all]
  topics_they_own: [2-3 specific areas where they sound most confident]
  tone_default: [one sentence capturing their overall tone]
  example_best_tweet: [pick their single best tweet from the samples that shows their voice perfectly]
  what_makes_them_sound_like_them: [2-3 sentences on the most distinctive things about their writing]"""

    def _call_claude() -> str:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    return await asyncio.to_thread(_call_claude)


def _store_fingerprint(fingerprint: str) -> None:
    """Store the voice fingerprint in MEMORY.md Section 1."""
    path = ensure_memory_file()
    content = path.read_text(encoding="utf-8")

    if "VOICE_FINGERPRINT:" in content:
        content = re.sub(
            r"VOICE_FINGERPRINT:\s*.*?(?=\n## SECTION|\Z)",
            fingerprint.strip() + "\n",
            content,
            flags=re.DOTALL,
        )
    else:
        content = content.replace(
            "AVOID_PATTERNS:",
            fingerprint.strip() + "\n\nAVOID_PATTERNS:",
        )
    path.write_text(content, encoding="utf-8")


def get_voice_context_for_prompt(memory: dict) -> str:
    """Build a voice instruction block for injection into agent prompts."""
    fingerprint = memory.get("voice_fingerprint", "")
    if not fingerprint:
        return ""

    return f"""
WRITE IN THIS PERSON'S EXACT VOICE:
{fingerprint}

Study their example_best_tweet carefully. Every reply should sound like it
came from the same person who wrote that tweet. Not similar - identical voice.
If you're unsure, err toward shorter and more direct rather than longer and more elaborate.
"""
