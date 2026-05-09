"""Packet `craft_recipe_request` (play/serverbound, id 0x1B)."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x1B


@dataclass(frozen=True, slots=True)
class CraftRecipeRequest:
    window_id: int  # i8
    recipe: str
    make_all: bool


def decode(reader: Reader) -> CraftRecipeRequest:
    wid, = struct.unpack(">b", reader.read(1))
    rec = string.read(reader)
    ma = reader.read(1)[0]
    if ma not in (0, 1):
        raise ValueOutOfRange("craft_recipe_request.make_all", ma)
    return CraftRecipeRequest(window_id=wid, recipe=rec, make_all=ma == 1)


def encode(packet: CraftRecipeRequest, writer: Writer) -> None:
    writer.write(struct.pack(">b", packet.window_id))
    string.write(packet.recipe, writer)
    writer.write(b"\x01" if packet.make_all else b"\x00")
