from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager
from typing import Any

from social_reply_crew.config import AppConfig
from social_reply_crew.exceptions import (
    AuthenticationRequiredError,
    DomChangedError,
    RateLimitError,
    ReplyPostError,
)
from social_reply_crew.models import InspirationalReplySample, ReplyMetricSnapshot, TimelinePost

try:
    from browser_use import Browser
except ImportError as exc:  # pragma: no cover - import guard for environments without dependencies
    Browser = None  # type: ignore[assignment]
    BROWSER_IMPORT_ERROR = exc
else:
    BROWSER_IMPORT_ERROR = None


class XBrowserService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def collect_timeline_candidates_sync(self) -> list[TimelinePost]:
        return asyncio.run(self.collect_timeline_candidates())

    def collect_inspiration_samples_sync(self) -> list[InspirationalReplySample]:
        return asyncio.run(self.collect_inspiration_samples())

    def post_reply_sync(self, post_url: str, reply_text: str) -> None:
        asyncio.run(self.post_reply(post_url=post_url, reply_text=reply_text))

    def collect_own_reply_metrics_sync(self) -> list[ReplyMetricSnapshot]:
        return asyncio.run(self.collect_own_reply_metrics())

    def get_user_context_sync(self, handle: str) -> dict[str, Any]:
        return asyncio.run(self.get_user_context(handle))

    def scrape_account_tweets_for_voice_sync(self, handle: str, limit: int = 200) -> list[dict[str, str]]:
        return asyncio.run(self.scrape_account_tweets_for_voice(handle=handle, limit=limit))

    def scrape_linkedin_about_sync(self, linkedin_url: str) -> str:
        return asyncio.run(self.scrape_linkedin_about(linkedin_url))

    def scrape_page_text_sync(self, url: str) -> str:
        return asyncio.run(self.scrape_page_text(url))

    async def collect_timeline_candidates(self) -> list[TimelinePost]:
        async with self._browser_session("https://x.com/home") as page:
            await self._ensure_authenticated(page)
            if await self._requires_login(page):
                await self._login(page, destination_url="https://x.com/home")
            await self._wait_for_timeline(page)

            unique_posts: dict[str, TimelinePost] = {}
            for _ in range(4):
                for post in await self._extract_timeline_posts(page):
                    if post.link and post.text and post.link not in unique_posts:
                        unique_posts[post.link] = post
                if len(unique_posts) >= self.config.timeline_candidate_limit:
                    break
                await page.evaluate("() => window.scrollBy(0, window.innerHeight * 0.85)")
                await asyncio.sleep(1.5)
                await self._guard_page(page)

            posts = list(unique_posts.values())[: self.config.timeline_candidate_limit]
            if not posts:
                raise DomChangedError("No timeline posts were extracted from the authenticated home feed.")
            return posts

    async def collect_inspiration_samples(self) -> list[InspirationalReplySample]:
        samples: list[InspirationalReplySample] = []
        async with self._browser_session("https://x.com/home") as page:
            await self._ensure_authenticated(page)
            if await self._requires_login(page):
                await self._login(page, destination_url="https://x.com/home")
            for handle in self.config.inspirational_handles:
                target_url = f"https://x.com/{handle}/with_replies"
                await page.goto(target_url)
                await asyncio.sleep(2.5)
                await self._guard_page(page)
                if await self._requires_login(page):
                    await self._login(page, destination_url=target_url)
                await self._wait_for_tweets(page)

                account_samples: list[InspirationalReplySample] = []
                for _ in range(3):
                    account_samples.extend(await self._extract_reply_samples(page, handle=handle))
                    if len(account_samples) >= self.config.inspiration_replies_per_account * 2:
                        break
                    await page.evaluate("() => window.scrollBy(0, window.innerHeight * 0.85)")
                    await asyncio.sleep(1.5)

                unique_by_link: dict[str, InspirationalReplySample] = {}
                for sample in sorted(
                    account_samples,
                    key=lambda item: (item.likes + item.retweets, len(item.reply_text)),
                    reverse=True,
                ):
                    dedupe_key = sample.link or sample.reply_text
                    if dedupe_key not in unique_by_link and sample.reply_text:
                        unique_by_link[dedupe_key] = sample

                samples.extend(
                    list(unique_by_link.values())[: self.config.inspiration_replies_per_account]
                )

        if not samples:
            raise DomChangedError("No inspirational reply samples were extracted from the configured handles.")
        return samples

    async def post_reply(self, post_url: str, reply_text: str) -> None:
        if len(reply_text) > self.config.reply_character_limit:
            raise ReplyPostError(
                f"Reply exceeds the configured limit of {self.config.reply_character_limit} characters."
            )

        async with self._browser_session(post_url) as page:
            await self._ensure_authenticated(page)
            await page.goto(post_url)
            await asyncio.sleep(2.0)
            await self._guard_page(page)
            await self._wait_for_tweets(page)

            composer = await self._first_selector(
                page,
                [
                    "div[data-testid='tweetTextarea_0']",
                    "div[role='textbox'][contenteditable='true']",
                ],
            )
            if composer is None:
                reply_button = await self._first_selector(
                    page,
                    [
                        "button[data-testid='reply']",
                        "div[data-testid='reply']",
                    ],
                )
                if reply_button is None:
                    raise ReplyPostError("Reply composer could not be opened on the target post.")
                await reply_button.click()
                await asyncio.sleep(1.0)
                composer = await self._wait_for_selector(
                    page,
                    [
                        "div[data-testid='tweetTextarea_0']",
                        "div[role='textbox'][contenteditable='true']",
                    ],
                )

            try:
                await composer.click()
                await composer.fill(reply_text, clear=True)
            except Exception:
                inserted = await page.evaluate(
                    """
                    (replyText) => {
                      const composer =
                        document.querySelector("div[data-testid='tweetTextarea_0']") ||
                        document.querySelector("div[role='textbox'][contenteditable='true']");
                      if (!composer) return false;
                      composer.focus();
                      const selection = window.getSelection();
                      const range = document.createRange();
                      range.selectNodeContents(composer);
                      range.collapse(false);
                      selection.removeAllRanges();
                      selection.addRange(range);
                      const inserted = document.execCommand("insertText", false, replyText);
                      if (!inserted) {
                        composer.textContent = replyText;
                        composer.dispatchEvent(
                          new InputEvent("input", {
                            bubbles: true,
                            cancelable: true,
                            data: replyText,
                            inputType: "insertText"
                          })
                        );
                      }
                      return true;
                    }
                    """,
                    reply_text,
                )
                if not self._to_bool(inserted):
                    raise ReplyPostError("Reply text could not be inserted into the composer.")

            await asyncio.sleep(0.8)
            clicked = await page.evaluate(
                """
                () => {
                  const button =
                    document.querySelector("button[data-testid='tweetButtonInline']") ||
                    document.querySelector("button[data-testid='tweetButton']");
                  if (!button) return false;
                  if (button.getAttribute("aria-disabled") === "true") return false;
                  button.click();
                  return true;
                }
                """
            )
            if not self._to_bool(clicked):
                raise ReplyPostError("Reply send button was not available or remained disabled.")

            await asyncio.sleep(3.0)
            await self._guard_page(page)

    async def collect_own_reply_metrics(self) -> list[ReplyMetricSnapshot]:
        async with self._browser_session(self.config.x_replies_tab_url) as page:
            await self._ensure_authenticated(page)
            await page.goto(self.config.x_replies_tab_url)
            await asyncio.sleep(2.5)
            await self._guard_page(page)
            if await self._requires_login(page):
                await self._login(page, destination_url=self.config.x_replies_tab_url)
            await self._wait_for_tweets(page)

            unique_replies: dict[str, ReplyMetricSnapshot] = {}
            for _ in range(4):
                for snapshot in await self._extract_reply_metrics(page):
                    key = snapshot.reply_url or snapshot.reply_text
                    if key and key not in unique_replies:
                        unique_replies[key] = snapshot
                if len(unique_replies) >= self.config.refresh_limit:
                    break
                await page.evaluate("() => window.scrollBy(0, window.innerHeight * 0.9)")
                await asyncio.sleep(1.2)

            return list(unique_replies.values())[: self.config.refresh_limit]

    async def scrape_account_tweets_for_voice(
        self,
        handle: str,
        limit: int = 200,
    ) -> list[dict[str, str]]:
        clean_handle = handle.lstrip("@")
        target_url = f"https://x.com/{clean_handle}"
        async with self._browser_session(target_url) as page:
            await self._ensure_logged_in(page)
            await page.goto(target_url)
            await asyncio.sleep(2.5)
            await self._guard_page(page)
            await self._wait_for_tweets(page)

            unique_tweets: dict[str, dict[str, str]] = {}
            for _ in range(10):
                payload = await page.evaluate(
                    """
                    (cleanHandle) => JSON.stringify(
                      Array.from(document.querySelectorAll("article[data-testid='tweet']")).map((article) => {
                        const textNodes = Array.from(article.querySelectorAll("div[data-testid='tweetText']"));
                        const text = textNodes.map((node) => node.innerText || "").join("\\n").trim();
                        const linkNode = Array.from(article.querySelectorAll("a[href*='/status/']")).find((anchor) => {
                          const href = anchor.getAttribute("href") || "";
                          return href.startsWith(`/${cleanHandle}/status/`) && !href.includes("/analytics");
                        });
                        if (!text || !linkNode) return null;
                        return {
                          text,
                          link: linkNode.href.split("?")[0]
                        };
                      }).filter(Boolean)
                    )
                    """,
                    clean_handle,
                )
                for item in json.loads(payload or "[]"):
                    text = str(item.get("text") or "").strip()
                    if len(text) < 10:
                        continue
                    unique_tweets.setdefault(
                        text,
                        {
                            "text": text,
                            "link": str(item.get("link") or "").strip(),
                        },
                    )
                if len(unique_tweets) >= limit:
                    break
                await page.evaluate("() => window.scrollBy(0, window.innerHeight * 0.9)")
                await asyncio.sleep(1.5)
                await self._guard_page(page)

            return list(unique_tweets.values())[:limit]

    async def scrape_linkedin_about(self, linkedin_url: str) -> str:
        async with self._browser_session(linkedin_url) as page:
            await page.goto(linkedin_url)
            await asyncio.sleep(3.0)
            raw_text = await page.evaluate(
                """
                () => {
                  const selectors = [
                    ".about-section",
                    "#about",
                    "[id*='about']",
                    "[data-generated-suggestion-target]"
                  ];
                  for (const selector of selectors) {
                    const node = document.querySelector(selector);
                    if (node && (node.innerText || "").trim()) {
                      return node.innerText.trim();
                    }
                  }
                  return document.body ? document.body.innerText : "";
                }
                """
            )
            return raw_text if isinstance(raw_text, str) else str(raw_text or "")

    async def scrape_page_text(self, url: str) -> str:
        async with self._browser_session(url) as page:
            await page.goto(url)
            await asyncio.sleep(2.0)
            return await self._body_text(page)

    async def get_user_context(self, handle: str) -> dict[str, Any]:
        clean_handle = handle.lstrip("@")
        target_url = f"https://x.com/{clean_handle}"
        context: dict[str, Any] = {
            "handle": f"@{clean_handle}" if clean_handle else handle,
            "followers": "unknown",
            "bio": "",
            "is_followed_back": False,
        }
        if not clean_handle:
            return context

        try:
            async with self._browser_session(target_url) as page:
                await self._ensure_logged_in(page)
                await page.goto(target_url)
                await asyncio.sleep(2.5)
                await self._guard_page(page)
                if await self._requires_login(page):
                    await self._login(page, destination_url=target_url)

                payload = await page.evaluate(
                    """
                    () => {
                      const followerNode =
                        document.querySelector("a[href$='/followers'] span") ||
                        document.querySelector("a[href$='/verified_followers'] span") ||
                        document.querySelector("[data-testid='UserProfileHeader_Items']");
                      const bioNode = document.querySelector("[data-testid='UserDescription']");
                      const handleNode = Array.from(document.querySelectorAll("a[href^='/']")).find((anchor) => {
                        const href = anchor.getAttribute("href") || "";
                        return /^\\/[A-Za-z0-9_]+$/.test(href);
                      });
                      return JSON.stringify({
                        followers: followerNode ? (followerNode.innerText || followerNode.textContent || "") : "",
                        bio: bioNode ? (bioNode.innerText || bioNode.textContent || "") : "",
                        handle: handleNode ? handleNode.getAttribute("href") : "",
                        is_followed_back: Boolean(document.querySelector("[data-testid='userFollowIndicator']"))
                      });
                    }
                    """
                )
                parsed = json.loads(payload or "{}")
                follower_text = str(parsed.get("followers") or "")
                follower_match = re.search(r"([\d.,]+(?:[KkMmBb])?)", follower_text)
                if follower_match:
                    context["followers"] = follower_match.group(1)
                bio_text = str(parsed.get("bio") or "").strip()
                if bio_text:
                    context["bio"] = bio_text
                handle_value = str(parsed.get("handle") or "").strip().lstrip("/")
                if handle_value:
                    context["handle"] = f"@{handle_value}"
                context["is_followed_back"] = self._to_bool(parsed.get("is_followed_back"))
        except Exception:
            return context

        return context

    @asynccontextmanager
    async def _browser_session(self, initial_url: str):
        browser = self._build_browser()
        await browser.start()
        try:
            page = await browser.new_page(initial_url)
            yield page
        finally:
            await browser.stop()

    def _build_browser(self):
        if Browser is None:
            raise ImportError(
                "browser-use is not installed in this environment."
            ) from BROWSER_IMPORT_ERROR

        if self.config.use_system_chrome:
            profile_directory = self.config.chrome_profile_directory or "Default"
            return Browser.from_system_chrome(profile_directory=profile_directory)

        browser_kwargs: dict[str, Any] = {
            "headless": self.config.browser_headless,
        }
        if self.config.storage_state_path is not None:
            browser_kwargs["storage_state"] = str(self.config.storage_state_path)
        if self.config.chrome_executable_path is not None:
            browser_kwargs["executable_path"] = str(self.config.chrome_executable_path)
        if self.config.chrome_user_data_dir is not None:
            browser_kwargs["user_data_dir"] = str(self.config.chrome_user_data_dir)
        if self.config.chrome_profile_directory:
            browser_kwargs["profile_directory"] = self.config.chrome_profile_directory
        return Browser(**browser_kwargs)

    async def _ensure_authenticated(self, page) -> None:
        await page.goto("https://x.com/home")
        await asyncio.sleep(2.5)
        body_text = await self._body_text(page)
        if "rate limit exceeded" in body_text.lower():
            raise RateLimitError("X rate-limited access while checking the authenticated timeline.")
        if await self._looks_authenticated(page):
            return

        if not self.config.x_username or not self.config.x_password:
            raise AuthenticationRequiredError(
                "X session is not authenticated. Provide X_STORAGE_STATE or X_USERNAME/X_PASSWORD."
            )

        await self._login(page, destination_url="https://x.com/home")

    async def _ensure_logged_in(self, page) -> None:
        await self._ensure_authenticated(page)

    async def _login(self, page, destination_url: str | None = None) -> None:
        await page.goto("https://x.com/i/flow/login")
        await asyncio.sleep(2.5)

        username_input = await self._wait_for_selector(
            page,
            ["input[autocomplete='username']", "input[name='text']"],
        )
        await username_input.fill(self.config.x_username, clear=True)
        await self._submit_login_step(page, ["Next", "Sign in", "Log in"])

        body_text = await self._body_text(page)
        if ("phone number or username" in body_text.lower() or "check your email" in body_text.lower()) and self.config.x_email:
            email_input = await self._wait_for_selector(
                page,
                ["input[data-testid='ocfEnterTextTextInput']", "input[name='text']"],
            )
            await email_input.fill(self.config.x_email, clear=True)
            await self._submit_login_step(page, ["Next", "Continue"])

        password_input = await self._wait_for_selector(
            page,
            ["input[name='password']", "input[autocomplete='current-password']"],
        )
        await password_input.fill(self.config.x_password, clear=True)
        await self._submit_login_step(page, ["Log in", "Sign in"])
        await self._wait_for_login_completion(page)

        if destination_url:
            await page.goto(destination_url)
            await asyncio.sleep(2.5)
            await self._guard_page(page)

        if not await self._looks_authenticated(page):
            raise AuthenticationRequiredError(
                "X login did not complete. Seed X_STORAGE_STATE or use a logged-in Chrome profile."
            )

    async def _looks_authenticated(self, page) -> bool:
        if await self._requires_login(page):
            return False
        tweet_nodes = await page.get_elements_by_css_selector("article[data-testid='tweet']")
        if tweet_nodes:
            return True
        authenticated_ui = await page.evaluate(
            """
            () => Boolean(
              document.querySelector("a[data-testid='AppTabBar_Home_Link']") ||
              document.querySelector("button[data-testid='SideNav_NewTweet_Button']") ||
              document.querySelector("nav[aria-label='Primary']")
            )
            """
        )
        if self._to_bool(authenticated_ui):
            return True
        body_text = await self._body_text(page)
        lowered = body_text.lower()
        if "sign in" in lowered or "join x today" in lowered:
            return False
        return "for you" in lowered or "following" in lowered

    async def _requires_login(self, page) -> bool:
        current_url = await self._current_url(page)
        if "login" in current_url.lower() or "/i/flow" in current_url.lower():
            return True
        has_login_form = await page.evaluate(
            """
            () => Boolean(
              document.querySelector("input[autocomplete='username']") ||
              document.querySelector("input[name='text']") ||
              document.querySelector("input[name='password']") ||
              document.querySelector("input[autocomplete='current-password']")
            )
            """
        )
        return self._to_bool(has_login_form)

    async def _current_url(self, page) -> str:
        raw_url = await page.evaluate("() => window.location.href")
        return raw_url if isinstance(raw_url, str) else str(raw_url or "")

    async def _body_text(self, page) -> str:
        raw_text = await page.evaluate("() => document.body ? document.body.innerText : ''")
        return raw_text if isinstance(raw_text, str) else str(raw_text)

    async def _guard_page(self, page) -> None:
        body_text = (await self._body_text(page)).lower()
        if "rate limit exceeded" in body_text:
            raise RateLimitError("X rate-limited the current browser session.")
        if "something went wrong" in body_text and "try reloading" in body_text:
            raise DomChangedError("X returned an error page instead of the expected content.")

    async def _wait_for_timeline(self, page) -> None:
        await self._wait_for_selector(page, ["article[data-testid='tweet']"], retries=12)

    async def _wait_for_tweets(self, page) -> None:
        await self._wait_for_selector(page, ["article[data-testid='tweet']"], retries=12)

    async def _wait_for_selector(
        self,
        page,
        selectors: list[str],
        retries: int = 10,
        delay_seconds: float = 1.0,
    ):
        for _ in range(retries):
            element = await self._first_selector(page, selectors)
            if element is not None:
                return element
            await asyncio.sleep(delay_seconds)
        await self._save_debug_screenshot(page)
        raise DomChangedError(f"Failed to locate selectors: {selectors}")

    async def _save_debug_screenshot(self, page) -> None:
        try:
            await page.screenshot(
                path=str(self.config.app_dir / "debug_screenshot.png"),
                full_page=True,
            )
        except Exception:
            return

    async def _submit_login_step(self, page, primary_labels: list[str]) -> None:
        clicked = await self._click_button_by_text(page, primary_labels)
        if not clicked:
            await page.press("Enter")
        await asyncio.sleep(2.5)

    async def _click_button_by_text(self, page, labels: list[str]) -> bool:
        clicked = await page.evaluate(
            """
            (labels) => {
              const wanted = labels.map((label) => label.trim().toLowerCase());
              const candidates = Array.from(document.querySelectorAll("button, div[role='button']"));
              for (const candidate of candidates) {
                const text = (candidate.innerText || candidate.textContent || "").trim().toLowerCase();
                if (!text) continue;
                const match = wanted.some((label) => text === label || text.includes(label));
                if (!match) continue;
                candidate.click();
                return true;
              }
              return false;
            }
            """,
            labels,
        )
        return self._to_bool(clicked)

    async def _wait_for_login_completion(self, page, max_attempts: int = 10) -> None:
        for _ in range(max_attempts):
            if not await self._requires_login(page) and await self._looks_authenticated(page):
                return
            await asyncio.sleep(1.5)
        raise AuthenticationRequiredError(
            "X login did not complete. Seed X_STORAGE_STATE or use a logged-in Chrome profile."
        )

    async def _first_selector(self, page, selectors: list[str]):
        for selector in selectors:
            elements = await page.get_elements_by_css_selector(selector)
            if elements:
                return elements[0]
        return None

    async def _extract_timeline_posts(self, page) -> list[TimelinePost]:
        raw_payload = await page.evaluate(
            """
            () => JSON.stringify(
              Array.from(document.querySelectorAll("article[data-testid='tweet']")).map((article) => {
                const articleText = article.innerText || "";
                if (articleText.includes("Promoted")) return null;

                const authorNode = article.querySelector("div[data-testid='User-Name'] span");
                const handleNode = Array.from(article.querySelectorAll("a[href^='/']")).find((anchor) => {
                  const href = anchor.getAttribute("href") || "";
                  return /^\\/[A-Za-z0-9_]+$/.test(href);
                });
                const textNodes = Array.from(article.querySelectorAll("div[data-testid='tweetText']"));
                const text = textNodes.map((node) => node.innerText || "").join("\\n").trim();
                const linkNode = Array.from(article.querySelectorAll("a[href*='/status/']")).find((anchor) => {
                  const href = anchor.getAttribute("href") || "";
                  return /\\/status\\/\\d+/.test(href) && !href.includes("/analytics");
                });

                return {
                  author: authorNode ? authorNode.textContent.trim() : "",
                  author_handle: handleNode ? handleNode.getAttribute("href").replace("/", "") : "",
                  text,
                  link: linkNode ? linkNode.href.split("?")[0] : ""
                };
              }).filter(Boolean)
            )
            """
        )
        items = json.loads(raw_payload or "[]")
        posts: list[TimelinePost] = []
        for item in items:
            if not item.get("text") or not item.get("link"):
                continue
            posts.append(
                TimelinePost(
                    author=item.get("author") or "Unknown",
                    author_handle=(item.get("author_handle") or "").strip() or None,
                    text=item["text"].strip(),
                    link=item["link"].strip(),
                )
            )
        return posts

    async def _extract_reply_samples(self, page, handle: str) -> list[InspirationalReplySample]:
        raw_payload = await page.evaluate(
            """
            () => JSON.stringify(
              Array.from(document.querySelectorAll("article[data-testid='tweet']")).map((article) => {
                const articleText = article.innerText || "";
                if (!articleText.includes("Replying to")) return null;
                const textNodes = Array.from(article.querySelectorAll("div[data-testid='tweetText']"));
                const replyText = textNodes.map((node) => node.innerText || "").join("\\n").trim();
                const linkNode = Array.from(article.querySelectorAll("a[href*='/status/']")).find((anchor) => {
                  const href = anchor.getAttribute("href") || "";
                  return /\\/status\\/\\d+/.test(href) && !href.includes("/analytics");
                });
                const metricText = (testId) => {
                  const node = article.querySelector(`[data-testid="${testId}"]`);
                  if (!node) return "";
                  return node.getAttribute("aria-label") || node.innerText || "";
                };
                return {
                  reply_text: replyText,
                  link: linkNode ? linkNode.href.split("?")[0] : "",
                  likes: metricText("like"),
                  retweets: metricText("retweet")
                };
              }).filter(Boolean)
            )
            """
        )
        items = json.loads(raw_payload or "[]")
        results: list[InspirationalReplySample] = []
        for item in items:
            if not item.get("reply_text"):
                continue
            results.append(
                InspirationalReplySample(
                    handle=handle,
                    reply_text=item["reply_text"].strip(),
                    likes=self._parse_metric_text(item.get("likes")),
                    retweets=self._parse_metric_text(item.get("retweets")),
                    link=(item.get("link") or "").strip() or None,
                )
            )
        return results

    async def _extract_reply_metrics(self, page) -> list[ReplyMetricSnapshot]:
        raw_payload = await page.evaluate(
            """
            () => JSON.stringify(
              Array.from(document.querySelectorAll("article[data-testid='tweet']")).map((article) => {
                const articleText = article.innerText || "";
                if (!articleText.includes("Replying to")) return null;
                const textNodes = Array.from(article.querySelectorAll("div[data-testid='tweetText']"));
                const replyText = textNodes.map((node) => node.innerText || "").join("\\n").trim();
                const linkNode = Array.from(article.querySelectorAll("a[href*='/status/']")).find((anchor) => {
                  const href = anchor.getAttribute("href") || "";
                  return /\\/status\\/\\d+/.test(href) && !href.includes("/analytics");
                });
                const metricText = (testId) => {
                  const node = article.querySelector(`[data-testid="${testId}"]`);
                  if (!node) return "";
                  return node.getAttribute("aria-label") || node.innerText || "";
                };
                return {
                  reply_text: replyText,
                  reply_url: linkNode ? linkNode.href.split("?")[0] : "",
                  likes: metricText("like"),
                  retweets: metricText("retweet")
                };
              }).filter(Boolean)
            )
            """
        )
        items = json.loads(raw_payload or "[]")
        snapshots: list[ReplyMetricSnapshot] = []
        for item in items:
            if not item.get("reply_text"):
                continue
            snapshots.append(
                ReplyMetricSnapshot(
                    reply_text=item["reply_text"].strip(),
                    reply_url=(item.get("reply_url") or "").strip() or None,
                    likes=self._parse_metric_text(item.get("likes")),
                    retweets=self._parse_metric_text(item.get("retweets")),
                )
            )
        return snapshots

    @staticmethod
    def _parse_metric_text(raw_value: str | None) -> int:
        if not raw_value:
            return 0
        normalized = raw_value.lower().replace(",", "").strip()
        match = re.search(r"(\d+(?:\.\d+)?)([kmb]?)", normalized)
        if not match:
            return 0
        amount = float(match.group(1))
        suffix = match.group(2)
        multiplier = {
            "": 1,
            "k": 1_000,
            "m": 1_000_000,
            "b": 1_000_000_000,
        }[suffix]
        return int(amount * multiplier)

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() == "true"
        return bool(value)
