"""Packet `teams` (play/clientbound, id 0x5A).

Manages scoreboard teams. ``mode`` codes:

- 0  create team (carries display name + flags + members)
- 1  remove team
- 2  update info (carries display name + flags but no members)
- 3  add players
- 4  remove players

Modes 0/2 carry a thick body of fields (display_name, flags, friendly_fire,
name_tag_visibility, collision_rule, formatting, prefix, suffix). Modes
0/3/4 also carry a list of player/entity names.

Phase 4 captures everything after the (team, mode) header as opaque
``payload``. Structured decode by mode is a Bot API milestone task.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string

PACKET_ID = 0x5A


@dataclass(frozen=True, slots=True)
class Teams:
    team: str
    mode: int       # i8 (0..4)
    payload: bytes  # opaque mode-specific bytes


def decode(reader: Reader) -> Teams:
    t = string.read(reader)
    m, = struct.unpack(">b", reader.read(1))
    pl = reader.read(reader.remaining())
    return Teams(team=t, mode=m, payload=pl)


def encode(packet: Teams, writer: Writer) -> None:
    string.write(packet.team, writer)
    writer.write(struct.pack(">b", packet.mode))
    writer.write(packet.payload)
