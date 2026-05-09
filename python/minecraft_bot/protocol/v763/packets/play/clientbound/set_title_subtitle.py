"""Packet `set_title_subtitle` (play/clientbound, id 0x5D)."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string

PACKET_ID = 0x5D


@dataclass(frozen=True, slots=True)
class SetTitleSubtitle:
    text: str  # JSON chat component


def decode(reader: Reader) -> SetTitleSubtitle:
    return SetTitleSubtitle(text=string.read(reader))


def encode(packet: SetTitleSubtitle, writer: Writer) -> None:
    string.write(packet.text, writer)
