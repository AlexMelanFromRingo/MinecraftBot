"""Packet `set_protocol` (handshaking/serverbound, id 0x00).

The first packet sent on every connection. Tells the server which
protocol version the client speaks and which state to transition into
next (1 = STATUS, 2 = LOGIN).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint

PACKET_ID = 0x00


@dataclass(frozen=True, slots=True)
class SetProtocol:
    protocol_version: int   # varint, e.g. 763 for 1.20.1
    server_host: str        # the host the client connected to
    server_port: int        # u16, the port the client connected to
    next_state: int         # varint: 1 = status, 2 = login


def decode(reader: Reader) -> SetProtocol:
    return SetProtocol(
        protocol_version=varint.read(reader),
        server_host=string.read(reader),
        server_port=struct.unpack(">H", reader.read(2))[0],
        next_state=varint.read(reader),
    )


def encode(packet: SetProtocol, writer: Writer) -> None:
    varint.write(packet.protocol_version, writer)
    string.write(packet.server_host, writer)
    writer.write(struct.pack(">H", packet.server_port))
    varint.write(packet.next_state, writer)
