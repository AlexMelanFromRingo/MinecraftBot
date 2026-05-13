"""Packet `entity_equipment` (play/clientbound, id 0x55).

Updates an entity's worn/held items. The wire format uses a "top-bit
terminated array": each entry's slot byte's high bit (0x80) indicates
"more entries follow"; clearing the bit marks the last entry. Slot
codes 0-5 are: main hand, off hand, boots, leggings, chestplate, helmet.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, slot, varint

PACKET_ID = 0x55


@dataclass(frozen=True, slots=True)
class EquipmentEntry:
    slot: int                       # i8 (0..5); top bit reserved for stream
    item: slot.SlotData | None


@dataclass(frozen=True, slots=True)
class EntityEquipment:
    entity_id: int
    equipments: tuple[EquipmentEntry, ...]


def decode(reader: Reader) -> EntityEquipment:
    eid = varint.read(reader)
    entries: list[EquipmentEntry] = []
    while True:
        raw_slot = reader.read(1)[0]
        more = bool(raw_slot & 0x80)
        s = raw_slot & 0x7F
        if s & 0x40:
            s -= 0x80  # sign-extend lower 7 bits to i8
        item = slot.read(reader)
        entries.append(EquipmentEntry(slot=s, item=item))
        if not more:
            break
    return EntityEquipment(entity_id=eid, equipments=tuple(entries))


def encode(packet: EntityEquipment, writer: Writer) -> None:
    varint.write(packet.entity_id, writer)
    for i, entry in enumerate(packet.equipments):
        is_last = i == len(packet.equipments) - 1
        if not -64 <= entry.slot <= 63:
            from minecraft_bot.errors import ValueOutOfRange
            raise ValueOutOfRange("entity_equipment.slot", entry.slot)
        # Encode slot in low 7 bits (signed) plus continuation bit.
        b = (entry.slot & 0x7F) | (0x00 if is_last else 0x80)
        writer.write(bytes([b]))
        slot.write(entry.item, writer)
