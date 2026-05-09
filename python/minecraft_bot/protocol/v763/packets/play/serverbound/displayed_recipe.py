"""Packet `displayed_recipe` (play/serverbound, id 0x22)."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string

PACKET_ID = 0x22


@dataclass(frozen=True, slots=True)
class DisplayedRecipe:
    recipe_id: str


def decode(reader: Reader) -> DisplayedRecipe:
    return DisplayedRecipe(recipe_id=string.read(reader))


def encode(packet: DisplayedRecipe, writer: Writer) -> None:
    string.write(packet.recipe_id, writer)
