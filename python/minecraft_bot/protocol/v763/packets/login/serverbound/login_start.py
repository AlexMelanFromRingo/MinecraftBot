"""Packet `login_start` (login/serverbound, id 0x00).

The first packet a client sends after the LOGIN state transition.
Carries the player name and (since 1.19.3) an optional pre-computed
profile UUID. For offline mode the framework computes the UUID from
the username via the standard Notchian formula, but the protocol
permits the field to be absent.
"""

from __future__ import annotations

import uuid as _uuid_stdlib
from dataclasses import dataclass
from typing import Optional

from minecraft_bot.codec import Reader, Writer, string, uuid
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x00


@dataclass(frozen=True, slots=True)
class LoginStart:
    username: str                          # max 16 chars
    player_uuid: Optional[_uuid_stdlib.UUID]


def decode(reader: Reader) -> LoginStart:
    username = string.read(reader)
    present = reader.read(1)[0]
    if present == 1:
        u: Optional[_uuid_stdlib.UUID] = uuid.read(reader)
    elif present == 0:
        u = None
    else:
        raise ValueOutOfRange("login_start.player_uuid.present", present)
    return LoginStart(username=username, player_uuid=u)


def encode(packet: LoginStart, writer: Writer) -> None:
    string.write(packet.username, writer)
    if packet.player_uuid is None:
        writer.write(b"\x00")
    else:
        writer.write(b"\x01")
        uuid.write(packet.player_uuid, writer)
