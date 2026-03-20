from __future__ import annotations

import json
from typing import TypeVar

from crewai import Agent, Crew, Process, Task
from crewai.tools import BaseTool
from pydantic import BaseModel, PrivateAttr

from social_reply_crew.browser_tools import XBrowserService
from social_reply_crew.config import AppConfig
from social_reply_crew.db import ReplyMemoryStore
from social_reply_crew.models import PerformanceRuleset, ReplyDigest, TimelineScoutReport, ToneAnalysisReport

ModelType = TypeVar("ModelType", bound=BaseModel)


class TimelineScoutBrowserTool(BaseTool):
    name: str = "timeline_scout_browser"
    description: str = (
        "Read the authenticated user's For You timeline on X and return candidate posts as JSON."
    )

    _browser_service: XBrowserService = PrivateAttr()

    def __init__(self, browser_service: XBrowserService) -> None:
        super().__init__()
        self._browser_service = browser_service

    def _run(self) -> str:
        posts = self._browser_service.collect_timeline_candidates_sync()
        return json.dumps(
            {
                "candidate_count": len(posts),
                "posts": [post.model_dump(mode="json") for post in posts],
            },
            indent=2,
        )


class ToneSamplesBrowserTool(BaseTool):
    name: str = "tone_samples_browser"
    description: str = (
        "Visit inspirational X accounts on the Replies tab and return their recent high-signal replies as JSON."
    )

    _browser_service: XBrowserService = PrivateAttr()

    def __init__(self, browser_service: XBrowserService) -> None:
        super().__init__()
        self._browser_service = browser_service

    def _run(self) -> str:
        samples = self._browser_service.collect_inspiration_samples_sync()
        return json.dumps(
            {
                "sample_count": len(samples),
                "samples": [sample.model_dump(mode="json") for sample in samples],
            },
            indent=2,
        )


class HistoricalPerformanceTool(BaseTool):
    name: str = "historical_performance"
    description: str = (
        "Read the local SQLite reply history and return weighted performance signals plus top examples as JSON."
    )

    _memory_store: ReplyMemoryStore = PrivateAttr()

    def __init__(self, memory_store: ReplyMemoryStore) -> None:
        super().__init__()
        self._memory_store = memory_store

    def _run(self) -> str:
        payload = self._memory_store.build_performance_payload()
        return json.dumps(payload, indent=2)


