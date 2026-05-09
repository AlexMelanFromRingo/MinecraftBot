"""Packet `camera` (play/clientbound, id 0x4C).

Switches the client's view to follow the entity with id ``camera_id``.
``camera_id`` equal to the player's own entity ID restores normal view.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x4C


@dataclass(frozen=True, slots=True)
class Camera:
    camera_id: int  # varint


def decode(reader: Reader) -> Camera:
    return Camera(camera_id=varint.read(reader))


def encode(packet: Camera, writer: Writer) -> None:
    varint.write(packet.camera_id, writer)
