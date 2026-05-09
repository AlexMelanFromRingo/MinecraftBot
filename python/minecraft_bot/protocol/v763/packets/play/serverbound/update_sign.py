"""Packet `update_sign` (play/serverbound, id 0x2E)."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, position, string
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x2E


@dataclass(frozen=True, slots=True)
class UpdateSign:
    location: tuple[int, int, int]
    is_front_text: bool
    line1: str
    line2: str
    line3: str
    line4: str


def decode(reader: Reader) -> UpdateSign:
    loc = position.read(reader)
    front = reader.read(1)[0]
    if front not in (0, 1):
        raise ValueOutOfRange("update_sign.is_front_text", front)
    l1 = string.read(reader, max_length=384)
    l2 = string.read(reader, max_length=384)
    l3 = string.read(reader, max_length=384)
    l4 = string.read(reader, max_length=384)
    return UpdateSign(location=loc, is_front_text=front == 1,
                      line1=l1, line2=l2, line3=l3, line4=l4)


def encode(packet: UpdateSign, writer: Writer) -> None:
    position.write(packet.location, writer)
    writer.write(b"\x01" if packet.is_front_text else b"\x00")
    string.write(packet.line1, writer, max_length=384)
    string.write(packet.line2, writer, max_length=384)
    string.write(packet.line3, writer, max_length=384)
    string.write(packet.line4, writer, max_length=384)
