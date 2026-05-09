"""Packet `set_title_time` (play/clientbound, id 0x60).

Title timing in ticks: ``fade_in`` ramps in, ``stay`` holds, ``fade_out``
ramps out.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x60


@dataclass(frozen=True, slots=True)
class SetTitleTime:
    fade_in: int   # i32, ticks
    stay: int      # i32
    fade_out: int  # i32


def decode(reader: Reader) -> SetTitleTime:
    fi, st, fo = struct.unpack(">iii", reader.read(12))
    return SetTitleTime(fade_in=fi, stay=st, fade_out=fo)


def encode(packet: SetTitleTime, writer: Writer) -> None:
    writer.write(struct.pack(">iii", packet.fade_in, packet.stay, packet.fade_out))
