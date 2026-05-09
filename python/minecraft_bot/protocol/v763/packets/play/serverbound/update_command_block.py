"""Packet `update_command_block` (play/serverbound, id 0x29). Op-only."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, position, string, varint

PACKET_ID = 0x29


@dataclass(frozen=True, slots=True)
class UpdateCommandBlock:
    location: tuple[int, int, int]
    command: str
    mode: int        # varint: 0=sequence, 1=auto, 2=redstone
    flags: int       # u8 bitfield


def decode(reader: Reader) -> UpdateCommandBlock:
    loc = position.read(reader)
    cmd = string.read(reader)
    mode = varint.read(reader)
    flags = reader.read(1)[0]
    return UpdateCommandBlock(location=loc, command=cmd, mode=mode, flags=flags)


def encode(packet: UpdateCommandBlock, writer: Writer) -> None:
    position.write(packet.location, writer)
    string.write(packet.command, writer)
    varint.write(packet.mode, writer)
    writer.write(bytes([packet.flags & 0xFF]))
