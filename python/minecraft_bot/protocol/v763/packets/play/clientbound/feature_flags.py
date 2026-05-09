"""Packet `feature_flags` (play/clientbound, id 0x6B).

Lists "feature flags" the server has enabled (e.g.,
``minecraft:vanilla``, ``minecraft:bundle``).
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint

PACKET_ID = 0x6B


@dataclass(frozen=True, slots=True)
class FeatureFlags:
    features: tuple[str, ...]  # identifier strings


def decode(reader: Reader) -> FeatureFlags:
    n = varint.read(reader)
    feats = tuple(string.read(reader) for _ in range(n))
    return FeatureFlags(features=feats)


def encode(packet: FeatureFlags, writer: Writer) -> None:
    varint.write(len(packet.features), writer)
    for f in packet.features:
        string.write(f, writer)
