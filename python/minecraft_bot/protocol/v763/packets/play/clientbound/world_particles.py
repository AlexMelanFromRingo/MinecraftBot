"""Packet `world_particles` (play/clientbound, id 0x26).

Spawns particles at a world position. The trailing ``data`` field is a
type-dependent payload whose shape is selected by ``particle_id``.

Per protocol-data, the data section uses a ``particleData`` switch type
keyed on ``particleId``. For most particles ``data`` is empty; for a
small subset (block, dust, item, vibration, sculk_charge, shriek) it
carries a few bytes. To preserve byte-faithful round-trip without
bloating each packet file with the full type-table switch, we capture
``data`` as opaque ``bytes`` consisting of the rest of the packet
payload. Bot-API consumers that need typed access can parse it per
particle type using the Bot API milestone helpers.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x26


@dataclass(frozen=True, slots=True)
class WorldParticles:
    particle_id: int
    long_distance: bool
    x: float
    y: float
    z: float
    offset_x: float    # f32
    offset_y: float
    offset_z: float
    particle_data: float  # f32, e.g. velocity multiplier
    particle_count: int   # i32
    data: bytes        # opaque tail; type-specific shape, see docstring


def decode(reader: Reader) -> WorldParticles:
    pid = varint.read(reader)
    ld = reader.read(1)[0]
    if ld not in (0, 1):
        raise ValueOutOfRange("world_particles.long_distance", ld)
    x, y, z = struct.unpack(">ddd", reader.read(24))
    ox, oy, oz, pdata = struct.unpack(">ffff", reader.read(16))
    cnt, = struct.unpack(">i", reader.read(4))
    data = reader.read(reader.remaining())
    return WorldParticles(
        particle_id=pid, long_distance=ld == 1, x=x, y=y, z=z,
        offset_x=ox, offset_y=oy, offset_z=oz,
        particle_data=pdata, particle_count=cnt, data=data,
    )


def encode(packet: WorldParticles, writer: Writer) -> None:
    varint.write(packet.particle_id, writer)
    writer.write(b"\x01" if packet.long_distance else b"\x00")
    writer.write(struct.pack(">ddd", packet.x, packet.y, packet.z))
    writer.write(struct.pack(">ffff", packet.offset_x, packet.offset_y,
                              packet.offset_z, packet.particle_data))
    writer.write(struct.pack(">i", packet.particle_count))
    writer.write(packet.data)
