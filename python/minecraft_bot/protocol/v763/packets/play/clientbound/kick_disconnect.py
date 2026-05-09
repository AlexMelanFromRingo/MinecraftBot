"""Packet `kick_disconnect` (play/clientbound, id 0x1A).

Server-initiated disconnect during the PLAY state (typical "kick").
Surfaced via :class:`~minecraft_bot.errors.KickedByServer`.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string

PACKET_ID = 0x1A


@dataclass(frozen=True, slots=True)
class KickDisconnect:
    reason: str  # JSON chat component


def decode(reader: Reader) -> KickDisconnect:
    return KickDisconnect(reason=string.read(reader))


def encode(packet: KickDisconnect, writer: Writer) -> None:
    string.write(packet.reason, writer)
