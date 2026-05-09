"""Packet `position` (play/clientbound, id 0x3C).

Synchronize Player Position. Server pushes an authoritative position
to the client; the client must reply with a
:class:`~minecraft_bot.protocol.v763.packets.play.serverbound.teleport_confirm.TeleportConfirm`
echoing ``teleport_id``. The framework auto-confirms this packet
inside the decode loop (FR-006), so the developer's hooks see the
position update only after the confirm has been queued — and
critically, the framework MUST NOT echo a position update back
("moved too quickly" prevention from spec edge cases / past-incident
memory).

``flags`` is a bitfield: bit 0 X-rel, 1 Y-rel, 2 Z-rel, 3 Y-rot-rel,
4 X-rot-rel. Bot code that wants relative-movement awareness can
inspect it; the framework treats the position as authoritative
regardless.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x3C


@dataclass(frozen=True, slots=True)
class Position:
    x: float
    y: float
    z: float
    yaw: float
    pitch: float
    flags: int           # i8 bitfield (relative-movement flags)
    teleport_id: int     # varint; echoed back in TeleportConfirm


def decode(reader: Reader) -> Position:
    x, y, z = struct.unpack(">ddd", reader.read(24))
    yaw, pitch = struct.unpack(">ff", reader.read(8))
    (flags,) = struct.unpack(">b", reader.read(1))
    teleport_id = varint.read(reader)
    return Position(x=x, y=y, z=z, yaw=yaw, pitch=pitch, flags=flags, teleport_id=teleport_id)


def encode(packet: Position, writer: Writer) -> None:
    writer.write(struct.pack(">ddd", packet.x, packet.y, packet.z))
    writer.write(struct.pack(">ff", packet.yaw, packet.pitch))
    writer.write(struct.pack(">b", packet.flags))
    varint.write(packet.teleport_id, writer)
