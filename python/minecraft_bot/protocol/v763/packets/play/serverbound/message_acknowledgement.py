"""Packet `message_acknowledgement` (play/serverbound, id 0x03)."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x03


@dataclass(frozen=True, slots=True)
class MessageAcknowledgement:
    count: int  # varint, number of messages acknowledged


def decode(reader: Reader) -> MessageAcknowledgement:
    return MessageAcknowledgement(count=varint.read(reader))


def encode(packet: MessageAcknowledgement, writer: Writer) -> None:
    varint.write(packet.count, writer)
