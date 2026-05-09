"""Packet `set_title_text` (play/clientbound, id 0x5F)."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string

PACKET_ID = 0x5F


@dataclass(frozen=True, slots=True)
class SetTitleText:
    text: str  # JSON chat component


def decode(reader: Reader) -> SetTitleText:
    return SetTitleText(text=string.read(reader))


def encode(packet: SetTitleText, writer: Writer) -> None:
    string.write(packet.text, writer)
