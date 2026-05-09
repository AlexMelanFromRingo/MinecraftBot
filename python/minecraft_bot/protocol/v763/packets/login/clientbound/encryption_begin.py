"""Packet `encryption_begin` (login/clientbound, id 0x01).

Server requests encryption (online-mode flow). Offline-mode servers do
not send this packet. If a bot in offline mode receives it, the
framework raises :class:`~minecraft_bot.errors.LoginFailed` with a
clear "encryption requested in offline mode" message — encryption
support is deferred to a future ``Connection.online_*`` factory.

Decode and encode are implemented for protocol completeness and for
diagnostic logging.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint

PACKET_ID = 0x01


@dataclass(frozen=True, slots=True)
class EncryptionBegin:
    server_id: str
    public_key: bytes
    verify_token: bytes


def decode(reader: Reader) -> EncryptionBegin:
    server_id = string.read(reader)
    pk_len = varint.read(reader)
    public_key = reader.read(pk_len)
    vt_len = varint.read(reader)
    verify_token = reader.read(vt_len)
    return EncryptionBegin(
        server_id=server_id,
        public_key=public_key,
        verify_token=verify_token,
    )


def encode(packet: EncryptionBegin, writer: Writer) -> None:
    string.write(packet.server_id, writer)
    varint.write(len(packet.public_key), writer)
    writer.write(packet.public_key)
    varint.write(len(packet.verify_token), writer)
    writer.write(packet.verify_token)
