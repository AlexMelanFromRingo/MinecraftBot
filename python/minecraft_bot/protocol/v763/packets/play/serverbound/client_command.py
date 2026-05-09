"""Packet `client_command` (play/serverbound, id 0x07).

Action: 0=Perform respawn (after death), 1=Request stats.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x07


@dataclass(frozen=True, slots=True)
class ClientCommand:
    action_id: int  # varint


def decode(reader: Reader) -> ClientCommand:
    return ClientCommand(action_id=varint.read(reader))


def encode(packet: ClientCommand, writer: Writer) -> None:
    varint.write(packet.action_id, writer)
