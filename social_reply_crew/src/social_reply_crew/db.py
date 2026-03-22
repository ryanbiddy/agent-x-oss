from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from statistics import median
from typing import Callable

from dotenv import load_dotenv

from social_reply_crew.models import MetricsRefreshReport, ReplyMetricSnapshot, StoredReply

APP_DIR = Path(__file__).resolve().parents[2]
load_dotenv(APP_DIR / ".env")


def get_default_database_path() -> Path:
    raw_path = os.getenv("DB_PATH") or os.getenv("X_DATABASE_PATH")
    if raw_path:
        path = Path(raw_path)
        return path if path.is_absolute() else (APP_DIR / path).resolve()
    data_dir = APP_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "social_reply_memory.db"


class ReplyMemoryStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_url TEXT NOT NULL,
                    original_tweet TEXT NOT NULL,
                    generated_reply TEXT NOT NULL,
                    engagement_score INTEGER NOT NULL DEFAULT 0,
                    timestamp TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_replies_post_url ON replies(post_url)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_replies_score ON replies(engagement_score DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS engagement_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_handle TEXT NOT NULL,
                    tweet_url TEXT NOT NULL,
                    tweet_text TEXT NOT NULL,
                    reply_text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_engagement_log_handle ON engagement_log(source_handle)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_engagement_log_created_at ON engagement_log(created_at DESC)"
            )
            connection.commit()

    def record_reply(
        self,
        post_url: str,
        original_tweet: str,
        generated_reply: str,
        engagement_score: int = 0,
    ) -> int:
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO replies (post_url, original_tweet, generated_reply, engagement_score, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (post_url, original_tweet, generated_reply, engagement_score, timestamp),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def get_recent_replies(self, limit: int = 100) -> list[StoredReply]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, post_url, original_tweet, generated_reply, engagement_score, timestamp
                FROM replies
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_reply(row) for row in rows]

    def record_interaction(
        self,
        source_handle: str,
        tweet_url: str,
        tweet_text: str,
        reply_text: str,
        status: str = "sent",
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO engagement_log (
                    source_handle, tweet_url, tweet_text, reply_text, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    source_handle.strip() or "unknown",
                    tweet_url,
                    tweet_text,
                    reply_text,
                    status,
                    created_at,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def get_top_performing_replies(self, limit: int = 12) -> list[StoredReply]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, post_url, original_tweet, generated_reply, engagement_score, timestamp
                FROM replies
                ORDER BY engagement_score DESC, timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_reply(row) for row in rows]

    def build_performance_payload(self, limit: int = 12) -> dict[str, object]:
        top_replies = self.get_top_performing_replies(limit=limit)
        if not top_replies:
            return {
                "summary": "No historical replies are stored yet. Use concise, useful, opinionated replies and treat the first batch as exploration data.",
                "rules": [
                    "Keep replies crisp and high-signal.",
                    "Favor concrete observations over generic praise.",
                    "Offer a distinct angle in the first sentence.",
                    "Avoid sounding automated or overly promotional.",
                ],
                "weighted_metrics": {
                    "sample_count": 0,
                    "avg_characters": 0,
                    "question_rate": 0,
                    "exclamation_rate": 0,
                    "line_break_rate": 0,
                },
                "high_performing_examples": [],
            }

        weighted_metrics = self._weighted_style_metrics(top_replies)
        rules = self._suggest_rules(weighted_metrics, top_replies)
        return {
            "summary": (
                f"Derived from {len(top_replies)} replies, with higher engagement replies weighted more heavily."
            ),
            "rules": rules,
            "weighted_metrics": weighted_metrics,
            "high_performing_examples": [
                reply.model_dump(mode="json") for reply in top_replies[:6]
            ],
        }

    def refresh_from_snapshots(
        self,
        snapshots: list[ReplyMetricSnapshot],
        recent_history_limit: int = 150,
    ) -> MetricsRefreshReport:
        recent_replies = self.get_recent_replies(limit=recent_history_limit)
        matched_rows = 0
        updated_rows = 0
        used_reply_ids: set[int] = set()
        unmatched_samples: list[str] = []

        with self._connect() as connection:
            for snapshot in snapshots:
                best_reply = None
                best_score = 0.0
                for reply in recent_replies:
                    if reply.id in used_reply_ids:
                        continue
                    match_score = self._text_match_score(reply.generated_reply, snapshot.reply_text)
                    if match_score > best_score:
                        best_score = match_score
                        best_reply = reply

                if best_reply is None or best_score < 0.72:
                    unmatched_samples.append(snapshot.reply_text[:140])
                    continue

                matched_rows += 1
                used_reply_ids.add(best_reply.id)
                if best_reply.engagement_score != snapshot.engagement_score:
                    connection.execute(
                        "UPDATE replies SET engagement_score = ? WHERE id = ?",
                        (snapshot.engagement_score, best_reply.id),
                    )
                    updated_rows += 1

            connection.commit()

        return MetricsRefreshReport(
            scanned_replies=len(snapshots),
            updated_rows=updated_rows,
            matched_rows=matched_rows,
            unmatched_samples=unmatched_samples[:5],
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _row_to_reply(row: sqlite3.Row) -> StoredReply:
        return StoredReply(
            id=int(row["id"]),
            post_url=str(row["post_url"]),
            original_tweet=str(row["original_tweet"]),
            generated_reply=str(row["generated_reply"]),
            engagement_score=int(row["engagement_score"]),
            timestamp=datetime.fromisoformat(str(row["timestamp"])),
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        without_urls = re.sub(r"https?://\S+", "", text)
        lowered = without_urls.lower().replace("\u00a0", " ")
        collapsed = re.sub(r"\s+", " ", lowered)
        return collapsed.strip()

    def _text_match_score(self, left: str, right: str) -> float:
        normalized_left = self._normalize_text(left)
        normalized_right = self._normalize_text(right)
        if not normalized_left or not normalized_right:
            return 0.0
        if normalized_left == normalized_right:
            return 1.0
        shorter, longer = sorted((normalized_left, normalized_right), key=len)
        if shorter and shorter in longer:
            return len(shorter) / len(longer)
        return SequenceMatcher(a=normalized_left, b=normalized_right).ratio()

    @staticmethod
    def _weighted_style_metrics(replies: list[StoredReply]) -> dict[str, float | int]:
        weights = [max(reply.engagement_score, 1) for reply in replies]
        total_weight = sum(weights)

        def weighted_rate(predicate: Callable[[StoredReply], bool]) -> float:
            score = 0
            for reply, weight in zip(replies, weights, strict=True):
                if predicate(reply):
                    score += weight
            return round(score / total_weight, 3)

        avg_characters = round(
            sum(len(reply.generated_reply) * weight for reply, weight in zip(replies, weights, strict=True))
            / total_weight,
            1,
        )
        avg_words = round(
            sum(len(reply.generated_reply.split()) * weight for reply, weight in zip(replies, weights, strict=True))
            / total_weight,
            1,
        )

        return {
            "sample_count": len(replies),
            "avg_characters": avg_characters,
            "avg_words": avg_words,
            "median_engagement": int(median(reply.engagement_score for reply in replies)),
            "question_rate": weighted_rate(lambda reply: "?" in reply.generated_reply),
            "exclamation_rate": weighted_rate(lambda reply: "!" in reply.generated_reply),
            "line_break_rate": weighted_rate(lambda reply: "\n" in reply.generated_reply),
            "emoji_rate": weighted_rate(
                lambda reply: any(ord(character) > 127 for character in reply.generated_reply)
            ),
            "statement_open_rate": weighted_rate(
                lambda reply: not reply.generated_reply.strip().lower().startswith(("why", "how", "what"))
            ),
        }

    @staticmethod
    def _suggest_rules(
        weighted_metrics: dict[str, float | int],
        replies: list[StoredReply],
    ) -> list[str]:
        avg_characters = float(weighted_metrics.get("avg_characters", 0))
        question_rate = float(weighted_metrics.get("question_rate", 0))
        exclamation_rate = float(weighted_metrics.get("exclamation_rate", 0))
        line_break_rate = float(weighted_metrics.get("line_break_rate", 0))
        emoji_rate = float(weighted_metrics.get("emoji_rate", 0))

        rules = [
            "Anchor the first sentence in a specific observation from the original post.",
            f"Keep the typical reply length near {int(avg_characters or 180)} characters unless a shorter punch lands better.",
        ]
        if question_rate >= 0.4:
            rules.append("Use a pointed question when it sharpens the take instead of asking for engagement bait.")
        else:
            rules.append("Prefer declarative punch over question-heavy replies.")
        if exclamation_rate >= 0.3:
            rules.append("A touch of intensity is acceptable, but keep it selective and earned.")
        else:
            rules.append("Keep punctuation controlled; intensity should come from the idea, not excitement marks.")
        if line_break_rate >= 0.25:
            rules.append("Short two-beat cadence is working, so a strategic line break is allowed.")
        else:
            rules.append("Favor a clean one-block reply instead of multi-line formatting.")
        if emoji_rate < 0.15:
            rules.append("Avoid leaning on emojis unless the original post clearly invites it.")

        if replies:
            rules.append(
                f"Mirror the tone of the strongest historical reply: \"{replies[0].generated_reply[:120]}\""
            )
        return rules


def save_approved_reply(
    source_handle: str,
    tweet_url: str,
    tweet_text: str,
    reply_text: str,
) -> None:
    store = ReplyMemoryStore(get_default_database_path())
    store.initialize()
    store.record_reply(
        post_url=tweet_url,
        original_tweet=tweet_text,
        generated_reply=reply_text,
        engagement_score=0,
    )
    store.record_interaction(
        source_handle=source_handle,
        tweet_url=tweet_url,
        tweet_text=tweet_text,
        reply_text=reply_text,
        status="approved",
    )
