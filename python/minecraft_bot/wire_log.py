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

    @classmethod
    def replay(
        cls,
        path: str | Path,
        *,
        version: Optional[int] = None,
    ) -> "ReplayedConnection":
        """Replay a captured ``.jsonl`` file offline.

        Reads every line, decodes each packet via the appropriate
        :class:`~minecraft_bot.protocol.v763.registry.CodecRegistry`,
        and builds a :class:`ReplayedConnection` with the same
        read-only state-view a live :class:`Connection` would have at
        the end of the session (FR-019, SC-005).

        ``version`` overrides the protocol number (otherwise read from
        the file's meta header).

        Raises :class:`~minecraft_bot.errors.DecodeError` for malformed
        files, unsupported format versions, or corrupt packet payloads.
        """
        # Local import keeps `wire_log` independent of `protocol.v763` at
        # module-import time (avoids circular imports during package init).
        from minecraft_bot.errors import DecodeError, UnknownPacketId
        from minecraft_bot.protocol.v763.registry import CodecRegistry
        from minecraft_bot.protocol.v763.states import ConnectionState, Direction
        from minecraft_bot.codec import Reader as CodecReader
        from minecraft_bot.codec import varint as varint_codec

        registry = CodecRegistry.build()
        path = Path(path)
        if not path.exists():
            raise DecodeError(f"replay: file not found: {path}")

        replay = ReplayedConnection()

        with path.open("r", encoding="utf-8") as fh:
            first_line = fh.readline()
            if not first_line:
                raise DecodeError(f"replay: empty file: {path}")

            try:
                first_obj = json.loads(first_line)
            except json.JSONDecodeError as exc:
                raise DecodeError(f"replay: malformed first line: {exc}") from exc

            # Meta header line is optional but expected.
            if "meta" in first_obj:
                meta = first_obj["meta"]
                fmt = meta.get("format")
                if fmt is None or not isinstance(fmt, int):
                    raise DecodeError(f"replay: missing meta.format")
                if fmt > _FORMAT_VERSION:
                    raise DecodeError(
                        f"replay: unsupported format version {fmt}; "
                        f"this build understands up to {_FORMAT_VERSION}"
                    )
                if version is None:
                    version = meta.get("version")
                replay.meta = dict(meta)
                first_data_line: Optional[str] = None
            else:
                # No meta header — treat the first line as a packet entry.
                first_data_line = first_line
                if version is None:
                    raise DecodeError(
                        "replay: file has no meta header and no `version` argument given"
                    )

            replay.protocol_version = version
            replay.state = ConnectionState.HANDSHAKING

            # Stream packet lines.
            data_lines: list[str] = []
            if first_data_line is not None:
                data_lines.append(first_data_line)
            data_lines.extend(fh)

            for line_no, raw_line in enumerate(data_lines, start=2 if first_data_line is None else 1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise DecodeError(f"replay line {line_no}: malformed json: {exc}") from exc

                # Validate required fields.
                for k in ("ts", "dir", "state", "id", "raw"):
                    if k not in obj:
                        raise DecodeError(f"replay line {line_no}: missing key {k!r}")

                state_label = obj["state"]
                dir_label = obj["dir"]
                try:
                    state = ConnectionState[state_label.upper()]
                except KeyError as exc:
                    raise DecodeError(
                        f"replay line {line_no}: unknown state {state_label!r}"
                    ) from exc
                try:
                    direction = Direction.from_label(dir_label)
                except ValueError as exc:
                    raise DecodeError(
                        f"replay line {line_no}: unknown direction {dir_label!r}"
                    ) from exc

                pid = int(obj["id"])
                raw = bytes.fromhex(obj["raw"])

                try:
                    decoder = registry.decoder(state, direction, pid)
                except UnknownPacketId:
                    # File references a packet not in this build's registry —
                    # e.g., replaying a file from a future protocol version.
                    raise DecodeError(
                        f"replay line {line_no}: no decoder for "
                        f"({state.label()}, {direction.label()}, id=0x{pid:02x})"
                    ) from None

                try:
                    decoded = decoder(CodecReader(raw))
                except DecodeError as exc:
                    raise DecodeError(
                        f"replay line {line_no}: decode error in "
                        f"{state.label()}/{direction.label()}/0x{pid:02x}: {exc}"
                    ) from exc

                replay.entries.append(WireLogEntry(
                    ts=float(obj["ts"]),
                    direction=direction, state=state, packet_id=pid,
                    name=obj.get("name"),
                    fields=obj.get("fields"),
                    raw=raw,
                ))

                # Emulate the bits of state evolution a live Connection would
                # have after each packet — only the pieces a tester is likely
                # to want to compare in SC-005.
                _apply_state(replay, state, direction, decoded)

        return replay


@dataclass(slots=True)
class ReplayedConnection:
    """Offline-only counterpart to :class:`~minecraft_bot.connection.Connection`.

    Exposes the same read-only state attributes a live Connection would
    have at the end of a captured session. Constructed by
    :meth:`WireLog.replay`.
    """

    protocol_version: Optional[int] = None
    meta: dict[str, Any] = field(default_factory=dict)
    entries: list[WireLogEntry] = field(default_factory=list)

    # Per-session state mirrored from a live Connection.
    state: Any = None  # ConnectionState; Any to avoid forward-import dance
    compression_threshold: int = -1
    entity_id: Optional[int] = None
    game_mode: Optional[int] = None
    world_name: Optional[str] = None
    final_position: Optional[tuple[float, float, float]] = None

    @property
    def entry_count(self) -> int:
        return len(self.entries)


def _apply_state(replay: "ReplayedConnection", state: Any, direction: Any, packet: Any) -> None:
    """Mirror a subset of live-Connection state derivations from a decoded packet."""
    from minecraft_bot.protocol.v763.states import ConnectionState, Direction
    from minecraft_bot.protocol.v763.packets.login.clientbound import compress as p_l_cb_compress
    from minecraft_bot.protocol.v763.packets.login.clientbound import success as p_l_cb_success
    from minecraft_bot.protocol.v763.packets.play.clientbound import login as p_p_cb_login
    from minecraft_bot.protocol.v763.packets.play.clientbound import position as p_p_cb_pos

    if direction != Direction.CLIENTBOUND:
        return
    if isinstance(packet, p_l_cb_compress.Compress):
        replay.compression_threshold = packet.threshold
    elif isinstance(packet, p_l_cb_success.Success):
        replay.state = ConnectionState.PLAY
    elif isinstance(packet, p_p_cb_login.Login):
        replay.entity_id = packet.entity_id
        replay.game_mode = packet.game_mode
        replay.world_name = packet.world_name
        replay.state = ConnectionState.PLAY
    elif isinstance(packet, p_p_cb_pos.Position):
        replay.final_position = (packet.x, packet.y, packet.z)


__all__ = [
    "WireLog", "WireLogEntry", "WireLogSink",
    "InMemory", "JsonlFile", "LoggerSink", "Tee",
    "ReplayedConnection",
]
