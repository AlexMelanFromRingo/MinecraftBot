"""Packet `block_dig` (play/serverbound, id 0x1D).

Player dig action. ``status`` codes: 0=start digging, 1=cancel digging,
2=finish digging, 3=drop item stack, 4=drop item, 5=shoot/finish use,
6=swap items in hands.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, position, varint

PACKET_ID = 0x1D


@dataclass(frozen=True, slots=True)
class BlockDig:
    status: int                       # varint
    location: tuple[int, int, int]
    face: int                         # i8
    sequence: int                     # varint


def decode(reader: Reader) -> BlockDig:
    st = varint.read(reader)
    loc = position.read(reader)
    f, = struct.unpack(">b", reader.read(1))
    seq = varint.read(reader)
    return BlockDig(status=st, location=loc, face=f, sequence=seq)


def encode(packet: BlockDig, writer: Writer) -> None:
    varint.write(packet.status, writer)
    position.write(packet.location, writer)
    writer.write(struct.pack(">b", packet.face))
    varint.write(packet.sequence, writer)
