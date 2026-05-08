"""Typed error hierarchy for the minecraft_bot framework.

See ``specs/001-protocol-foundation/data-model.md`` E-10 and
``specs/001-protocol-foundation/contracts/python-api.md`` for the
normative contract.

The hierarchy is:

    ProtocolError
    ├── HandshakeFailed
    ├── LoginFailed
    ├── Disconnected
    │   └── KickedByServer
    ├── ConnectionDropped
    │   ├── KeepAliveTimeout
    │   └── PeerReset
    ├── DecodeError
    │   ├── UnknownPacketId
    │   ├── OversizedVarInt
    │   ├── IncompleteRead       — codec ran past the end of the buffer
    │   └── MalformedNbt
    ├── EncodeError
    │   └── ValueOutOfRange
    └── ConnectionClosed         — operation attempted on a closed Connection

All error types here are part of the public API.
"""

from __future__ import annotations

from typing import Any


class ProtocolError(Exception):
    """Base class for every error the framework surfaces to the developer."""


# --- connection lifecycle --------------------------------------------------


class HandshakeFailed(ProtocolError):
    """Server rejected the handshake or peer aborted before login."""


class LoginFailed(ProtocolError):
    """Server rejected the login. ``reason`` carries the server-provided text
    if available (or a synthesised one for offline-mode policy violations,
    e.g., an unexpected EncryptionRequest)."""


class Disconnected(ProtocolError):
    """Server-initiated disconnect during the play state."""


class KickedByServer(Disconnected):
    """The server sent a clientbound disconnect packet with a reason."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class ConnectionDropped(ProtocolError):
    """TCP-level loss outside a clean disconnect."""


class KeepAliveTimeout(ConnectionDropped):
    """The framework did not answer a keep-alive within the protocol window."""


class PeerReset(ConnectionDropped):
    """The OS reported the socket was reset by the peer."""


class ConnectionClosed(ProtocolError):
    """Operation attempted on a Connection that is no longer open."""


# --- decoding --------------------------------------------------------------


class DecodeError(ProtocolError):
    """The framework received bytes it could not parse."""


class UnknownPacketId(DecodeError):
    """A packet ID that has no schema registered for the current
    (state, direction) tuple."""

    def __init__(self, state: Any, direction: Any, id: int):
        super().__init__(f"unknown packet id: state={state} dir={direction} id={id}")
        self.state = state
        self.direction = direction
        self.id = id


class OversizedVarInt(DecodeError):
    """A VarInt or VarLong consumed more bytes than the format allows
    (5 for VarInt, 10 for VarLong)."""

    def __init__(self, byte_count: int):
        super().__init__(f"oversized varint ({byte_count} bytes)")
        self.byte_count = byte_count


class IncompleteRead(DecodeError):
    """A codec asked the Reader for more bytes than remain in the buffer.
    Distinct from OversizedVarInt — this means the buffer is truncated."""

    def __init__(self, requested: int, available: int):
        super().__init__(f"incomplete read: requested {requested}, available {available}")
        self.requested = requested
        self.available = available


class MalformedNbt(DecodeError):
    """An NBT tag was structurally invalid (unknown tag id, bad string
    length, list of incompatible types, ...)."""

    def __init__(self, detail: str):
        super().__init__(f"malformed NBT: {detail}")
        self.detail = detail


# --- encoding --------------------------------------------------------------


class EncodeError(ProtocolError):
    """A value provided by the developer cannot be serialised."""


class ValueOutOfRange(EncodeError):
    """A numeric or length-bounded field is out of its protocol-defined range."""

    def __init__(self, field: str, value: Any):
        super().__init__(f"value out of range: field={field!s} value={value!r}")
        self.field = field
        self.value = value


__all__ = [
    "ProtocolError",
    "HandshakeFailed",
    "LoginFailed",
    "Disconnected",
    "KickedByServer",
    "ConnectionDropped",
    "KeepAliveTimeout",
    "PeerReset",
    "ConnectionClosed",
    "DecodeError",
    "UnknownPacketId",
    "OversizedVarInt",
    "IncompleteRead",
    "MalformedNbt",
    "EncodeError",
    "ValueOutOfRange",
]
