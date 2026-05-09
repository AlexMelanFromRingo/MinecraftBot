"""Packet `player_chat` (play/clientbound, id 0x35).

Signed chat from a player. Carries the sender UUID, message body,
optional signature, chat-type info, and last-seen-message acknowledgements.
Wire format is large with several conditional sections.

Phase 4 captures everything after the sender UUID as opaque bytes.
Structured decode is a Bot API milestone task; for offline-mode bots
this is rarely needed.
"""

from __future__ import annotations

import uuid as _uuid_stdlib
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, uuid as uuid_codec

PACKET_ID = 0x35


@dataclass(frozen=True, slots=True)
class PlayerChat:
    sender: _uuid_stdlib.UUID
    payload: bytes


def decode(reader: Reader) -> PlayerChat:
    s = uuid_codec.read(reader)
    pl = reader.read(reader.remaining())
    return PlayerChat(sender=s, payload=pl)


def encode(packet: PlayerChat, writer: Writer) -> None:
    uuid_codec.write(packet.sender, writer)
    writer.write(packet.payload)
