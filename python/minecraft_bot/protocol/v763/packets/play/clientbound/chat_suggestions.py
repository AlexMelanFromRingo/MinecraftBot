"""Packet `chat_suggestions` (play/clientbound, id 0x16).

Server tells the client to add/remove/replace chat-completion
suggestion entries. ``action`` codes: 0=add, 1=remove, 2=set.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint

PACKET_ID = 0x16


@dataclass(frozen=True, slots=True)
class ChatSuggestions:
    action: int                 # varint
    entries: tuple[str, ...]


def decode(reader: Reader) -> ChatSuggestions:
    act = varint.read(reader)
    n = varint.read(reader)
    ents = tuple(string.read(reader) for _ in range(n))
    return ChatSuggestions(action=act, entries=ents)


def encode(packet: ChatSuggestions, writer: Writer) -> None:
    varint.write(packet.action, writer)
    varint.write(len(packet.entries), writer)
    for e in packet.entries:
        string.write(e, writer)
