"""Packet `boss_bar` (play/clientbound, id 0x0B).

Manages a boss-bar UI element on the client. The wire format is::

    UUID id
    varint action  # 0=add, 1=remove, 2=update_health,
                   # 3=update_title, 4=update_style, 5=update_flags
    [action-specific fields...]

For Phase 4 we store the trailing action-specific bytes as opaque
``payload``. Structured decode of each action's fields is a Bot API
milestone task.
"""

from __future__ import annotations

import uuid as _uuid_stdlib
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, uuid as uuid_codec, varint

PACKET_ID = 0x0B


@dataclass(frozen=True, slots=True)
class BossBar:
    bar_id: _uuid_stdlib.UUID
    action: int        # varint, 0..5
    payload: bytes     # opaque action-specific bytes


def decode(reader: Reader) -> BossBar:
    u = uuid_codec.read(reader)
    act = varint.read(reader)
    pl = reader.read(reader.remaining())
    return BossBar(bar_id=u, action=act, payload=pl)


def encode(packet: BossBar, writer: Writer) -> None:
    uuid_codec.write(packet.bar_id, writer)
    varint.write(packet.action, writer)
    writer.write(packet.payload)
