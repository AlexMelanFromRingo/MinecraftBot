"""Packet `trade_list` (play/clientbound, id 0x2A).

A villager's trade offers. Each trade has buy items (1-2), an output
item, demand metrics, and trade flags. Phase 4 captures the trailing
trade list as opaque bytes after the window-id header.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x2A


@dataclass(frozen=True, slots=True)
class TradeList:
    window_id: int     # varint
    payload: bytes     # opaque tail (count + per-trade containers + meta)


def decode(reader: Reader) -> TradeList:
    wid = varint.read(reader)
    pl = reader.read(reader.remaining())
    return TradeList(window_id=wid, payload=pl)


def encode(packet: TradeList, writer: Writer) -> None:
    varint.write(packet.window_id, writer)
    writer.write(packet.payload)
