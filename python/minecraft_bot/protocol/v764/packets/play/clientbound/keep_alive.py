"""Packet `keep_alive` (play/clientbound) for protocol 764.

Demonstrative override of v763's keep_alive. In a hypothetical 1.20.2
where the server packed an extra "deadline_ms" field into the keepalive
to give clients a hint about timeout deadlines, this would be the
single-file port. The exact wire format is invented for the
demonstration; the point is that adding it doesn't require touching
``protocol/v763/`` at all.

Per FR-016 (Single-File Port to a New Protocol Version): this file
demonstrates the architectural promise.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x24  # different id from v763 (0x23) — demonstrating per-version IDs


@dataclass(frozen=True, slots=True)
class KeepAlive:
    keep_alive_id: int     # i64
    deadline_ms: int       # i32; v764 demo addition


def decode(reader: Reader) -> KeepAlive:
    kid, dl = struct.unpack(">qi", reader.read(12))
    return KeepAlive(keep_alive_id=kid, deadline_ms=dl)


def encode(packet: KeepAlive, writer: Writer) -> None:
    writer.write(struct.pack(">qi", packet.keep_alive_id, packet.deadline_ms))
