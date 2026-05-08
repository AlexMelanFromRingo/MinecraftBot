"""Protocol-version-aware module root.

Each supported wire-protocol version lives under a `vNNN` sub-package
(currently only :mod:`minecraft_bot.protocol.v763`). The
:class:`ProtocolVersion` value type identifies which sub-package a
:class:`~minecraft_bot.connection.Connection` should use.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProtocolVersion:
    """Numeric identifier for a wire protocol version.

    ``number`` — the protocol number on the handshake wire (e.g., 763).
    ``display_name`` — informational, e.g., ``"1.20.1"``.

    Two ProtocolVersions are equal iff their ``number`` matches; the
    ``display_name`` is informational only.
    """

    number: int
    display_name: str = ""

    def __post_init__(self) -> None:
        if self.number <= 0:
            raise ValueError(f"protocol number must be positive: {self.number}")


# Constants for each implemented protocol version.
V_1_20_1: ProtocolVersion = ProtocolVersion(number=763, display_name="1.20.1")


__all__ = ["ProtocolVersion", "V_1_20_1"]