class SocialReplyCrew:
    def __init__(
        self,
        config: AppConfig,
        browser_service: XBrowserService,
        memory_store: ReplyMemoryStore,
    ) -> None:
        self.config = config
        self.browser_service = browser_service
        self.memory_store = memory_store

    def build_digest(self, focus_override: str | None = None) -> ReplyDigest:
        focus_brief = focus_override or self.config.focus_brief
        timeline_tool = TimelineScoutBrowserTool(browser_service=self.browser_service)
        tone_tool = ToneSamplesBrowserTool(browser_service=self.browser_service)
        performance_tool = HistoricalPerformanceTool(memory_store=self.memory_store)

        timeline_scout = Agent(
            role="Timeline Scout",
            goal="Find the highest-value posts on the authenticated For You timeline for the user to reply to.",
            backstory=(
                "You scan noisy timelines, ignore filler, and surface the posts that are most worth engaging."
            ),
            llm=self.config.crew_model,
            tools=[timeline_tool],
            allow_delegation=False,
            max_iter=3,
            verbose=False,
        )

        tone_analyzer = Agent(
            role="Tone Analyzer",
            goal="Learn repeatable reply style patterns from inspirational accounts and use them without sounding derivative.",
            backstory=(
                "You reverse engineer cadence, rhythm, sentence shape, and humor from high-performing replies, then translate that into reusable style guidance."
            ),
            llm=self.config.crew_model,
            tools=[tone_tool],
            allow_delegation=False,
            max_iter=3,
            verbose=False,
        )

        performance_analyst = Agent(
            role="Performance Analyst",
            goal="Turn reply history into a dynamic ruleset that heavily weights what already wins engagement.",
            backstory=(
                "You behave like a reinforcement loop. You look at historical engagement, identify what style compounds, and convert that into constraints for future drafts."
            ),
            llm=self.config.crew_model,
            tools=[performance_tool],
            allow_delegation=False,
            max_iter=3,
            verbose=False,
        )

        scout_task = Task(
            description=(
                "Use the timeline_scout_browser tool once to collect candidate posts from the authenticated For You timeline. "
                f"Select exactly {self.config.timeline_post_limit} posts that are most relevant to these focus areas: {focus_brief}. "
                "Prefer posts that are timely, substantive, and naturally invite a high-value reply. "
                "Return valid JSON with keys focus_summary and posts. Each post must include author, text, link, and a concise reason."
            ),
            expected_output=(
                f"JSON with a focus_summary string and exactly {self.config.timeline_post_limit} selected posts."
            ),
            agent=timeline_scout,
            output_pydantic=TimelineScoutReport,
        )

        tone_task = Task(
            description=(
                "Use the tone_samples_browser tool to gather reply examples from the configured inspirational accounts. "
                "Extract practical style rules about cadence, sentence length, rhythm, specificity, humor, and how the reply opens. "
                "Return valid JSON with keys style_summary, rules, and signal_examples."
            ),
            expected_output="JSON with a style_summary, a non-empty rules list, and signal_examples.",
            agent=tone_analyzer,
            output_pydantic=ToneAnalysisReport,
        )

        performance_task = Task(
            description=(
                "Use the historical_performance tool to inspect the SQLite reply history. "
                "Create a dynamic ruleset that heavily prioritizes styles found in higher-engagement replies, while still noting confidence limits when the data is sparse. "
                "Return valid JSON with keys summary, rules, weighted_metrics, and high_performing_examples."
            ),
            expected_output="JSON with a summary, rules, weighted metrics, and the best historical reply examples.",
            agent=performance_analyst,
            output_pydantic=PerformanceRuleset,
        )

        draft_task = Task(
            description=(
                "Using the context from the timeline scout, tone analyzer, and performance analyst, draft exactly two reply options for each selected post. "
                "Option 1 should lean witty, rhythmic, and socially sharp. "
                "Option 2 should lean analytical, insight-dense, and strategically useful. "
                f"Keep each reply under {self.config.reply_character_limit} characters. "
                "Do not use hashtags. Avoid generic praise, bot-sounding intros, or obvious engagement bait. "
                "Heavily respect the historical ruleset when it conflicts with stylistic flourish. "
                "Return valid JSON with keys global_guidance and recommendations. "
                "Each recommendation must include post_url, author, original_text, and exactly two options. "
                "Each option must include style_label, reply_text, and rationale."
            ),
            expected_output="JSON digest containing two reply options per selected post.",
            agent=tone_analyzer,
            context=[scout_task, tone_task, performance_task],
            output_pydantic=ReplyDigest,
        )

        crew = Crew(
            agents=[timeline_scout, tone_analyzer, performance_analyst],
            tasks=[scout_task, tone_task, performance_task, draft_task],
            process=Process.sequential,
            verbose=False,
        )
        crew.kickoff()
        digest = self._coerce_task_output(draft_task, ReplyDigest)
        digest.recommendations = digest.recommendations[: self.config.timeline_post_limit]
        return digest

    @staticmethod
    def _coerce_task_output(task: Task, model_type: type[ModelType]) -> ModelType:
        task_output = getattr(task, "output", None)
        if task_output is None:
            raise RuntimeError(f"Task '{task.description[:40]}' did not produce output.")

        pydantic_output = getattr(task_output, "pydantic", None)
        if isinstance(pydantic_output, model_type):
            return pydantic_output

        json_dict_output = getattr(task_output, "json_dict", None)
        if isinstance(json_dict_output, dict):
            return model_type.model_validate(json_dict_output)

        raw_output = getattr(task_output, "raw", None)
        if isinstance(raw_output, str):
            return model_type.model_validate_json(raw_output)

        raise RuntimeError(f"Unable to coerce task output into {model_type.__name__}.")
