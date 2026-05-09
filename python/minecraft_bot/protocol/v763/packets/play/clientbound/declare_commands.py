"""Packet `declare_commands` (play/clientbound, id 0x10).

Brian Kernighan-grade complex packet — a graph of "command nodes"
describing the server's command tree (used for client-side tab
completion). Each node has its own variable wire format depending on
node type, parser, redirects, etc.

For Phase 4 we capture the **raw** node array and root index so the
packet registers cleanly and round-trips byte-for-byte. Structured
decoding is a Bot API milestone task — most bots never need it.
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, varint

PACKET_ID = 0x10


@dataclass(frozen=True, slots=True)
class DeclareCommands:
    raw_nodes: bytes  # opaque: the ``count`` varint + ``count`` node bytes
    root_index: int


def decode(reader: Reader) -> DeclareCommands:
    # Capture from the start through to the rootIndex varint at the tail.
    # We don't know node sizes without the full schema; the safe move is
    # to read everything except the trailing rootIndex varint. Since the
    # framer gives us a tight slice, ``remaining()`` is exact.
    full = reader.read(reader.remaining())
    # rootIndex is the last varint. Walk back to find it.
    # A varint occupies 1..5 bytes; the last byte has its high bit clear.
    # To find the start of the trailing varint, find the longest suffix
    # of length <= 5 such that all bytes except the last have the high
    # bit set.
    idx = len(full)
    for back in range(1, 6):
        candidate_start = len(full) - back
        if candidate_start < 0:
            break
        chunk = full[candidate_start:]
        # last byte must have high bit clear
        if (chunk[-1] & 0x80) == 0 and all((b & 0x80) for b in chunk[:-1]):
            idx = candidate_start
    raw_nodes = full[:idx]
    # Decode the trailing varint from full[idx:]
    tail = full[idx:]
    val = 0
    for i, b in enumerate(tail):
        val |= (b & 0x7F) << (7 * i)
        if (b & 0x80) == 0:
            break
    if val & (1 << 31):
        val -= 1 << 32
    return DeclareCommands(raw_nodes=raw_nodes, root_index=val)


def encode(packet: DeclareCommands, writer: Writer) -> None:
    writer.write(packet.raw_nodes)
    varint.write(packet.root_index, writer)
