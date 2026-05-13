"""Packet `resource_pack_send` (play/clientbound, id 0x40).

Server requests the client to download a resource pack. ``forced``
disconnects the client if it refuses; ``prompt_message`` is the
shown-to-user explanation (JSON chat component) when prompting.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string
from minecraft_bot.errors import ValueOutOfRange

PACKET_ID = 0x40


@dataclass(frozen=True, slots=True)
class ResourcePackSend:
    url: str
    hash: str            # sha-1 hex
    forced: bool
    prompt_message: str | None  # JSON chat component, may be None


def decode(reader: Reader) -> ResourcePackSend:
    url = string.read(reader)
    h = string.read(reader)
    f = reader.read(1)[0]
    if f not in (0, 1):
        raise ValueOutOfRange("resource_pack_send.forced", f)
    p = reader.read(1)[0]
    if p == 1:
        prompt: str | None = string.read(reader)
    elif p == 0:
        prompt = None
    else:
        raise ValueOutOfRange("resource_pack_send.prompt.present", p)
    return ResourcePackSend(url=url, hash=h, forced=f == 1, prompt_message=prompt)


def encode(packet: ResourcePackSend, writer: Writer) -> None:
    string.write(packet.url, writer)
    string.write(packet.hash, writer)
    writer.write(b"\x01" if packet.forced else b"\x00")
    if packet.prompt_message is None:
        writer.write(b"\x00")
    else:
        writer.write(b"\x01")
        string.write(packet.prompt_message, writer)
