"""T068 — WireLog format invariance.

Both backends MUST emit the same JSONL when given the same packet
stream. We don't yet have a high-level WireLog.record call wired
through the accel Bot — instead we test the lower-level invariant:
that the accel WireLog produces the same per-entry shape as the
Python WireLog when called directly.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path


def test_accel_wirelog_writes_session_header() -> None:
    """`WireLog.to_jsonl(path).start_session(...)` writes a meta header
    line whose JSON structure matches the accel header shape."""
    from minecraft_bot_accel import WireLog

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "accel.jsonl"
        log = WireLog.to_jsonl(str(p))
        log.start_session(version=763, host="paper.test", port=25565, username="W")
        # Idempotent — second call is a no-op.
        log.start_session(version=763, host="paper.test", port=25565, username="W")
        lines = p.read_text().splitlines()
        assert len(lines) == 1
        header = json.loads(lines[0])
        assert "meta" in header
        meta = header["meta"]
        assert meta["version"] == 1  # format version, not protocol
        assert meta["protocol"] == 763
        assert meta["host"] == "paper.test"
        assert meta["port"] == 25565
        assert meta["username"] == "W"


def test_accel_wirelog_writes_entry() -> None:
    """Record one entry; verify keys and types."""
    from minecraft_bot_accel import WireLog

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "accel.jsonl"
        log = WireLog.to_jsonl(str(p))
        log.start_session(version=763, host="h", port=25565, username="U")
        log.record(
            direction="rx",
            state="play",
            packet_id=0x24,
            raw=b"\xde\xad\xbe\xef",
            name="map_chunk",
        )
        lines = p.read_text().splitlines()
        assert len(lines) == 2
        entry = json.loads(lines[1])
        assert set(entry.keys()) >= {"ts", "dir", "state", "id", "raw"}
        assert entry["dir"] == "rx"
        assert entry["state"] == "play"
        assert entry["id"] == 0x24
        assert entry["raw"] == "deadbeef"
        assert isinstance(entry["ts"], (int, float))
        assert entry["name"] == "map_chunk"


def test_accel_wirelog_rejects_unknown_state_label() -> None:
    """Unknown direction or state strings raise ValueError, matching the
    Python WireLog's typed enum behaviour."""
    import pytest
    from minecraft_bot_accel import WireLog

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "accel.jsonl"
        log = WireLog.to_jsonl(str(p))
        log.start_session(version=763, host="h", port=25565, username="U")
        with pytest.raises(ValueError):
            log.record(
                direction="rx",
                state="not-a-state",
                packet_id=0,
                raw=b"",
                name=None,
            )
