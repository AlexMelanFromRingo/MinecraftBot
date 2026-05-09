"""Packet `encryption_begin` (login/serverbound, id 0x01).

Client's response to a clientbound :class:`EncryptionBegin`. Used in
the online-mode handshake. Offline-mode flows never produce this; it
is implemented here for protocol completeness and for the future
``Connection.online_*`` factory.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x01


@dataclass(frozen=True, slots=True)
class EncryptionBegin:
    shared_secret: bytes
    verify_token: bytes


def decode(reader: Reader) -> EncryptionBegin:
    ss_len = varint.read(reader)
    shared_secret = reader.read(ss_len)
    vt_len = varint.read(reader)
    verify_token = reader.read(vt_len)
    return EncryptionBegin(shared_secret=shared_secret, verify_token=verify_token)


def encode(packet: EncryptionBegin, writer: Writer) -> None:
    varint.write(len(packet.shared_secret), writer)
    writer.write(packet.shared_secret)
    varint.write(len(packet.verify_token), writer)
    writer.write(packet.verify_token)
