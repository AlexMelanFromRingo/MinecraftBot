"""Packet `resource_pack_receive` (play/serverbound, id 0x24).

Client tells the server how it handled a clientbound resource_pack_send.
``result``: 0=success, 1=declined, 2=failed-download, 3=accepted, 4=downloaded, 5=invalid-url, 6=failed-reload, 7=discarded.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x24


@dataclass(frozen=True, slots=True)
class ResourcePackReceive:
    result: int  # varint enum


def decode(reader: Reader) -> ResourcePackReceive:
    return ResourcePackReceive(result=varint.read(reader))


def encode(packet: ResourcePackReceive, writer: Writer) -> None:
    varint.write(packet.result, writer)
