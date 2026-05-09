"""Packet `set_passengers` (play/clientbound, id 0x59).

Updates which entities are riding a vehicle entity.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x59


@dataclass(frozen=True, slots=True)
class SetPassengers:
    entity_id: int                  # varint, the vehicle
    passengers: tuple[int, ...]     # varint ids


def decode(reader: Reader) -> SetPassengers:
    eid = varint.read(reader)
    n = varint.read(reader)
    pas = tuple(varint.read(reader) for _ in range(n))
    return SetPassengers(entity_id=eid, passengers=pas)


def encode(packet: SetPassengers, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    varint.write(len(packet.passengers), writer)
    for p in packet.passengers:
        varint.write(p, writer)
