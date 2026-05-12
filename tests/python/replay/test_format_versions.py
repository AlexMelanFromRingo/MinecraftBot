"""WireLog format version conformance (T106).

Replay tolerates files with the v1 header and headerless legacy files;
refuses files with a header declaring an unsupported format version.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _make_jsonl(tmp_path: Path, lines: list[dict]) -> Path:
    p = tmp_path / "log.jsonl"
    p.write_text(
        "\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n",
        encoding="utf-8",
    )
    return p


def test_replay_accepts_v1_header(tmp_path: Path) -> None:
    """Header with version=1 + empty body → replay succeeds with zero events."""
    from minecraft_bot.wire_log import WireLog
    path = _make_jsonl(tmp_path, [
        {"meta": {"format": 1, "version": 763, "host": "h", "port": 25565,
                  "username": "Bot"}},
    ])
    replay = WireLog.replay(path)
    assert replay.state.name.lower() in ("handshaking", "play")  # no packets, no transition


def test_replay_accepts_empty_file_after_header(tmp_path: Path) -> None:
    """File with only header → replay returns an empty session."""
    from minecraft_bot.wire_log import WireLog
    path = _make_jsonl(tmp_path, [
        {"meta": {"format": 1, "version": 763, "host": "h", "port": 25565,
                  "username": "Bot"}},
    ])
    replay = WireLog.replay(path)
    assert replay is not None


def test_replay_refuses_future_format_version(tmp_path: Path) -> None:
    """File with meta.format > 1 should refuse to replay."""
    from minecraft_bot.errors import DecodeError
    from minecraft_bot.wire_log import WireLog
    path = _make_jsonl(tmp_path, [
        {"meta": {"format": 99, "version": 763, "host": "h", "port": 25565,
                  "username": "Bot"}},
    ])
    with pytest.raises((DecodeError, ValueError, RuntimeError)):
        WireLog.replay(path)
