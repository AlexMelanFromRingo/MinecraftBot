"""Packet `login_plugin_request` (login/clientbound, id 0x04).

Server-side custom plugin negotiation during login. The framework's
default response is a "not understood" reply
(:class:`LoginPluginResponse` with ``data=None``) so login proceeds
without per-server tweaks. ``data`` is the raw plugin payload.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint

PACKET_ID = 0x04


@dataclass(frozen=True, slots=True)
class LoginPluginRequest:
    message_id: int
    channel: str        # identifier
    data: bytes         # restBuffer — opaque to the framework


def decode(reader: Reader) -> LoginPluginRequest:
    message_id = varint.read(reader)
    channel = string.read(reader)
    data = reader.read(reader.remaining())
    return LoginPluginRequest(message_id=message_id, channel=channel, data=data)


def encode(packet: LoginPluginRequest, writer: Writer) -> None:
    varint.write(packet.message_id, writer)
    string.write(packet.channel, writer)
    writer.write(packet.data)
