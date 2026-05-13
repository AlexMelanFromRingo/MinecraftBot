"""Packet `success` (login/clientbound, id 0x02).

Server's confirmation that login succeeded. Receiving this packet
transitions the connection from LOGIN to PLAY.
"""

from __future__ import annotations

import uuid as _uuid_stdlib
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, uuid, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x02


@dataclass(frozen=True, slots=True)
class Property:
    name: str
    value: str
    signature: str | None  # None when absent


@dataclass(frozen=True, slots=True)
class Success:
    uuid: _uuid_stdlib.UUID
    username: str
    properties: tuple[Property, ...]


def decode(reader: Reader) -> Success:
    u = uuid.read(reader)
    name = string.read(reader)
    n_props = varint.read(reader)
    props: list[Property] = []
    for _ in range(n_props):
        prop_name = string.read(reader)
        prop_value = string.read(reader)
        signed = reader.read(1)[0]
        if signed == 1:
            signature: str | None = string.read(reader)
        elif signed == 0:
            signature = None
        else:
            raise ValueOutOfRange("success.properties.signature.present", signed)
        props.append(Property(name=prop_name, value=prop_value, signature=signature))
    return Success(uuid=u, username=name, properties=tuple(props))


def encode(packet: Success, writer: Writer) -> None:
    uuid.write(packet.uuid, writer)
    string.write(packet.username, writer)
    varint.write(len(packet.properties), writer)
    for prop in packet.properties:
        string.write(prop.name, writer)
        string.write(prop.value, writer)
        if prop.signature is None:
            writer.write(b"\x00")
        else:
            writer.write(b"\x01")
            string.write(prop.signature, writer)
