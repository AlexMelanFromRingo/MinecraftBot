"""Shared loader for the golden-byte primitives fixture."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PRIMITIVES_PATH = REPO_ROOT / "protocol-data" / "v763" / "golden_bytes" / "primitives.json"


@lru_cache(maxsize=1)
def load_primitives() -> dict:
    return json.loads(PRIMITIVES_PATH.read_text(encoding="utf-8"))


def codec_fixtures(codec_name: str) -> list[dict]:
    return load_primitives()[codec_name]
