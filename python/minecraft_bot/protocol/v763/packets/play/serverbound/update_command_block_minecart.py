"""Packet `update_command_block_minecart` (play/serverbound, id 0x2A). Op-only."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x2A


@dataclass(frozen=True, slots=True)
class UpdateCommandBlockMinecart:
    entity_id: int
    command: str
    track_output: bool


def decode(reader: Reader) -> UpdateCommandBlockMinecart:
    eid = varint.read(reader)
    cmd = string.read(reader)
    to = reader.read(1)[0]
    if to not in (0, 1):
        raise ValueOutOfRange("update_command_block_minecart.track_output", to)
    return UpdateCommandBlockMinecart(entity_id=eid, command=cmd, track_output=to == 1)


def encode(packet: UpdateCommandBlockMinecart, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    string.write(packet.command, writer)
    writer.write(b"\x01" if packet.track_output else b"\x00")
