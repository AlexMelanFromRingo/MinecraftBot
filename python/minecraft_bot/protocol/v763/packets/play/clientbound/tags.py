"""Packet `tags` (play/clientbound, id 0x6E).

Server's announcement of which registry-tag groups are defined. Each
registry (blocks, items, fluids, …) maps to a list of tag names, each
of which holds a list of registry IDs.

Wire shape::

    array<
      registry_name: string,
      tags: array<
        tag_name: string,
        ids: array<varint>
      >
    >
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer, string, varint

PACKET_ID = 0x6E


@dataclass(frozen=True, slots=True)
class Tag:
    name: str
    entries: tuple[int, ...]   # registry IDs


@dataclass(frozen=True, slots=True)
class TagGroup:
    registry: str               # e.g., "minecraft:block"
    tags: tuple[Tag, ...]


@dataclass(frozen=True, slots=True)
class Tags:
    groups: tuple[TagGroup, ...]


def decode(reader: Reader) -> Tags:
    n_groups = varint.read(reader)
    groups: list[TagGroup] = []
    for _ in range(n_groups):
        reg = string.read(reader)
        n_tags = varint.read(reader)
        tags: list[Tag] = []
        for _ in range(n_tags):
            name = string.read(reader)
            n_ids = varint.read(reader)
            ids = tuple(varint.read(reader) for _ in range(n_ids))
            tags.append(Tag(name=name, entries=ids))
        groups.append(TagGroup(registry=reg, tags=tuple(tags)))
    return Tags(groups=tuple(groups))


def encode(packet: Tags, writer: Writer) -> None:
    varint.write(len(packet.groups), writer)
    for g in packet.groups:
        string.write(g.registry, writer)
        varint.write(len(g.tags), writer)
        for t in g.tags:
            string.write(t.name, writer)
            varint.write(len(t.entries), writer)
            for tid in t.entries:
                varint.write(tid, writer)
