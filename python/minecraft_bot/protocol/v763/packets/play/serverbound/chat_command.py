"""Packet `chat_command` (play/serverbound, id 0x04).

Client sends a slash command. Carries a timestamp + salt + an array of
per-argument signatures + last-seen-message metadata. The signature
sub-fields are opaque to the framework (offline-mode bots send empty
signatures).

Phase 5 keeps everything after the command string as opaque ``payload``.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string

PACKET_ID = 0x04


@dataclass(frozen=True, slots=True)
class ChatCommand:
    command: str       # max 256 chars
    payload: bytes     # opaque (timestamp/salt/sigs/ack metadata)


def decode(reader: Reader) -> ChatCommand:
    cmd = string.read(reader, max_length=256)
    pl = reader.read(reader.remaining())
    return ChatCommand(command=cmd, payload=pl)


def encode(packet: ChatCommand, writer: Writer) -> None:
    string.write(packet.command, writer, max_length=256)
    writer.write(packet.payload)
