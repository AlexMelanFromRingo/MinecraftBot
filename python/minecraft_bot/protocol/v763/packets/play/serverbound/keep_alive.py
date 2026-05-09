"""Packet `keep_alive` (play/serverbound, id 0x12).

Client → server keep-alive reply. Sent automatically by the framework's
decode loop (FR-005) in the critical path the moment a clientbound
:class:`~minecraft_bot.protocol.v763.packets.play.clientbound.keep_alive.KeepAlive`
arrives, before any user hook runs.

Note: PrismarineJS minecraft-data lists this packet at id 0x12 for
protocol 763; verify at runtime via the registry.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x12


@dataclass(frozen=True, slots=True)
class KeepAlive:
    keep_alive_id: int  # i64; must match the clientbound keepAliveId


def decode(reader: Reader) -> KeepAlive:
    return KeepAlive(keep_alive_id=struct.unpack(">q", reader.read(8))[0])


def encode(packet: KeepAlive, writer: Writer) -> None:
    writer.write(struct.pack(">q", packet.keep_alive_id))
