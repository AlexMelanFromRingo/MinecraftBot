"""Packet `server_info` (status/clientbound, id 0x00).

Server's response to a status request. ``response`` is a JSON string
describing the server (version, players, MOTD, favicon).
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string

PACKET_ID = 0x00


@dataclass(frozen=True, slots=True)
class ServerInfo:
    response: str  # raw JSON; caller may json.loads if needed


def decode(reader: Reader) -> ServerInfo:
    return ServerInfo(response=string.read(reader))


def encode(packet: ServerInfo, writer: Writer) -> None:
    string.write(packet.response, writer)
