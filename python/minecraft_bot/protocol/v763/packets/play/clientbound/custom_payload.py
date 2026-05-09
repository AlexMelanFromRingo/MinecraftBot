"""Packet `custom_payload` (play/clientbound, id 0x17).

Plugin Message channel from server to client. ``channel`` is an
identifier (e.g., ``minecraft:brand``); ``data`` is opaque to the
framework. Common channels:

- ``minecraft:brand`` — server's "brand" string (Vanilla, Paper, ...)

The framework forwards these to subscribers; default response to
``minecraft:brand`` should send a serverbound ``custom_payload`` with
the bot's brand name.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string

PACKET_ID = 0x17


@dataclass(frozen=True, slots=True)
class CustomPayload:
    channel: str   # identifier
    data: bytes    # restBuffer


def decode(reader: Reader) -> CustomPayload:
    channel = string.read(reader)
    data = reader.read(reader.remaining())
    return CustomPayload(channel=channel, data=data)


def encode(packet: CustomPayload, writer: Writer) -> None:
    string.write(packet.channel, writer)
    writer.write(packet.data)
