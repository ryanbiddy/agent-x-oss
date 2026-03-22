from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _read_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _read_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    values = [item.strip().lstrip("@") for item in raw_value.split(",")]
    return tuple(item for item in values if item)


def _resolve_optional_path(app_dir: Path, raw_value: str | None) -> Path | None:
    if not raw_value:
        return None
    path = Path(raw_value)
    return path if path.is_absolute() else (app_dir / path).resolve()


@dataclass(slots=True)
class AppConfig:
    app_dir: Path
    database_path: Path
    storage_state_path: Path | None
    x_profile_url: str
    x_username: str | None
    x_password: str | None
    x_email: str | None
    use_system_chrome: bool
    chrome_profile_directory: str | None
    chrome_user_data_dir: Path | None
    chrome_executable_path: Path | None
    browser_headless: bool
    crew_model: str
    inspirational_handles: tuple[str, ...]
    focus_areas: tuple[str, ...]
    timeline_candidate_limit: int
    timeline_post_limit: int
    inspiration_replies_per_account: int
    refresh_limit: int
    reply_character_limit: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        app_dir = Path(__file__).resolve().parents[2]
        load_dotenv(app_dir / ".env")

        data_dir = app_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        storage_state_path = _resolve_optional_path(
            app_dir,
            os.getenv("X_STORAGE_STATE", "./x_storage_state.json"),
        )

        return cls(
            app_dir=app_dir,
            database_path=_resolve_optional_path(
                app_dir,
                os.getenv("DB_PATH") or os.getenv("X_DATABASE_PATH"),
            )
            or (data_dir / "social_reply_memory.db"),
            storage_state_path=storage_state_path,
            x_profile_url=os.getenv("X_PROFILE_URL", "").rstrip("/"),
            x_username=os.getenv("X_USERNAME") or None,
            x_password=os.getenv("X_PASSWORD") or None,
            x_email=os.getenv("X_EMAIL") or None,
            use_system_chrome=_read_bool("X_USE_SYSTEM_CHROME", False),
            chrome_profile_directory=os.getenv("X_PROFILE_DIRECTORY") or None,
            chrome_user_data_dir=_resolve_optional_path(app_dir, os.getenv("X_USER_DATA_DIR")),
            chrome_executable_path=_resolve_optional_path(app_dir, os.getenv("X_EXECUTABLE_PATH")),
            browser_headless=_read_bool("HEADLESS_BROWSER", _read_bool("X_HEADLESS", False)),
            crew_model=os.getenv("LLM_MODEL")
            or os.getenv("CREW_LLM_MODEL", "anthropic/claude-sonnet-4-20250514"),
            inspirational_handles=_read_csv(
                "X_INSPIRATIONAL_HANDLES",
                ("gregisenberg", "sahilbloom", "naval"),
            ),
            focus_areas=_read_csv(
                "X_FOCUS_AREAS",
                ("AI agents", "browser automation", "developer tools"),
            ),
            timeline_candidate_limit=int(
                os.getenv("MAX_TWEETS_PER_RUN", os.getenv("X_TIMELINE_CANDIDATE_LIMIT", "12"))
            ),
            timeline_post_limit=int(os.getenv("X_TIMELINE_POST_LIMIT", "5")),
            inspiration_replies_per_account=int(
                os.getenv("X_INSPIRATION_REPLIES_PER_ACCOUNT", "4")
            ),
            refresh_limit=int(os.getenv("X_REFRESH_LIMIT", "30")),
            reply_character_limit=int(os.getenv("X_REPLY_CHARACTER_LIMIT", "260")),
        )

    @property
    def x_replies_tab_url(self) -> str:
        if not self.x_profile_url:
            raise ValueError("X_PROFILE_URL must be set to refresh historical reply engagement.")
        return f"{self.x_profile_url}/with_replies"

    @property
    def focus_brief(self) -> str:
        return ", ".join(self.focus_areas)
