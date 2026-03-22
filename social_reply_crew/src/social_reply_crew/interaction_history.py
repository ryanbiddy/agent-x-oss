from __future__ import annotations

import sqlite3

from social_reply_crew.db import get_default_database_path


def get_interaction_history(handle: str) -> dict:
    """Get prior interaction history with a specific account."""
    clean_handle = handle.lstrip("@")
    try:
        conn = sqlite3.connect(get_default_database_path())
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute(
            """
            SELECT COUNT(*) as total_replies,
                   MAX(created_at) as last_reply_date,
                   MAX(reply_text) as last_reply_text
            FROM engagement_log
            WHERE source_handle IN (?, ?)
              AND status IN ('approved', 'sent')
            """,
            (clean_handle, f"@{clean_handle}"),
        )
        row = cur.fetchone()
        conn.close()

        if row and row["total_replies"] > 0:
            return {
                "replied_before": True,
                "total_replies": row["total_replies"],
                "last_reply_date": row["last_reply_date"],
                "last_reply_text": row["last_reply_text"],
            }
    except Exception:
        pass

    return {"replied_before": False, "total_replies": 0}


def format_context_card(
    handle: str,
    user_context: dict,
    interaction: dict,
    tweet_score: float,
    why_surfaced: str,
) -> str:
    """Format the user context card for display."""
    lines = [
        f"\n{'-' * 60}",
        f"  {handle}",
    ]

    if user_context.get("followers") not in {None, "", "unknown"}:
        lines.append(f"  Followers: {user_context['followers']}")

    if user_context.get("bio"):
        bio = str(user_context["bio"]).strip()
        if len(bio) > 80:
            bio = bio[:80].rstrip() + "..."
        lines.append(f"  Bio: {bio}")

    if interaction.get("replied_before"):
        lines.append(f"  You've replied: {interaction['total_replies']} times")
        if interaction.get("last_reply_date"):
            lines.append(f"  Last: {str(interaction['last_reply_date'])[:10]}")
    else:
        lines.append("  First time replying to this account")

    if tweet_score:
        lines.append(f"  Relevance score: {tweet_score:.1f}")
    lines.append(f"  Why surfaced: {why_surfaced or 'High focus match'}")
    lines.append(f"{'-' * 60}\n")

    return "\n".join(lines)
