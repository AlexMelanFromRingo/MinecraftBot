"""Packet `login_plugin_response` (login/serverbound, id 0x02).

Client's reply to a clientbound :class:`LoginPluginRequest`.
``data == None`` means the client did not recognise the channel.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x02


@dataclass(frozen=True, slots=True)
class LoginPluginResponse:
    message_id: int
    data: bytes | None  # None = client did not understand the channel


def decode(reader: Reader) -> LoginPluginResponse:
    message_id = varint.read(reader)
    present = reader.read(1)[0]
    if present == 1:
        data: bytes | None = reader.read(reader.remaining())
    elif present == 0:
        data = None
    else:
        raise ValueOutOfRange("login_plugin_response.data.present", present)
    return LoginPluginResponse(message_id=message_id, data=data)


def encode(packet: LoginPluginResponse, writer: Writer) -> None:
    varint.write(packet.message_id, writer)
    if packet.data is None:
        writer.write(b"\x00")
    else:
        writer.write(b"\x01")
        writer.write(packet.data)
