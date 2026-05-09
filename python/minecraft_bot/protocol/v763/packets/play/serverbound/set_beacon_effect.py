"""Packet `set_beacon_effect` (play/serverbound, id 0x27)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from minecraft_bot.codec import Reader, Writer, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x27


@dataclass(frozen=True, slots=True)
class SetBeaconEffect:
    primary_effect: Optional[int]    # varint, registry id; None = clear
    secondary_effect: Optional[int]


def _opt_varint(reader: Reader, name: str) -> Optional[int]:
    present = reader.read(1)[0]
    if present == 1:
        return varint.read(reader)
    if present == 0:
        return None
    raise ValueOutOfRange(name, present)


def decode(reader: Reader) -> SetBeaconEffect:
    p = _opt_varint(reader, "set_beacon_effect.primary.present")
    s = _opt_varint(reader, "set_beacon_effect.secondary.present")
    return SetBeaconEffect(primary_effect=p, secondary_effect=s)


def _write_opt_varint(value: Optional[int], writer: Writer) -> None:
    if value is None:
        writer.write(b"\x00")
    else:
        writer.write(b"\x01")
        varint.write(value, writer)


def encode(packet: SetBeaconEffect, writer: Writer) -> None:
    _write_opt_varint(packet.primary_effect, writer)
    _write_opt_varint(packet.secondary_effect, writer)
