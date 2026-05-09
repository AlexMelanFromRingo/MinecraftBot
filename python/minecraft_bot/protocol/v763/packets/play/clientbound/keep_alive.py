"""Packet `keep_alive` (play/clientbound, id 0x23).

Server → client heartbeat. The framework's decode loop auto-replies
with the matching :class:`~minecraft_bot.protocol.v763.packets.play.serverbound.keep_alive.KeepAlive`
inside the critical path (R-07) so a slow user hook cannot starve
the keep-alive cycle (FR-005).

Note: PrismarineJS minecraft-data lists this packet at id 0x23 for
protocol 763; verify against the registry at runtime.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x23


@dataclass(frozen=True, slots=True)
class KeepAlive:
    keep_alive_id: int  # i64


def decode(reader: Reader) -> KeepAlive:
    return KeepAlive(keep_alive_id=struct.unpack(">q", reader.read(8))[0])


def encode(packet: KeepAlive, writer: Writer) -> None:
    writer.write(struct.pack(">q", packet.keep_alive_id))
