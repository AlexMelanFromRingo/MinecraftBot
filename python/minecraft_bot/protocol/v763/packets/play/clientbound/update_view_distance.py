"""Packet `update_view_distance` (play/clientbound, id 0x4F).

Server-pushed view distance change. Affects how many chunks the client
loads around itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x4F


@dataclass(frozen=True, slots=True)
class UpdateViewDistance:
    view_distance: int  # varint


def decode(reader: Reader) -> UpdateViewDistance:
    return UpdateViewDistance(view_distance=varint.read(reader))


def encode(packet: UpdateViewDistance, writer: Writer) -> None:
    varint.write(packet.view_distance, writer)
