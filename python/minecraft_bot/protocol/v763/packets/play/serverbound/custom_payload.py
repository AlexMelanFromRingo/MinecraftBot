"""Packet `custom_payload` (play/serverbound, id 0x0D).

Plugin Message channel from client to server. Mirror of the
clientbound :class:`~minecraft_bot.protocol.v763.packets.play.clientbound.custom_payload.CustomPayload`.
Bots typically send a ``minecraft:brand`` payload right after entering
play, declaring their client identity.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string

PACKET_ID = 0x0D


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
