"""Packet `initialize_world_border` (play/clientbound, id 0x22).

Full world-border state on join. After this, individual world_border_*
packets handle in-flight updates.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x22


@dataclass(frozen=True, slots=True)
class InitializeWorldBorder:
    x: float
    z: float
    old_diameter: float
    new_diameter: float
    speed: int                    # varint, ticks for the lerp
    portal_teleport_boundary: int # varint, blocks
    warning_blocks: int           # varint
    warning_time: int             # varint, seconds


def decode(reader: Reader) -> InitializeWorldBorder:
    x, z, old_d, new_d = struct.unpack(">dddd", reader.read(32))
    speed = varint.read(reader)
    ptb = varint.read(reader)
    wb = varint.read(reader)
    wt = varint.read(reader)
    return InitializeWorldBorder(
        x=x, z=z, old_diameter=old_d, new_diameter=new_d,
        speed=speed, portal_teleport_boundary=ptb,
        warning_blocks=wb, warning_time=wt,
    )


def encode(packet: InitializeWorldBorder, writer: Writer) -> None:
    writer.write(struct.pack(">dddd", packet.x, packet.z,
                              packet.old_diameter, packet.new_diameter))
    varint.write(packet.speed, writer)
    varint.write(packet.portal_teleport_boundary, writer)
    varint.write(packet.warning_blocks, writer)
    varint.write(packet.warning_time, writer)
