"""Packet `bundle_delimiter` (play/clientbound, id 0x00).

Empty packet that brackets a "bundle" of related packets so the client
applies them atomically (e.g., entity spawn + metadata + equipment).
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x00


@dataclass(frozen=True, slots=True)
class BundleDelimiter:
    """Empty packet."""


def decode(reader: Reader) -> BundleDelimiter:
    return BundleDelimiter()


def encode(packet: BundleDelimiter, writer: Writer) -> None:
    pass
