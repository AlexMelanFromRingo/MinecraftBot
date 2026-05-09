"""US4 — Inspect, replay, and diff the wire (offline + live).

T105: parity test — capture a live session, replay, assert reconstructed
state matches what the live Connection had.

T106: format version regression — synthetic files; offline only.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import pytest

from minecraft_bot.errors import DecodeError, ProtocolError
from minecraft_bot.protocol.v763.states import ConnectionState
from minecraft_bot.wire_log import (
    InMemory,
    JsonlFile,
    ReplayedConnection,
    WireLog,
    WireLogEntry,
)


# --- T106: format-version conformance --------------------------------------


def test_replay_unsupported_format_raises(tmp_path: Path) -> None:
    """meta.format > 1 is rejected with a clear error."""
    p = tmp_path / "future.jsonl"
    p.write_text(
        json.dumps({"meta": {"format": 999, "version": 763}}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(DecodeError, match="unsupported format version"):
        WireLog.replay(p)


def test_replay_missing_format_raises(tmp_path: Path) -> None:
    p = tmp_path / "noformat.jsonl"
    p.write_text(
        json.dumps({"meta": {"version": 763}}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(DecodeError, match="missing meta.format"):
        WireLog.replay(p)


def test_replay_no_header_requires_version_arg(tmp_path: Path) -> None:
    """Without a meta header and without --version, replay fails fast."""
    p = tmp_path / "noheader.jsonl"
    p.write_text(
        json.dumps({"ts": 0.0, "dir": "rx", "state": "play", "id": 0x23, "raw": "0000000000000001"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(DecodeError, match="no meta header"):
        WireLog.replay(p)


def test_replay_with_explicit_version(tmp_path: Path) -> None:
    """No header but an explicit ``version`` arg works for known packets."""
    p = tmp_path / "noheader.jsonl"
    # Clientbound play KeepAlive (id 0x23): single i64 = 1
    p.write_text(
        json.dumps({
            "ts": 0.0, "dir": "rx", "state": "play", "id": 0x23,
            "name": "keep_alive",
            "raw": "0000000000000001",
        }) + "\n",
        encoding="utf-8",
    )
    rep = WireLog.replay(p, version=763)
    assert rep.entry_count == 1
    assert rep.entries[0].name == "keep_alive"


def test_replay_empty_file_raises(tmp_path: Path) -> None:
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    with pytest.raises(DecodeError, match="empty file"):
        WireLog.replay(p)


def test_replay_malformed_line_raises(tmp_path: Path) -> None:
    p = tmp_path / "broken.jsonl"
    p.write_text(
        json.dumps({"meta": {"format": 1, "version": 763}}) + "\n"
        + "not-json\n",
        encoding="utf-8",
    )
    with pytest.raises(DecodeError, match="malformed json"):
        WireLog.replay(p)


# --- T105: round-trip via in-memory capture ---------------------------------


def test_capture_then_replay_in_memory(tmp_path: Path) -> None:
    """Synthesise a small session, write to JSONL, replay, assert
    reconstructed state matches the input."""
    from minecraft_bot.codec import Writer
    from minecraft_bot.protocol.v763.packets.play.clientbound import (
        keep_alive as p_cb_ka,
    )
    from minecraft_bot.protocol.v763.packets.play.clientbound import (
        position as p_cb_pos,
    )
    from minecraft_bot.protocol.v763.states import ConnectionState, Direction

    out = tmp_path / "synth.jsonl"
    log = WireLog.to_jsonl(out)
    log.start_session(version=763, host="localhost", port=25565, username="Synth")

    # Three packets: KeepAlive, Position, KeepAlive
    ka1 = p_cb_ka.KeepAlive(keep_alive_id=42)
    pos = p_cb_pos.Position(x=10.0, y=64.0, z=-5.0, yaw=0.0, pitch=0.0, flags=0, teleport_id=1)
    ka2 = p_cb_ka.KeepAlive(keep_alive_id=43)

    for pkt in (ka1, pos, ka2):
        if isinstance(pkt, p_cb_ka.KeepAlive):
            w = Writer(); p_cb_ka.encode(pkt, w)
            log.record(direction=Direction.CLIENTBOUND, state=ConnectionState.PLAY,
                       packet_id=p_cb_ka.PACKET_ID, raw=w.bytes(), name="keep_alive")
        elif isinstance(pkt, p_cb_pos.Position):
            w = Writer(); p_cb_pos.encode(pkt, w)
            log.record(direction=Direction.CLIENTBOUND, state=ConnectionState.PLAY,
                       packet_id=p_cb_pos.PACKET_ID, raw=w.bytes(), name="position")
    log.sink.close()  # type: ignore[union-attr]

    # Replay and assert
    rep = WireLog.replay(out)
    assert isinstance(rep, ReplayedConnection)
    assert rep.entry_count == 3
    assert rep.protocol_version == 763
    # The Position packet updates final_position
    assert rep.final_position == (10.0, 64.0, -5.0)
    # The names are preserved
    assert [e.name for e in rep.entries] == ["keep_alive", "position", "keep_alive"]
    # Raw bytes round-trip identically
    assert rep.entries[0].raw == bytes.fromhex("000000000000002a")
    assert rep.entries[2].raw == bytes.fromhex("000000000000002b")


def test_replay_missing_required_field(tmp_path: Path) -> None:
    """Lines missing one of (ts, dir, state, id, raw) fail with a clear msg."""
    p = tmp_path / "incomplete.jsonl"
    p.write_text(
        json.dumps({"meta": {"format": 1, "version": 763}}) + "\n"
        + json.dumps({"ts": 0.0, "dir": "rx", "state": "play", "id": 0x23}) + "\n",  # no 'raw'
        encoding="utf-8",
    )
    with pytest.raises(DecodeError, match="missing key 'raw'"):
        WireLog.replay(p)


def test_replay_unknown_packet_in_file(tmp_path: Path) -> None:
    """Replay raises if the file references a packet the registry doesn't have."""
    p = tmp_path / "unknown.jsonl"
    p.write_text(
        json.dumps({"meta": {"format": 1, "version": 763}}) + "\n"
        + json.dumps({"ts": 0.0, "dir": "rx", "state": "play", "id": 0xFF, "raw": ""}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(DecodeError, match="no decoder for"):
        WireLog.replay(p)
