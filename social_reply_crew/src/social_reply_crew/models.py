from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TimelinePost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    author: str
    text: str
    link: str
    reason: str | None = None


class TimelineScoutReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focus_summary: str
    posts: list[TimelinePost] = Field(min_length=1)


class InspirationalReplySample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handle: str
    reply_text: str
    likes: int = 0
    retweets: int = 0
    link: str | None = None


class ToneAnalysisReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style_summary: str
    rules: list[str] = Field(min_length=1)
    signal_examples: list[str] = Field(default_factory=list)


class StoredReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    post_url: str
    original_tweet: str
    generated_reply: str
    engagement_score: int
    timestamp: datetime


class PerformanceRuleset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    rules: list[str] = Field(min_length=1)
    weighted_metrics: dict[str, Any] = Field(default_factory=dict)
    high_performing_examples: list[StoredReply] = Field(default_factory=list)


class ReplyOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style_label: str
    reply_text: str
    rationale: str


class ReplyRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    post_url: str
    author: str
    original_text: str
    options: list[ReplyOption] = Field(min_length=2, max_length=2)


class ReplyDigest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    global_guidance: str
    recommendations: list[ReplyRecommendation] = Field(min_length=1)


class ReplyMetricSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply_text: str
    reply_url: str | None = None
    likes: int = 0
    retweets: int = 0

    @property
    def engagement_score(self) -> int:
        return self.likes + self.retweets


class MetricsRefreshReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanned_replies: int
    updated_rows: int
    matched_rows: int
    unmatched_samples: list[str] = Field(default_factory=list)


@dataclass(slots=True)
class SelectedReply:
    recommendation: ReplyRecommendation
    chosen_option: ReplyOption | None
