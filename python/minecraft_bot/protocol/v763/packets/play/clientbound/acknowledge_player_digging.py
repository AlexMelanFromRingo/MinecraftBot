"""Packet `acknowledge_player_digging` (play/clientbound, id 0x06).

Server's ack of a serverbound dig action; ``sequence_id`` matches what
the client sent so it can correlate with its own optimistic prediction.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x06


@dataclass(frozen=True, slots=True)
class AcknowledgePlayerDigging:
    sequence_id: int  # varint


def decode(reader: Reader) -> AcknowledgePlayerDigging:
    return AcknowledgePlayerDigging(sequence_id=varint.read(reader))


def encode(packet: AcknowledgePlayerDigging, writer: Writer) -> None:
    varint.write(packet.sequence_id, writer)
