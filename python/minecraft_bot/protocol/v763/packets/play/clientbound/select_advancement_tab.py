"""Packet `select_advancement_tab` (play/clientbound, id 0x44).

Tells the client which advancement tab to display. ``id`` is ``None`` to
deselect (close the tab).
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x44


@dataclass(frozen=True, slots=True)
class SelectAdvancementTab:
    id: str | None  # advancement identifier, or None


def decode(reader: Reader) -> SelectAdvancementTab:
    present = reader.read(1)[0]
    if present == 1:
        return SelectAdvancementTab(id=string.read(reader))
    if present == 0:
        return SelectAdvancementTab(id=None)
    raise ValueOutOfRange("select_advancement_tab.id.present", present)


def encode(packet: SelectAdvancementTab, writer: Writer) -> None:
    if packet.id is None:
        writer.write(b"\x00")
    else:
        writer.write(b"\x01")
        string.write(packet.id, writer)
