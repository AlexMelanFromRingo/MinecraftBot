"""Packet `update_view_position` (play/clientbound, id 0x4E).

Updates the client's "center chunk" — the chunk the player is in. Used
to drive view-distance loading.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x4E


@dataclass(frozen=True, slots=True)
class UpdateViewPosition:
    chunk_x: int  # varint
    chunk_z: int  # varint


def decode(reader: Reader) -> UpdateViewPosition:
    cx = varint.read(reader)
    cz = varint.read(reader)
    return UpdateViewPosition(chunk_x=cx, chunk_z=cz)


def encode(packet: UpdateViewPosition, writer: Writer) -> None:
    varint.write(packet.chunk_x, writer)
    varint.write(packet.chunk_z, writer)
