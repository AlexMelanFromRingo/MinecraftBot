"""Packet `select_trade` (play/serverbound, id 0x26)."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x26


@dataclass(frozen=True, slots=True)
class SelectTrade:
    slot: int  # varint, trade slot index


def decode(reader: Reader) -> SelectTrade:
    return SelectTrade(slot=varint.read(reader))


def encode(packet: SelectTrade, writer: Writer) -> None:
    varint.write(packet.slot, writer)
