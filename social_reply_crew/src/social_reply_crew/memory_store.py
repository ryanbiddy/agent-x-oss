from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parents[2]
load_dotenv(APP_DIR / ".env")

_raw_memory_path = os.getenv("MEMORY_PATH")
if _raw_memory_path:
    _memory_path = Path(_raw_memory_path)
    MEMORY_PATH = _memory_path if _memory_path.is_absolute() else (APP_DIR / _memory_path).resolve()
else:
    MEMORY_PATH = (APP_DIR / "MEMORY.md").resolve()

DEFAULT_MEMORY_TEMPLATE = """# Agent X Memory

## SECTION 1 - Voice
VOICE_FINGERPRINT:

## SECTION 2 - Patterns
AVOID_PATTERNS:
"""


def ensure_memory_file() -> Path:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not MEMORY_PATH.exists():
        MEMORY_PATH.write_text(DEFAULT_MEMORY_TEMPLATE, encoding="utf-8")
    return MEMORY_PATH


def load_memory_context() -> dict[str, str]:
    path = ensure_memory_file()
    content = path.read_text(encoding="utf-8")
    voice_match = re.search(
        r"VOICE_FINGERPRINT:\s*(.*?)(?=\n## SECTION|\Z)",
        content,
        flags=re.DOTALL,
    )
    return {
        "voice_fingerprint": (voice_match.group(1).strip() if voice_match else ""),
        "raw": content,
    }
