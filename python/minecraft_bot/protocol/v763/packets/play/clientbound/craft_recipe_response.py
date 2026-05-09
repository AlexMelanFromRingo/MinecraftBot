"""Packet `craft_recipe_response` (play/clientbound, id 0x33).

Server's ack/reject for a serverbound craft-recipe request. ``recipe``
is the recipe identifier the client clicked on.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string

PACKET_ID = 0x33


@dataclass(frozen=True, slots=True)
class CraftRecipeResponse:
    window_id: int   # i8
    recipe: str      # identifier (e.g. "minecraft:diamond_pickaxe")


def decode(reader: Reader) -> CraftRecipeResponse:
    wid, = struct.unpack(">b", reader.read(1))
    rec = string.read(reader)
    return CraftRecipeResponse(window_id=wid, recipe=rec)


def encode(packet: CraftRecipeResponse, writer: Writer) -> None:
    writer.write(struct.pack(">b", packet.window_id))
    string.write(packet.recipe, writer)
