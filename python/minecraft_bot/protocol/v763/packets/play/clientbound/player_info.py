"""Packet `player_info` (play/clientbound, id 0x3A).

Tab-list player updates. The payload is an action-bitfield + a list of
players, each carrying a UUID and per-action sub-fields (add: name,
properties, gamemode, latency, display name; update: subset of those;
update display: just display name; remove: nothing). Highly variable.

Phase 4 captures the entire payload as opaque ``payload`` so the
packet registers cleanly. Structured decode is a Bot API milestone
task.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x3A


@dataclass(frozen=True, slots=True)
class PlayerInfo:
    actions_mask: int   # i8 bitfield (which sub-actions are present)
    payload: bytes


def decode(reader: Reader) -> PlayerInfo:
    am, = struct.unpack(">b", reader.read(1))
    pl = reader.read(reader.remaining())
    return PlayerInfo(actions_mask=am, payload=pl)


def encode(packet: PlayerInfo, writer: Writer) -> None:
    writer.write(struct.pack(">b", packet.actions_mask))
    writer.write(packet.payload)
