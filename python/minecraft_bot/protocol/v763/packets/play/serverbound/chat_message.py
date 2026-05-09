"""Packet `chat_message` (play/serverbound, id 0x05).

Client sends a chat message. Wire format::

    string  message      (max 256 chars)
    i64     timestamp
    i64     salt
    option<256-byte buffer> signature
    varint  message_count
    bitset  acknowledged   (fixed 20-bit BitSet → 3 bytes)

Offline-mode bots send empty signatures; Paper accepts unsigned
messages when ``enforces-secure-chat=false`` (default for offline).
The framework lets the caller choose.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional

from minecraft_bot.codec import Reader, Writer, string, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x05


@dataclass(frozen=True, slots=True)
class ChatMessage:
    message: str               # max 256 chars
    timestamp: int             # i64, ms since epoch
    salt: int                  # i64
    signature: Optional[bytes] # exactly 256 bytes if present
    message_count: int         # varint
    acknowledged: bytes        # 3 bytes (20-bit fixed BitSet)


def decode(reader: Reader) -> ChatMessage:
    msg = string.read(reader, max_length=256)
    ts, salt = struct.unpack(">qq", reader.read(16))
    present = reader.read(1)[0]
    if present == 1:
        sig: Optional[bytes] = reader.read(256)
    elif present == 0:
        sig = None
    else:
        raise ValueOutOfRange("chat_message.signature.present", present)
    cnt = varint.read(reader)
    ack = reader.read(3)
    return ChatMessage(
        message=msg, timestamp=ts, salt=salt,
        signature=sig, message_count=cnt, acknowledged=ack,
    )


def encode(packet: ChatMessage, writer: Writer) -> None:
    string.write(packet.message, writer, max_length=256)
    writer.write(struct.pack(">qq", packet.timestamp, packet.salt))
    if packet.signature is None:
        writer.write(b"\x00")
    else:
        if len(packet.signature) != 256:
            raise ValueOutOfRange("chat_message.signature", len(packet.signature))
        writer.write(b"\x01")
        writer.write(packet.signature)
    varint.write(packet.message_count, writer)
    if len(packet.acknowledged) != 3:
        raise ValueOutOfRange("chat_message.acknowledged", len(packet.acknowledged))
    writer.write(packet.acknowledged)
