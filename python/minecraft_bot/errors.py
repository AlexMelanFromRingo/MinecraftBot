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


# --- Bot API errors (002-bot-api) -----------------------------------------


class NoPathFound(ProtocolError):
    """A* pathfinder exhausted the open set or node budget without
    reaching the target."""

    def __init__(self, target: Any, nodes_explored: int):
        super().__init__(f"no path to {target!r} ({nodes_explored} nodes explored)")
        self.target = target
        self.nodes_explored = nodes_explored


class WalkTimeout(ProtocolError):
    """A long-running movement method exceeded its ``timeout``."""

    def __init__(self, target: Any, elapsed: float):
        super().__init__(f"walk to {target!r} timed out after {elapsed:.1f}s")
        self.target = target
        self.elapsed = elapsed


class DigFailed(ProtocolError):
    """``bot.dig(x, y, z)`` could not finish — block did not break
    within 2x the natural break time, or the block changed mid-dig."""

    def __init__(self, position: Any, reason: str):
        super().__init__(f"dig at {position!r} failed: {reason}")
        self.position = position
        self.reason = reason


class TargetLost(ProtocolError):
    """A follow / attack target vanished from the EntityTracker."""

    def __init__(self, entity_id: int):
        super().__init__(f"target entity {entity_id} lost")
        self.entity_id = entity_id


class ContainerClosed(ProtocolError):
    """An operation was attempted on a container that the server has
    already closed (e.g., chunk unloaded under us)."""


class InventoryStateMismatch(ProtocolError):
    """A click_slot was rejected because the bot's local state_id
    diverged from the server's. Re-fetch ``InventoryTracker.state_id``
    and retry."""

    def __init__(self, local_state_id: int, server_state_id: int):
        super().__init__(
            f"inventory state mismatch: local={local_state_id}, server={server_state_id}"
        )
        self.local_state_id = local_state_id
        self.server_state_id = server_state_id


class InVehicle(ProtocolError):
    """A movement method was called while the bot is riding a vehicle;
    dismount first."""


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
    # Bot API
    "NoPathFound",
    "WalkTimeout",
    "DigFailed",
    "TargetLost",
    "ContainerClosed",
    "InventoryStateMismatch",
    "InVehicle",
]
