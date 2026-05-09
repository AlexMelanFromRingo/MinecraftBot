"""Packet `update_jigsaw_block` (play/serverbound, id 0x2C). Op-only."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, position, string

PACKET_ID = 0x2C


@dataclass(frozen=True, slots=True)
class UpdateJigsawBlock:
    location: tuple[int, int, int]
    name: str
    target: str
    pool: str
    final_state: str
    joint_type: str


def decode(reader: Reader) -> UpdateJigsawBlock:
    return UpdateJigsawBlock(
        location=position.read(reader),
        name=string.read(reader),
        target=string.read(reader),
        pool=string.read(reader),
        final_state=string.read(reader),
        joint_type=string.read(reader),
    )


def encode(packet: UpdateJigsawBlock, writer: Writer) -> None:
    position.write(packet.location, writer)
    for s in (packet.name, packet.target, packet.pool, packet.final_state, packet.joint_type):
        string.write(s, writer)
