"""Wire log capture and offline replay.

This module ships the **capture** half of the WireLog feature
(FR-018 / data-model E-8). The replay half lands in Phase 6 (US4) and
will reuse the :class:`WireLogEntry` schema, the JSONL line format
spec, and the sink hierarchy here.

JSONL format reference: ``contracts/wire-log-format.md``.

Sinks:

- :class:`InMemory`   — keeps entries in memory, optionally bounded
- :class:`JsonlFile`  — appends a JSONL line per entry, flushed each write
- :class:`LoggerSink` — emits each entry at DEBUG level via the
                         ``minecraft_bot.protocol.wire`` logger
- :class:`Tee`        — fans out to multiple sinks
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from minecraft_bot.protocol.v763.states import ConnectionState, Direction

_FORMAT_VERSION = 1
_log = logging.getLogger("minecraft_bot.protocol.wire")


# --- entry -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WireLogEntry:
    """One packet event on a Connection."""

    ts: float                       # seconds since session start (or epoch if no header)
    direction: Direction
    state: ConnectionState
    packet_id: int
    name: Optional[str]             # snake_case packet name, informational
    fields: Optional[dict[str, Any]]  # best-effort JSON of decoded fields; None on decode failure
    raw: bytes                      # lossless payload bytes

    def to_json_line(self) -> dict[str, Any]:
        """Render the entry as a JSON-serialisable dict (one JSONL line)."""
        out: dict[str, Any] = {
            "ts": round(self.ts, 6),
            "dir": self.direction.label(),
            "state": self.state.label(),
            "id": self.packet_id,
            "raw": self.raw.hex(),
        }
        if self.name is not None:
            out["name"] = self.name
        if self.fields is not None:
            out["fields"] = self.fields
        return out


# --- sinks -----------------------------------------------------------------


class WireLogSink:
    """Base interface for wire-log sinks."""

    def write_header(self, header: dict[str, Any]) -> None:  # pragma: no cover
        raise NotImplementedError

    def write_entry(self, entry: WireLogEntry) -> None:  # pragma: no cover
        raise NotImplementedError


class InMemory(WireLogSink):
    """Keep entries in a deque, optionally bounded.

    Entries can be retrieved via :meth:`entries`. When ``capacity`` is
    set, the oldest entries are evicted FIFO.
    """

    def __init__(self, capacity: Optional[int] = None) -> None:
        self.capacity = capacity
        self._header: Optional[dict[str, Any]] = None
        self._entries: deque[WireLogEntry] = deque(maxlen=capacity)

    def write_header(self, header: dict[str, Any]) -> None:
        self._header = dict(header)

    def write_entry(self, entry: WireLogEntry) -> None:
        self._entries.append(entry)

    def entries(self) -> list[WireLogEntry]:
        return list(self._entries)

    def header(self) -> Optional[dict[str, Any]]:
        return None if self._header is None else dict(self._header)


class JsonlFile(WireLogSink):
    """Append one JSON line per entry to a file. Flushed after every write."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Open in 'w' to truncate at session start; the header line goes
        # in via write_header.
        self._fh = self.path.open("w", encoding="utf-8")

    def write_header(self, header: dict[str, Any]) -> None:
        self._fh.write(json.dumps({"meta": header}, ensure_ascii=False))
        self._fh.write("\n")
        self._fh.flush()

    def write_entry(self, entry: WireLogEntry) -> None:
        self._fh.write(json.dumps(entry.to_json_line(), ensure_ascii=False))
        self._fh.write("\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


class LoggerSink(WireLogSink):
    """Emit each entry at DEBUG level via a Python logger."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or _log

    def write_header(self, header: dict[str, Any]) -> None:
        self._logger.debug("wire.meta %s", json.dumps(header, ensure_ascii=False))

    def write_entry(self, entry: WireLogEntry) -> None:
        self._logger.debug(
            "wire %s state=%s id=%d name=%s raw=%d_bytes",
            entry.direction.label(), entry.state.label(),
            entry.packet_id, entry.name or "?", len(entry.raw),
        )


class Tee(WireLogSink):
    """Fan-out sink: writes to all child sinks in order."""

    def __init__(self, *children: WireLogSink) -> None:
        self.children = children

    def write_header(self, header: dict[str, Any]) -> None:
        for c in self.children:
            c.write_header(header)

    def write_entry(self, entry: WireLogEntry) -> None:
        for c in self.children:
            c.write_entry(entry)


# --- WireLog facade --------------------------------------------------------


@dataclass(slots=True)
class WireLog:
    """The capture-side handle attached to a :class:`Connection`.

    ``WireLog.replay(path)`` (offline replay) lands in Phase 6 (US4).
    """

    sink: WireLogSink = field(default_factory=lambda: InMemory())
    started_at: float = field(default_factory=time.time)
    _header_written: bool = False

    @classmethod
    def to_jsonl(cls, path: str | Path) -> "WireLog":
        return cls(sink=JsonlFile(path))

    @classmethod
    def to_logger(cls, logger: logging.Logger | None = None) -> "WireLog":
        return cls(sink=LoggerSink(logger))

    @classmethod
    def in_memory(cls, capacity: Optional[int] = None) -> "WireLog":
        return cls(sink=InMemory(capacity))

    def start_session(
        self,
        *,
        version: int,
        host: str,
        port: int,
        username: str,
    ) -> None:
        """Write the meta-header line. Idempotent — only written once."""
        if self._header_written:
            return
        self.sink.write_header({
            "format": _FORMAT_VERSION,
            "version": version,
            "started_at": self.started_at,
            "host": host,
            "port": port,
            "username": username,
        })
        self._header_written = True

    def record(
        self,
        *,
        direction: Direction,
        state: ConnectionState,
        packet_id: int,
        raw: bytes,
        name: Optional[str] = None,
        fields: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record one packet event."""
        entry = WireLogEntry(
            ts=time.time() - self.started_at,
            direction=direction,
            state=state,
            packet_id=packet_id,
            name=name,
            fields=fields,
            raw=bytes(raw),
        )
        self.sink.write_entry(entry)

    def entries(self) -> list[WireLogEntry]:
        """Available only for InMemory sinks."""
        if not isinstance(self.sink, InMemory):
            raise TypeError(
                f"entries() is only valid on InMemory sinks; this sink is {type(self.sink).__name__}"
            )
        return self.sink.entries()


__all__ = [
    "WireLog", "WireLogEntry", "WireLogSink",
    "InMemory", "JsonlFile", "LoggerSink", "Tee",
]
