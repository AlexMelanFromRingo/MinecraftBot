"""Packet `tab_complete` (play/clientbound, id 0x0F).

Server's reply to a serverbound `tab_complete` request: a list of
matches, each with an optional tooltip.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x0F


@dataclass(frozen=True, slots=True)
class TabCompleteMatch:
    match: str
    tooltip: str | None  # JSON chat component, may be None


@dataclass(frozen=True, slots=True)
class TabComplete:
    transaction_id: int
    start: int
    length: int
    matches: tuple[TabCompleteMatch, ...]


def decode(reader: Reader) -> TabComplete:
    tid = varint.read(reader)
    st = varint.read(reader)
    ln = varint.read(reader)
    n = varint.read(reader)
    matches: list[TabCompleteMatch] = []
    for _ in range(n):
        m = string.read(reader)
        present = reader.read(1)[0]
        if present == 1:
            tip: str | None = string.read(reader)
        elif present == 0:
            tip = None
        else:
            raise ValueOutOfRange("tab_complete.match.tooltip.present", present)
        matches.append(TabCompleteMatch(match=m, tooltip=tip))
    return TabComplete(transaction_id=tid, start=st, length=ln, matches=tuple(matches))


def encode(packet: TabComplete, writer: Writer) -> None:
    varint.write(packet.transaction_id, writer)
    varint.write(packet.start, writer)
    varint.write(packet.length, writer)
    varint.write(len(packet.matches), writer)
    for m in packet.matches:
        string.write(m.match, writer)
        if m.tooltip is None:
            writer.write(b"\x00")
        else:
            writer.write(b"\x01")
            string.write(m.tooltip, writer)
