"""Packet `spectate` (play/serverbound, id 0x30). Spectator-mode teleport-to-player."""

from __future__ import annotations

import uuid as _uuid_stdlib
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, uuid as uuid_codec

PACKET_ID = 0x30


@dataclass(frozen=True, slots=True)
class Spectate:
    target: _uuid_stdlib.UUID


def decode(reader: Reader) -> Spectate:
    return Spectate(target=uuid_codec.read(reader))


def encode(packet: Spectate, writer: Writer) -> None:
    uuid_codec.write(packet.target, writer)
