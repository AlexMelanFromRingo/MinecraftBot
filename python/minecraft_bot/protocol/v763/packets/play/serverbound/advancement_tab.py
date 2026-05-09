"""Packet `advancement_tab` (play/serverbound, id 0x25).

``action``: 0=open tab (carries ``tab_id``), 1=close screen (no tab_id).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from minecraft_bot.codec import Reader, Writer, string, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x25


@dataclass(frozen=True, slots=True)
class AdvancementTab:
    action: int                # varint
    tab_id: Optional[str]


def decode(reader: Reader) -> AdvancementTab:
    act = varint.read(reader)
    tab_id: Optional[str] = None
    if act == 0:
        tab_id = string.read(reader)
    return AdvancementTab(action=act, tab_id=tab_id)


def encode(packet: AdvancementTab, writer: Writer) -> None:
    varint.write(packet.action, writer)
    if packet.action == 0:
        if packet.tab_id is None:
            raise ValueOutOfRange("advancement_tab.tab_id", None)
        string.write(packet.tab_id, writer)
