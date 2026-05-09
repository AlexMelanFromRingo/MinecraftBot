"""Packet `simulation_distance` (play/clientbound, id 0x5C).

Distance (in chunks) within which entities tick. Generally <= view_distance.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x5C


@dataclass(frozen=True, slots=True)
class SimulationDistance:
    distance: int  # varint, chunks


def decode(reader: Reader) -> SimulationDistance:
    return SimulationDistance(distance=varint.read(reader))


def encode(packet: SimulationDistance, writer: Writer) -> None:
    varint.write(packet.distance, writer)
