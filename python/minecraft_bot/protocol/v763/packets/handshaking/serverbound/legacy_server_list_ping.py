"""Packet `legacy_server_list_ping` (handshaking/serverbound, id 0xFE).

A pre-1.7 legacy ping mechanism. Modern clients never send this; it's
included for completeness. The body is opaque legacy bytes that the
framework treats as a single ``payload: bytes`` field.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0xFE


@dataclass(frozen=True, slots=True)
class LegacyServerListPing:
    payload: bytes


def decode(reader: Reader) -> LegacyServerListPing:
    return LegacyServerListPing(payload=reader.read(reader.remaining()))


def encode(packet: LegacyServerListPing, writer: Writer) -> None:
    writer.write(packet.payload)
