"""Typed Bot events (FR-101).

Every observable state-change emits an instance of one of these
frozen-dataclass event types via the Bot's hook registry. The base
:class:`Event` is just a marker; concrete subtypes are listed below.

Usage::

    @bot.on(ChatMessageEvent)
    def on_chat(event: ChatMessageEvent) -> None:
        print(event.sender, event.message)
"""

from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass
from typing import Any, Optional

# Re-export the Reconnected event from 001 so the public surface is unified.
from minecraft_bot.connection import Reconnected


class Event:
    """Marker base for all Bot events."""


@dataclass(frozen=True, slots=True)
class ChatMessageEvent(Event):
    """Incoming chat message (player, system, or profileless)."""

    sender: Optional[str]   # player display name, or None for system messages
    message: str            # human-readable message text
    chat_type: str          # "player" | "system" | "profileless"
    raw: str                # JSON chat-component / raw text as received


@dataclass(frozen=True, slots=True)
class EntityDamageEvent(Event):
    """Entity took damage."""

    entity_id: int
    damage: float
    source_entity_id: Optional[int]    # may be None for environmental damage
    source_type_id: int                # damage-type registry id


@dataclass(frozen=True, slots=True)
class EntityDeathEvent(Event):
    """Entity died."""

    entity_id: int
    death_message: Optional[str]


@dataclass(frozen=True, slots=True)
class ItemPickupEvent(Event):
    """The bot collected an item entity."""

    slot_index: int
    item_id: int
    count: int


@dataclass(frozen=True, slots=True)
class InventoryChangeEvent(Event):
    """A slot in the bot's inventory changed."""

    slot_index: int
    old_item_id: Optional[int]
    new_item_id: Optional[int]


@dataclass(frozen=True, slots=True)
class BlockBreakEvent(Event):
    """A nearby block was broken (by anyone, including this bot)."""

    x: int
    y: int
    z: int
    by_entity_id: Optional[int]


@dataclass(frozen=True, slots=True)
class ContainerOpenEvent(Event):
    """The bot opened a container UI."""

    window_id: int
    container_type: int   # registry id
    window_title: str     # JSON chat component


@dataclass(frozen=True, slots=True)
class ContainerCloseEvent(Event):
    """The bot (or server) closed the active container."""

    window_id: int


@dataclass(frozen=True, slots=True)
class TeleportedEvent(Event):
    """Server pushed a position update (anti-cheat sync or /tp)."""

    old_position: tuple[float, float, float]
    new_position: tuple[float, float, float]
    teleport_id: int


@dataclass(frozen=True, slots=True)
class InLavaEvent(Event):
    """The bot's feet just entered a lava block."""

    position: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class DimensionChangedEvent(Event):
    """Dimension change via ``respawn`` packet (e.g., Nether portal)."""

    old_dimension: Optional[str]
    new_dimension: str


@dataclass(frozen=True, slots=True)
class RespawnEvent(Event):
    """Bot respawned after death; per-session state has been reset."""

    spawn_position: tuple[float, float, float]


__all__ = [
    "Event",
    "ChatMessageEvent", "EntityDamageEvent", "EntityDeathEvent",
    "ItemPickupEvent", "InventoryChangeEvent", "BlockBreakEvent",
    "ContainerOpenEvent", "ContainerCloseEvent",
    "TeleportedEvent", "InLavaEvent", "DimensionChangedEvent",
    "RespawnEvent",
    "Reconnected",  # re-exported from 001
]
