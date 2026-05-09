"""Packet `teleport_confirm` (play/serverbound, id 0x00).

Client confirms it received and applied a server-pushed
:class:`~minecraft_bot.protocol.v763.packets.play.clientbound.position.Position`.
Sent automatically by the framework's decode loop (FR-006) in the
critical path. The framework MUST NOT also echo a position update
back to the server — that triggers "moved too quickly" anti-cheat
(see spec edge cases / past-incident memory).
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x00


@dataclass(frozen=True, slots=True)
class TeleportConfirm:
    teleport_id: int  # varint; echoes the value from the clientbound Position


def decode(reader: Reader) -> TeleportConfirm:
    return TeleportConfirm(teleport_id=varint.read(reader))


def encode(packet: TeleportConfirm, writer: Writer) -> None:
    varint.write(packet.teleport_id, writer)
