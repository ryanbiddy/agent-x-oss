from __future__ import annotations

import argparse
import time

from social_reply_crew.agents import SocialReplyCrew
from social_reply_crew.browser_tools import XBrowserService
from social_reply_crew.config import AppConfig
from social_reply_crew.db import ReplyMemoryStore
from social_reply_crew.digest import present_digest_and_collect_choices
from social_reply_crew.exceptions import DomChangedError, XAutomationError


def cli() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    config = AppConfig.from_env()
    memory_store = ReplyMemoryStore(config.database_path)
    memory_store.initialize()
    browser_service = XBrowserService(config=config)

    command = args.command or "run"
    if command == "run":
        _run_main_flow(
            config=config,
            browser_service=browser_service,
            memory_store=memory_store,
            refresh_first=args.refresh_first,
            focus_override=args.focus,
        )
        return
    if command == "refresh-metrics":
        report = refresh_engagement_metrics(browser_service, memory_store)
        print(
            f"Scanned {report.scanned_replies} replies, matched {report.matched_rows}, updated {report.updated_rows} rows."
        )
        if report.unmatched_samples:
            print("Unmatched samples:")
            for sample in report.unmatched_samples:
                print(f"- {sample}")
        return
    if command == "watch-metrics":
        watch_metrics(
            browser_service=browser_service,
            memory_store=memory_store,
            interval_minutes=args.interval_minutes,
        )
        return
    raise ValueError(f"Unsupported command: {command}")


def refresh_engagement_metrics(
    browser_service: XBrowserService,
    memory_store: ReplyMemoryStore,
):
    snapshots = browser_service.collect_own_reply_metrics_sync()
    return memory_store.refresh_from_snapshots(snapshots)


def watch_metrics(
    browser_service: XBrowserService,
    memory_store: ReplyMemoryStore,
    interval_minutes: int,
) -> None:
    while True:
        report = refresh_engagement_metrics(browser_service, memory_store)
        print(
            f"[refresh] scanned={report.scanned_replies} matched={report.matched_rows} updated={report.updated_rows}"
        )
        time.sleep(interval_minutes * 60)


def _run_main_flow(
    config: AppConfig,
    browser_service: XBrowserService,
    memory_store: ReplyMemoryStore,
    refresh_first: bool,
    focus_override: str | None,
) -> None:
    if refresh_first:
        try:
            report = refresh_engagement_metrics(browser_service, memory_store)
            print(
                f"Engagement refresh complete: scanned {report.scanned_replies}, matched {report.matched_rows}, updated {report.updated_rows}."
            )
        except DomChangedError:
            print(
                "Skipping engagement refresh — could not load profile page. Run without --refresh-first to skip this step."
            )

    crew = SocialReplyCrew(
        config=config,
        browser_service=browser_service,
        memory_store=memory_store,
    )
    digest = crew.build_digest(focus_override=focus_override)
    selections = present_digest_and_collect_choices(digest)

    for selection in selections:
        if selection.chosen_option is None:
            print(f"Skipped {selection.recommendation.post_url}")
            continue

        try:
            browser_service.post_reply_sync(
                post_url=selection.recommendation.post_url,
                reply_text=selection.chosen_option.reply_text,
            )
            memory_store.record_reply(
                post_url=selection.recommendation.post_url,
                original_tweet=selection.recommendation.original_text,
                generated_reply=selection.chosen_option.reply_text,
                engagement_score=0,
            )
            print(f"Posted reply to {selection.recommendation.post_url}")
        except XAutomationError as exc:
            print(f"Failed to post reply to {selection.recommendation.post_url}: {exc}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="social-reply-crew",
        description="CrewAI-driven X social listening and reply automation.",
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Draft replies and optionally post them to X.")
    run_parser.add_argument(
        "--focus",
        default=None,
        help="Optional focus override used when selecting relevant timeline posts.",
    )
    run_parser.add_argument(
        "--refresh-first",
        action="store_true",
        help="Refresh historical engagement metrics before drafting new replies.",
    )

    subparsers.add_parser(
        "refresh-metrics",
        help="Scrape the authenticated user's Replies tab and update SQLite engagement scores.",
    )

    watch_parser = subparsers.add_parser(
        "watch-metrics",
        help="Continuously refresh engagement metrics on a fixed interval.",
    )
    watch_parser.add_argument(
        "--interval-minutes",
        type=int,
        default=30,
        help="How often to refresh reply engagement metrics.",
    )

    return parser
