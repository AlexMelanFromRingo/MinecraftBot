"""Packet `sound_effect` (play/clientbound, id 0x62).

Plays a sound at world coordinates. The wire format begins with a
``sound`` selector — a VarInt sound ID; ``id == 0`` means the sound is
custom and the next bytes carry an ``Identifier`` plus an optional
``f32 range``.

Coordinates are in fixed-point eighth-blocks (i32 ``world * 8``).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x62


@dataclass(frozen=True, slots=True)
class SoundEffect:
    sound_id: int                # 0 = custom; 1+ = registry id
    custom_sound: str | None  # identifier; only if sound_id == 0
    custom_range: float | None  # f32, only when sound_id == 0 and range present
    sound_category: int          # varint enum
    x: int                       # i32 (world * 8)
    y: int                       # i32
    z: int                       # i32
    volume: float                # f32
    pitch: float                 # f32
    seed: int                    # i64


def decode(reader: Reader) -> SoundEffect:
    sid = varint.read(reader)
    if sid == 0:
        cs: str | None = string.read(reader)
        present = reader.read(1)[0]
        if present == 1:
            cr: float | None = struct.unpack(">f", reader.read(4))[0]
        elif present == 0:
            cr = None
        else:
            raise ValueOutOfRange("sound_effect.range.present", present)
    else:
        cs, cr = None, None
    cat = varint.read(reader)
    x, y, z = struct.unpack(">iii", reader.read(12))
    vol, pitch = struct.unpack(">ff", reader.read(8))
    seed, = struct.unpack(">q", reader.read(8))
    return SoundEffect(
        sound_id=sid, custom_sound=cs, custom_range=cr,
        sound_category=cat, x=x, y=y, z=z,
        volume=vol, pitch=pitch, seed=seed,
    )


def encode(packet: SoundEffect, writer: Writer) -> None:
    varint.write(packet.sound_id, writer)
    if packet.sound_id == 0:
        if packet.custom_sound is None:
            raise ValueOutOfRange("sound_effect.custom_sound", None)
        string.write(packet.custom_sound, writer)
        if packet.custom_range is None:
            writer.write(b"\x00")
        else:
            writer.write(b"\x01")
            writer.write(struct.pack(">f", packet.custom_range))
    varint.write(packet.sound_category, writer)
    writer.write(struct.pack(">iii", packet.x, packet.y, packet.z))
    writer.write(struct.pack(">ff", packet.volume, packet.pitch))
    writer.write(struct.pack(">q", packet.seed))
