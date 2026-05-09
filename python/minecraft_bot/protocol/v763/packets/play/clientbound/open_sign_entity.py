"""Packet `open_sign_entity` (play/clientbound, id 0x31).

Server tells the client to open the sign-edit UI for the sign at
``location``. ``is_front_text`` (added in 1.20) selects which side
of a hanging sign / standing sign to edit.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, position
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x31


@dataclass(frozen=True, slots=True)
class OpenSignEntity:
    location: tuple[int, int, int]
    is_front_text: bool


def decode(reader: Reader) -> OpenSignEntity:
    loc = position.read(reader)
    b = reader.read(1)[0]
    if b not in (0, 1):
        raise ValueOutOfRange("open_sign_entity.is_front_text", b)
    return OpenSignEntity(location=loc, is_front_text=b == 1)


def encode(packet: OpenSignEntity, writer: Writer) -> None:
    position.write(packet.location, writer)
    writer.write(b"\x01" if packet.is_front_text else b"\x00")
