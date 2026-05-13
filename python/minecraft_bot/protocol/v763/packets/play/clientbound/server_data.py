"""Packet `server_data` (play/clientbound, id 0x45).

MOTD + favicon + chat-security flag, sent on join and on
``/minecraft:server-info``-style requests.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x45


@dataclass(frozen=True, slots=True)
class ServerData:
    motd: str                        # JSON chat component
    icon_bytes: bytes | None      # raw PNG bytes, may be None
    enforces_secure_chat: bool


def decode(reader: Reader) -> ServerData:
    motd = string.read(reader)
    present = reader.read(1)[0]
    if present == 1:
        n = varint.read(reader)
        icon: bytes | None = reader.read(n)
    elif present == 0:
        icon = None
    else:
        raise ValueOutOfRange("server_data.icon.present", present)
    secure = reader.read(1)[0]
    if secure not in (0, 1):
        raise ValueOutOfRange("server_data.enforces_secure_chat", secure)
    return ServerData(motd=motd, icon_bytes=icon, enforces_secure_chat=secure == 1)


def encode(packet: ServerData, writer: Writer) -> None:
    string.write(packet.motd, writer)
    if packet.icon_bytes is None:
        writer.write(b"\x00")
    else:
        writer.write(b"\x01")
        varint.write(len(packet.icon_bytes), writer)
        writer.write(packet.icon_bytes)
    writer.write(b"\x01" if packet.enforces_secure_chat else b"\x00")
