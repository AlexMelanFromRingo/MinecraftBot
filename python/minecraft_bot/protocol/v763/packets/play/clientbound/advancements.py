"""Packet `advancements` (play/clientbound, id 0x69).

Full advancement tree update. Carries definitions, removal IDs, and
progress data. Each section is itself a length-prefixed array of
complex containers.

Phase 4 captures the entire payload as opaque ``payload``. Structured
decode is a Bot API milestone task.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x69


@dataclass(frozen=True, slots=True)
class Advancements:
    payload: bytes  # opaque (reset bool + 3 typed arrays)


def decode(reader: Reader) -> Advancements:
    return Advancements(payload=reader.read(reader.remaining()))


def encode(packet: Advancements, writer: Writer) -> None:
    writer.write(packet.payload)
