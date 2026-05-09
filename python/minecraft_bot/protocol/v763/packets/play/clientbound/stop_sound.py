"""Packet `stop_sound` (play/clientbound, id 0x63).

Stops a currently-playing sound. ``flags`` is a bitfield::

    0x01  source provided
    0x02  sound name provided

Both fields are optional and present only when their flag bit is set.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional

from minecraft_bot.codec import Reader, Writer, string, varint

PACKET_ID = 0x63


@dataclass(frozen=True, slots=True)
class StopSound:
    flags: int                # i8 bitfield
    source: Optional[int]     # varint, present iff (flags & 0x01)
    sound: Optional[str]      # identifier, present iff (flags & 0x02)


def decode(reader: Reader) -> StopSound:
    flags, = struct.unpack(">b", reader.read(1))
    src: Optional[int] = None
    snd: Optional[str] = None
    if flags & 0x01:
        src = varint.read(reader)
    if flags & 0x02:
        snd = string.read(reader)
    return StopSound(flags=flags, source=src, sound=snd)


def encode(packet: StopSound, writer: Writer) -> None:
    writer.write(struct.pack(">b", packet.flags))
    if packet.flags & 0x01:
        if packet.source is None:
            from minecraft_bot.errors import ValueOutOfRange
            raise ValueOutOfRange("stop_sound.source", packet.source)
        varint.write(packet.source, writer)
    if packet.flags & 0x02:
        if packet.sound is None:
            from minecraft_bot.errors import ValueOutOfRange
            raise ValueOutOfRange("stop_sound.sound", packet.sound)
        string.write(packet.sound, writer)
