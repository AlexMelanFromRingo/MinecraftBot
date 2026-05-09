"""Packet `settings` (play/serverbound, id 0x08).

Client Information — sent right after the play state begins, telling
the server the client's locale, view distance, chat preferences, and
which skin parts are visible. Vanilla servers expect this packet
relatively early; missing it can cause some servers to disconnect.

Default values for an offline bot:
- locale: "en_us"
- view_distance: 10 chunks
- chat_flags: 0 (FULL — accept all chat)
- chat_colors: True
- skin_parts: 0x7F (all)
- main_hand: 1 (RIGHT)
- enable_text_filtering: False (offline mode never filters)
- enable_server_listing: True
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x08


@dataclass(frozen=True, slots=True)
class Settings:
    locale: str             # max 16 chars
    view_distance: int      # i8; 2..32 typical
    chat_flags: int         # varint: 0=FULL, 1=COMMANDS_ONLY, 2=HIDDEN
    chat_colors: bool
    skin_parts: int         # u8 bitfield
    main_hand: int          # varint: 0=LEFT, 1=RIGHT
    enable_text_filtering: bool
    enable_server_listing: bool


def _read_bool(reader: Reader) -> bool:
    b = reader.read(1)[0]
    if b not in (0, 1):
        raise ValueOutOfRange("bool", b)
    return b == 1


def decode(reader: Reader) -> Settings:
    locale = string.read(reader, max_length=16)
    (view_distance,) = struct.unpack(">b", reader.read(1))
    chat_flags = varint.read(reader)
    chat_colors = _read_bool(reader)
    (skin_parts,) = struct.unpack(">B", reader.read(1))
    main_hand = varint.read(reader)
    enable_text_filtering = _read_bool(reader)
    enable_server_listing = _read_bool(reader)
    return Settings(
        locale=locale, view_distance=view_distance,
        chat_flags=chat_flags, chat_colors=chat_colors,
        skin_parts=skin_parts, main_hand=main_hand,
        enable_text_filtering=enable_text_filtering,
        enable_server_listing=enable_server_listing,
    )


def encode(packet: Settings, writer: Writer) -> None:
    string.write(packet.locale, writer, max_length=16)
    writer.write(struct.pack(">b", packet.view_distance))
    varint.write(packet.chat_flags, writer)
    writer.write(b"\x01" if packet.chat_colors else b"\x00")
    if not 0 <= packet.skin_parts <= 0xFF:
        raise ValueOutOfRange("settings.skin_parts", packet.skin_parts)
    writer.write(struct.pack(">B", packet.skin_parts))
    varint.write(packet.main_hand, writer)
    writer.write(b"\x01" if packet.enable_text_filtering else b"\x00")
    writer.write(b"\x01" if packet.enable_server_listing else b"\x00")
