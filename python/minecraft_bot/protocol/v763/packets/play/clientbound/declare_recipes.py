"""Packet `declare_recipes` (play/clientbound, id 0x6D).

Server's full recipe registry. Each entry has a recipe-type identifier
plus type-specific data (shaped, shapeless, smelting, smithing, etc.).
The largest packet in the protocol by schema complexity.

Phase 4 captures the entire payload as opaque ``payload``. Structured
decode lands in the Bot API milestone (when crafting/auto-craft
features need it).
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x6D


@dataclass(frozen=True, slots=True)
class DeclareRecipes:
    payload: bytes  # opaque count + per-recipe entries


def decode(reader: Reader) -> DeclareRecipes:
    return DeclareRecipes(payload=reader.read(reader.remaining()))


def encode(packet: DeclareRecipes, writer: Writer) -> None:
    writer.write(packet.payload)
