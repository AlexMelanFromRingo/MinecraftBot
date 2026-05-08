"""WireLog format conformance tests.

Verifies the JSONL produced by :class:`WireLog` matches the contract in
``specs/001-protocol-foundation/contracts/wire-log-format.md``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from minecraft_bot.protocol.v763.states import ConnectionState, Direction
from minecraft_bot.wire_log import (
    InMemory,
    JsonlFile,
    LoggerSink,
    Tee,
    WireLog,
    WireLogEntry,
)


def _make_entry() -> WireLogEntry:
    return WireLogEntry(
        ts=0.001234,
        direction=Direction.CLIENTBOUND,
        state=ConnectionState.PLAY,
        packet_id=36,
        name="synchronize_player_position",
        fields={"x": 0.5, "y": 64.0, "z": 0.5},
        raw=b"\x0a\x0b\x0c",
    )


# --- in-memory sink --------------------------------------------------------


def test_in_memory_capture() -> None:
    log = WireLog.in_memory()
    log.record(
        direction=Direction.CLIENTBOUND,
        state=ConnectionState.PLAY,
        packet_id=36,
        raw=b"\x00\x01",
        name="x",
    )
    assert len(log.entries()) == 1


def test_in_memory_capacity_evicts_fifo() -> None:
    log = WireLog.in_memory(capacity=2)
    for i in range(5):
        log.record(
            direction=Direction.CLIENTBOUND,
            state=ConnectionState.PLAY,
            packet_id=i,
            raw=b"\x00",
            name=f"p{i}",
        )
    entries = log.entries()
    assert len(entries) == 2
    assert [e.packet_id for e in entries] == [3, 4]  # last two retained


# --- entry → JSON ----------------------------------------------------------


def test_entry_json_required_fields() -> None:
    entry = _make_entry()
    line = entry.to_json_line()
    # Required per contract:
    assert set(line) >= {"ts", "dir", "state", "id", "raw"}
    assert line["dir"] == "rx"
    assert line["state"] == "play"
    assert line["id"] == 36
    assert line["raw"] == "0a0b0c"
    # Optional:
    assert line["name"] == "synchronize_player_position"
    assert "fields" in line


def test_entry_omits_optional_fields_when_none() -> None:
    e = WireLogEntry(
        ts=0.0, direction=Direction.SERVERBOUND, state=ConnectionState.LOGIN,
        packet_id=0, name=None, fields=None, raw=b"",
    )
    line = e.to_json_line()
    assert "name" not in line
    assert "fields" not in line


def test_dir_label_tx_for_serverbound() -> None:
    e = WireLogEntry(
        ts=0.0, direction=Direction.SERVERBOUND, state=ConnectionState.PLAY,
        packet_id=1, name="x", fields=None, raw=b"\xde\xad",
    )
    assert e.to_json_line()["dir"] == "tx"


# --- JSONL file sink ------------------------------------------------------


def test_jsonl_file_writes_header_and_entries(tmp_path: Path) -> None:
    p = tmp_path / "session.jsonl"
    log = WireLog.to_jsonl(p)
    log.start_session(version=763, host="172.26.160.1", port=25565, username="Bot")
    log.record(
        direction=Direction.CLIENTBOUND, state=ConnectionState.PLAY,
        packet_id=10, raw=b"\xff", name="x", fields=None,
    )
    log.record(
        direction=Direction.SERVERBOUND, state=ConnectionState.PLAY,
        packet_id=11, raw=b"\x00", name="y", fields=None,
    )
    assert isinstance(log.sink, JsonlFile)
    log.sink.close()  # ensure flushed

    lines = p.read_text(encoding="utf-8").rstrip("\n").split("\n")
    assert len(lines) == 3  # header + 2 entries

    header = json.loads(lines[0])
    assert "meta" in header
    assert header["meta"]["format"] == 1
    assert header["meta"]["version"] == 763

    entry_a = json.loads(lines[1])
    assert entry_a["dir"] == "rx"
    assert entry_a["id"] == 10
    assert entry_a["raw"] == "ff"

    entry_b = json.loads(lines[2])
    assert entry_b["dir"] == "tx"


def test_start_session_is_idempotent(tmp_path: Path) -> None:
    p = tmp_path / "session.jsonl"
    log = WireLog.to_jsonl(p)
    log.start_session(version=763, host="h", port=25565, username="u")
    log.start_session(version=763, host="h", port=25565, username="u")  # again
    log.sink.close()  # type: ignore[union-attr]
    n_lines = sum(1 for _ in p.read_text(encoding="utf-8").splitlines())
    assert n_lines == 1


# --- tee sink --------------------------------------------------------------


def test_tee_fans_out() -> None:
    a = InMemory()
    b = InMemory()
    log = WireLog(sink=Tee(a, b))
    log.start_session(version=763, host="h", port=25565, username="u")
    log.record(
        direction=Direction.CLIENTBOUND, state=ConnectionState.PLAY,
        packet_id=42, raw=b"\xab", name="x", fields=None,
    )
    assert len(a.entries()) == 1
    assert len(b.entries()) == 1
    assert a.entries()[0].packet_id == 42 == b.entries()[0].packet_id


# --- in-memory only on entries() ------------------------------------------


def test_entries_raises_for_non_inmemory(tmp_path: Path) -> None:
    log = WireLog.to_jsonl(tmp_path / "x.jsonl")
    with pytest.raises(TypeError):
        log.entries()
    log.sink.close()  # type: ignore[union-attr]


# --- logger sink doesn't crash --------------------------------------------


def test_logger_sink_smoke() -> None:
    log = WireLog.to_logger()
    log.start_session(version=763, host="h", port=25565, username="u")
    log.record(
        direction=Direction.CLIENTBOUND, state=ConnectionState.PLAY,
        packet_id=1, raw=b"\x00", name="x", fields=None,
    )
    assert isinstance(log.sink, LoggerSink)
