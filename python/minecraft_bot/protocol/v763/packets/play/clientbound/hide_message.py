"""Packet `hide_message` (play/clientbound, id 0x19).

Removes a previously-displayed signed chat message from the client.
``id`` is the message-id; iff ``id == 0`` a 256-byte signature follows
(used when the message is identified by signature, not registry id).
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x19


@dataclass(frozen=True, slots=True)
class HideMessage:
    id: int                  # varint
    signature: bytes | None  # exactly 256 bytes if id == 0; else None


def decode(reader: Reader) -> HideMessage:
    mid = varint.read(reader)
    if mid == 0:
        sig: bytes | None = reader.read(256)
    else:
        sig = None
    return HideMessage(id=mid, signature=sig)


def encode(packet: HideMessage, writer: Writer) -> None:
    varint.write(packet.id, writer)
    if packet.id == 0:
        if packet.signature is None or len(packet.signature) != 256:
            from minecraft_bot.errors import ValueOutOfRange
            raise ValueOutOfRange("hide_message.signature", packet.signature)
        writer.write(packet.signature)
