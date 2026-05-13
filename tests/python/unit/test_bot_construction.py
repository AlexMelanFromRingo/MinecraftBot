"""Bot construction + offline-mode unit tests (T040, T041).

These tests construct a :class:`Bot` *without* connecting to a real
server. We verify property defaults, the offline() factory, slot
acquisition semantics, and that walk_to performs A* + drives the
intent without needing the network.
"""

from __future__ import annotations

import asyncio
import struct

import pytest
from minecraft_bot.bot import Bot
from minecraft_bot.codec import Writer, nbt, varint
from minecraft_bot.errors import NoPathFound
from minecraft_bot.events import ChatMessageEvent
from minecraft_bot.physics import PhysicsState
from minecraft_bot.protocol.v763.packets.play.clientbound.position import Position
from minecraft_bot.protocol.v763.packets.play.clientbound.update_health import UpdateHealth
from minecraft_bot.slots import BotBusy


def _make_stone_chunk_payload(cx: int, cz: int, *, sections: int = 24) -> bytes:
    """Stone floor (state 1) up through y=63; air above. min_y=-64."""
    w = Writer()
    nbt.write(nbt.NbtCompound(), w)
    sec_w = Writer()
    for sec_idx in range(sections):
        # Section y range: min_y + 16*sec_idx ... + 16*sec_idx + 15.
        sec_y_min = -64 + 16 * sec_idx
        # Stone everywhere in this section if any y in 0..63 inclusive.
        # Section 7 covers y=48..63 → fully stone.
        # Section 8 covers y=64..79 → fully air.
        if sec_y_min + 15 < 64:
            block_id = 1   # stone
        else:
            block_id = 0   # air
        sec_w.write(struct.pack(">h", 0 if block_id == 0 else 4096))
        sec_w.write(b"\x00")
        varint.write(block_id, sec_w)
        varint.write(0, sec_w)
        sec_w.write(b"\x00")
        varint.write(1, sec_w)
        varint.write(0, sec_w)
    sec_bytes = sec_w.bytes()
    varint.write(len(sec_bytes), w)
    w.write(sec_bytes)
    varint.write(0, w)
    return w.bytes()


def test_offline_factory_constructs_bot_without_connection() -> None:
    bot = Bot.offline("server", 25565, "Test")
    assert not bot.is_connected
    assert bot.health == 20.0
    assert bot.food == 20
    assert bot.entity_id is None
    assert bot.world_name is None
    assert bot.position == (0.0, 64.0, 0.5)


def test_property_dimension_and_held_default() -> None:
    bot = Bot.offline("server", 25565, "Test")
    assert bot.held_slot == 0
    assert bot.dimension is None
    assert bot.is_dead is False


def test_position_packet_updates_position_state() -> None:
    bot = Bot.offline("server", 25565, "Test")
    # Simulate absolute teleport (flags=0).
    bot._on_position(Position(
        x=100.5, y=70.0, z=-25.5, yaw=180.0, pitch=0.0,
        flags=0, teleport_id=1,
    ))
    assert bot.x == 100.5
    assert bot.y == 70.0
    assert bot.z == -25.5
    assert bot.yaw == 180.0
    # And it should emit a TeleportedEvent.
    events = bot.drain_events()
    assert any(e.__class__.__name__ == "TeleportedEvent" for e in events)


def test_update_health_packet_updates_state() -> None:
    bot = Bot.offline("server", 25565, "Test")
    bot._on_health(UpdateHealth(health=15.0, food=18, food_saturation=2.5))
    assert bot.health == 15.0
    assert bot.food == 18
    assert bot.saturation == 2.5
    assert not bot.is_dead


def test_dead_when_health_zero() -> None:
    bot = Bot.offline("server", 25565, "Test")
    bot._on_health(UpdateHealth(health=0.0, food=0, food_saturation=0.0))
    assert bot.is_dead


def test_event_hook_decorator_dispatch() -> None:
    bot = Bot.offline("server", 25565, "Test")
    received: list[ChatMessageEvent] = []

    @bot.on(ChatMessageEvent)
    def handler(evt):
        received.append(evt)

    bot._emit(ChatMessageEvent(sender=None, message="hi", chat_type="system", raw="hi"))
    assert len(received) == 1
    assert received[0].message == "hi"


def test_drain_events_returns_and_clears() -> None:
    bot = Bot.offline("server", 25565, "Test")
    bot._emit(ChatMessageEvent(sender=None, message="a", chat_type="system", raw="a"))
    bot._emit(ChatMessageEvent(sender=None, message="b", chat_type="system", raw="b"))
    events = bot.drain_events()
    assert len(events) == 2
    assert bot.drain_events() == []


def test_walk_to_no_path_raises() -> None:
    """If there's no chunk loaded at all, A* sees pure 'air' (no floor)
    so no path exists from start to a far goal."""
    bot = Bot.offline("server", 25565, "Test")
    # No world loaded — start has no floor under it; can't stand.
    # Just check the method signature works asynchronously.
    bot._physics = PhysicsState(x=0.5, y=64.0, z=0.5, on_ground=True)
    bot._has_initial_position = True

    async def go():
        with pytest.raises(NoPathFound):
            await bot.walk_to(50, 64, 50, timeout=2.0)

    asyncio.run(go())


def test_walk_to_busy_slot_raises() -> None:
    """Two concurrent walk_to calls — the second should raise BotBusy."""
    bot = Bot.offline("server", 25565, "Test")
    bot._physics = PhysicsState(x=0.5, y=64.0, z=0.5, on_ground=True)
    bot._has_initial_position = True

    async def go():
        # Hold the movement slot manually then attempt walk_to.
        await bot.movement_slot.acquire()
        try:
            with pytest.raises(BotBusy):
                await bot.walk_to(50, 64, 50, timeout=2.0)
        finally:
            bot.movement_slot.release()

    asyncio.run(go())


def test_tick_method_is_pure_advance() -> None:
    """Bot.tick should call physics_tick and update state."""
    bot = Bot.offline("server", 25565, "Test")
    bot._physics = PhysicsState(x=0.5, y=100.0, z=0.5)
    before = bot._physics
    after = bot.tick()
    # In free fall, vy should have decreased.
    assert after.vy < before.vy + 1e-9


def test_walk_to_short_distance_returns_immediately() -> None:
    """If we're already at the goal, walk_to should return without error."""
    bot = Bot.offline("server", 25565, "Test")
    bot._physics = PhysicsState(x=10.5, y=64.0, z=10.5, on_ground=True)
    bot._has_initial_position = True

    async def go():
        await bot.walk_to(10, 64, 10, timeout=2.0)

    asyncio.run(go())  # should complete without raising
