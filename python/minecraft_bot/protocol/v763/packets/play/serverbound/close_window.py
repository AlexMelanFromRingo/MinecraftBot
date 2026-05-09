"""Packet `close_window` (play/serverbound, id 0x0C). Client closed a UI window."""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x0C


@dataclass(frozen=True, slots=True)
class CloseWindow:
    window_id: int  # u8


def decode(reader: Reader) -> CloseWindow:
    return CloseWindow(window_id=reader.read(1)[0])


def encode(packet: CloseWindow, writer: Writer) -> None:
    writer.write(bytes([packet.window_id & 0xFF]))
