"""Connection states and packet directions for protocol 763 (Minecraft 1.20.1).

Per ``data-model.md`` E-1, E-2. Variant integer values are stable across
captures and replay (used in WireLog JSONL ``state`` and ``dir`` fields
indirectly through their string forms).

**Note**: protocol 763 does NOT have the ``CONFIGURATION`` state — that
was introduced in protocol 764 (1.20.2). Adding it later means a new
variant on this enum and a new entry in the registry.
"""

from __future__ import annotations

from enum import IntEnum


class ConnectionState(IntEnum):
    """Discrete protocol phases of a Connection.

    Values are stable: 0 = HANDSHAKING, 1 = STATUS, 2 = LOGIN, 3 = PLAY.
    """

    HANDSHAKING = 0
    STATUS = 1
    LOGIN = 2
    PLAY = 3

    def label(self) -> str:
        """Lowercase string used in WireLog JSONL ``state`` field."""
        return self.name.lower()


class Direction(IntEnum):
    """Packet flow direction.

    Values are stable: 0 = CLIENTBOUND (server→client), 1 = SERVERBOUND.
    """

    CLIENTBOUND = 0
    SERVERBOUND = 1

    def label(self) -> str:
        """Two-letter string for WireLog (``"rx"`` / ``"tx"``).

        ``rx`` = clientbound (we receive); ``tx`` = serverbound (we transmit).
        """
        return "rx" if self == Direction.CLIENTBOUND else "tx"

    @classmethod
    def from_label(cls, label: str) -> "Direction":
        if label == "rx":
            return cls.CLIENTBOUND
        if label == "tx":
            return cls.SERVERBOUND
        raise ValueError(f"unknown direction label: {label!r}")


__all__ = ["ConnectionState", "Direction"]
