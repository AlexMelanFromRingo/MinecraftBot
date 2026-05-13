"""Packet `scoreboard_score` (play/clientbound, id 0x5B).

Updates a scoreboard score. ``action == 1`` (remove) omits ``value``;
otherwise ``value`` is a varint.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint

PACKET_ID = 0x5B


@dataclass(frozen=True, slots=True)
class ScoreboardScore:
    item_name: str          # entity / player name
    action: int             # varint: 0=update/create, 1=remove
    score_name: str         # objective name
    value: int | None    # varint, present when action != 1


def decode(reader: Reader) -> ScoreboardScore:
    item = string.read(reader)
    act = varint.read(reader)
    sn = string.read(reader)
    if act == 1:
        val: int | None = None
    else:
        val = varint.read(reader)
    return ScoreboardScore(item_name=item, action=act, score_name=sn, value=val)


def encode(packet: ScoreboardScore, writer: Writer) -> None:
    string.write(packet.item_name, writer)
    varint.write(packet.action, writer)
    string.write(packet.score_name, writer)
    if packet.action != 1:
        if packet.value is None:
            from minecraft_bot.errors import ValueOutOfRange
            raise ValueOutOfRange("scoreboard_score.value", packet.value)
        varint.write(packet.value, writer)
