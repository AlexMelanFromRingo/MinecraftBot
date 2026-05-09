"""Packet `player_remove` (play/clientbound, id 0x39).

Removes one or more players from the tab list.
"""

from __future__ import annotations

import uuid as _uuid_stdlib
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, uuid as uuid_codec, varint

PACKET_ID = 0x39


@dataclass(frozen=True, slots=True)
class PlayerRemove:
    players: tuple[_uuid_stdlib.UUID, ...]


def decode(reader: Reader) -> PlayerRemove:
    n = varint.read(reader)
    uuids = tuple(uuid_codec.read(reader) for _ in range(n))
    return PlayerRemove(players=uuids)


def encode(packet: PlayerRemove, writer: Writer) -> None:
    varint.write(len(packet.players), writer)
    for u in packet.players:
        uuid_codec.write(u, writer)
