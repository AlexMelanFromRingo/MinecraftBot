"""Packet `game_state_change` (play/clientbound, id 0x1F).

Server-side game-state notifications: change-gamemode, win-game,
demo-message, weather, raid-event, puffer-fish, etc. ``reason`` codes
0-13; ``value`` semantics vary per reason.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x1F


@dataclass(frozen=True, slots=True)
class GameStateChange:
    reason: int   # u8
    value: float  # f32


def decode(reader: Reader) -> GameStateChange:
    reason = reader.read(1)[0]
    val, = struct.unpack(">f", reader.read(4))
    return GameStateChange(reason=reason, value=val)


def encode(packet: GameStateChange, writer: Writer) -> None:
    writer.write(bytes([packet.reason & 0xFF]))
    writer.write(struct.pack(">f", packet.value))
