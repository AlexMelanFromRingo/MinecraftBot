"""Packet `statistics` (play/clientbound, id 0x05).

Server-pushed list of player statistics (kills, blocks broken, distance
walked, etc.). Sent in response to a serverbound request.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x05


@dataclass(frozen=True, slots=True)
class StatisticEntry:
    category_id: int   # varint, registry id of the stat category
    statistic_id: int  # varint, registry id of the statistic
    value: int         # varint, the count


@dataclass(frozen=True, slots=True)
class Statistics:
    entries: tuple[StatisticEntry, ...]


def decode(reader: Reader) -> Statistics:
    n = varint.read(reader)
    entries: list[StatisticEntry] = []
    for _ in range(n):
        cid = varint.read(reader)
        sid = varint.read(reader)
        val = varint.read(reader)
        entries.append(StatisticEntry(category_id=cid, statistic_id=sid, value=val))
    return Statistics(entries=tuple(entries))


def encode(packet: Statistics, writer: Writer) -> None:
    varint.write(len(packet.entries), writer)
    for e in packet.entries:
        varint.write(e.category_id, writer)
        varint.write(e.statistic_id, writer)
        varint.write(e.value, writer)
