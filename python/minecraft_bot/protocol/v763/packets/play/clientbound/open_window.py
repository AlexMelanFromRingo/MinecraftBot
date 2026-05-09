"""Packet `open_window` (play/clientbound, id 0x30).

Server tells the client to open a container UI. ``inventory_type`` is
the window's registry id (chest, furnace, anvil, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint

PACKET_ID = 0x30


@dataclass(frozen=True, slots=True)
class OpenWindow:
    window_id: int        # varint
    inventory_type: int   # varint, registry id
    window_title: str     # JSON chat component


def decode(reader: Reader) -> OpenWindow:
    wid = varint.read(reader)
    it = varint.read(reader)
    title = string.read(reader)
    return OpenWindow(window_id=wid, inventory_type=it, window_title=title)


def encode(packet: OpenWindow, writer: Writer) -> None:
    varint.write(packet.window_id, writer)
    varint.write(packet.inventory_type, writer)
    string.write(packet.window_title, writer)
