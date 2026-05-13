"""Packet `profileless_chat` (play/clientbound, id 0x1B).

Chat from a non-player source (server console, command output) routed
through the chat type registry.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x1B


@dataclass(frozen=True, slots=True)
class ProfilelessChat:
    message: str       # JSON chat component
    chat_type: int     # varint registry id
    name: str          # JSON chat component (sender display name)
    target: str | None  # JSON chat component (e.g., for /msg target)


def decode(reader: Reader) -> ProfilelessChat:
    msg = string.read(reader)
    ct = varint.read(reader)
    nm = string.read(reader)
    present = reader.read(1)[0]
    if present == 1:
        tg: str | None = string.read(reader)
    elif present == 0:
        tg = None
    else:
        raise ValueOutOfRange("profileless_chat.target.present", present)
    return ProfilelessChat(message=msg, chat_type=ct, name=nm, target=tg)


def encode(packet: ProfilelessChat, writer: Writer) -> None:
    string.write(packet.message, writer)
    varint.write(packet.chat_type, writer)
    string.write(packet.name, writer)
    if packet.target is None:
        writer.write(b"\x00")
    else:
        writer.write(b"\x01")
        string.write(packet.target, writer)
