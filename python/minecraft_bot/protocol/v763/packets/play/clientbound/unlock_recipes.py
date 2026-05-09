"""Packet `unlock_recipes` (play/clientbound, id 0x3D).

Server announces or modifies the player's known recipes. ``action``
codes: 0=init, 1=add, 2=remove. ``recipes2`` (a second array) is
present only on action 0.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x3D


@dataclass(frozen=True, slots=True)
class UnlockRecipes:
    action: int                       # varint: 0/1/2
    crafting_book_open: bool
    filtering_craftable: bool
    smelting_book_open: bool
    filtering_smeltable: bool
    blast_furnace_open: bool
    filtering_blast_furnace: bool
    smoker_book_open: bool
    filtering_smoker: bool
    recipes_1: tuple[str, ...]
    recipes_2: tuple[str, ...]        # empty unless action == 0


def _read_bool(reader: Reader, field: str) -> bool:
    b = reader.read(1)[0]
    if b not in (0, 1):
        raise ValueOutOfRange(field, b)
    return b == 1


def decode(reader: Reader) -> UnlockRecipes:
    act = varint.read(reader)
    flags = [_read_bool(reader, f"unlock_recipes.flag{i}") for i in range(8)]
    n1 = varint.read(reader)
    r1 = tuple(string.read(reader) for _ in range(n1))
    if act == 0:
        n2 = varint.read(reader)
        r2 = tuple(string.read(reader) for _ in range(n2))
    else:
        r2 = ()
    return UnlockRecipes(
        action=act,
        crafting_book_open=flags[0], filtering_craftable=flags[1],
        smelting_book_open=flags[2], filtering_smeltable=flags[3],
        blast_furnace_open=flags[4], filtering_blast_furnace=flags[5],
        smoker_book_open=flags[6], filtering_smoker=flags[7],
        recipes_1=r1, recipes_2=r2,
    )


def encode(packet: UnlockRecipes, writer: Writer) -> None:
    varint.write(packet.action, writer)
    for f in (packet.crafting_book_open, packet.filtering_craftable,
              packet.smelting_book_open, packet.filtering_smeltable,
              packet.blast_furnace_open, packet.filtering_blast_furnace,
              packet.smoker_book_open, packet.filtering_smoker):
        writer.write(b"\x01" if f else b"\x00")
    varint.write(len(packet.recipes_1), writer)
    for r in packet.recipes_1:
        string.write(r, writer)
    if packet.action == 0:
        varint.write(len(packet.recipes_2), writer)
        for r in packet.recipes_2:
            string.write(r, writer)
