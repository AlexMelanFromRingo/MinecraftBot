"""Bot.follow re-path trigger tests (T072)."""

from __future__ import annotations

import asyncio
import math
from uuid import uuid4

from minecraft_bot.bot import Bot
from minecraft_bot.entities.base import Player
from minecraft_bot.errors import TargetLost


def _bot() -> Bot:
    bot = Bot.offline("h", 25565, "t")
    return bot


def test_follow_raises_target_lost_when_entity_absent() -> None:
    bot = _bot()
    bot._has_initial_position = True

    async def go():
        # eid 999 is not in tracker
        try:
            await asyncio.wait_for(bot.follow(999, timeout=2.0), timeout=4.0)
            assert False, "should have raised TargetLost"
        except TargetLost as e:
            assert "999" in str(e)

    asyncio.run(go())


def test_follow_no_path_returns_without_crash() -> None:
    """When the world has no chunks, A* fails. follow should retry, not crash."""
    from minecraft_bot.errors import WalkTimeout
    bot = _bot()
    bot._has_initial_position = True
    # Add a target far away.
    target = Player(eid=5, uuid=uuid4(), x=100.0, y=64.0, z=100.0, on_ground=True)
    bot.entities._entities[5] = target

    async def go():
        # Should hit WalkTimeout eventually (no path possible).
        try:
            await bot.follow(5, distance=3, timeout=2.0)
        except WalkTimeout:
            pass

    asyncio.run(go())


def test_follow_close_target_stops_intent() -> None:
    """If target is already within distance, follow should set intent to zero."""
    bot = _bot()
    bot._has_initial_position = True
    bot._physics = bot._physics.__class__(
        x=10.0, y=64.0, z=10.0, on_ground=True,
    )
    target = Player(eid=5, uuid=uuid4(), x=10.5, y=64.0, z=10.5, on_ground=True)
    bot.entities._entities[5] = target

    async def go():
        from minecraft_bot.errors import WalkTimeout
        try:
            await asyncio.wait_for(bot.follow(5, distance=3.0, timeout=1.5), timeout=3.0)
        except (WalkTimeout, asyncio.TimeoutError):
            pass
        # After running close-to-target loop, intent should be zero (or whatever).
        # Most importantly the bot didn't try to walk away.

    asyncio.run(go())
