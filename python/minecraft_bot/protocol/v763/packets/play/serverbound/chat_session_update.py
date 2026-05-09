"""Packet `chat_session_update` (play/serverbound, id 0x06).

Client announces its public chat key. Offline-mode bots typically don't
send this; included for protocol completeness.
"""

from __future__ import annotations

import struct
import uuid as _uuid_stdlib
from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, uuid as uuid_codec, varint

PACKET_ID = 0x06


@dataclass(frozen=True, slots=True)
class ChatSessionUpdate:
    session_uuid: _uuid_stdlib.UUID
    expire_time: int        # i64
    public_key: bytes       # varint length + bytes
    signature: bytes        # varint length + bytes


def decode(reader: Reader) -> ChatSessionUpdate:
    su = uuid_codec.read(reader)
    et, = struct.unpack(">q", reader.read(8))
    pk_len = varint.read(reader)
    pk = reader.read(pk_len)
    sig_len = varint.read(reader)
    sig = reader.read(sig_len)
    return ChatSessionUpdate(session_uuid=su, expire_time=et, public_key=pk, signature=sig)


def encode(packet: ChatSessionUpdate, writer: Writer) -> None:
    uuid_codec.write(packet.session_uuid, writer)
    writer.write(struct.pack(">q", packet.expire_time))
    varint.write(len(packet.public_key), writer)
    writer.write(packet.public_key)
    varint.write(len(packet.signature), writer)
    writer.write(packet.signature)
