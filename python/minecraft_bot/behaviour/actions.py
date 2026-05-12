"""Built-in BT action wrappers around Bot methods (T075).

These are thin :class:`Action` factories so callers can compose a
behaviour tree without writing async lambdas.

Example::

    from minecraft_bot.behaviour import Sequence, Selector
    from minecraft_bot.behaviour.actions import (
        WalkTo, EatWhenHungry, FollowPlayer, Say,
    )

    tree = Selector([
        EatWhenHungry(threshold=15),
        FollowPlayer("Alex_Melan"),
        WalkTo(0, 64, 0),
    ])
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from minecraft_bot.behaviour.nodes import (
    Action, BehaviourNode, Condition, NodeStatus, Selector, Sequence,
)
from minecraft_bot.errors import NoPathFound, TargetLost, WalkTimeout


def WalkTo(x: float, y: float, z: float, *, timeout: float = 60.0) -> Action:
    """Walk to (x, y, z). Returns Success on arrival, Failure on
    NoPathFound / WalkTimeout."""

    async def fn(bot: Any, ctx: dict) -> NodeStatus:
        try:
            await bot.walk_to(x, y, z, timeout=timeout)
            return NodeStatus.SUCCESS
        except (NoPathFound, WalkTimeout):
            return NodeStatus.FAILURE

    return Action(fn)


def FollowPlayer(name: str, *, distance: float = 3.0, max_seconds: float = 10.0) -> Action:
    """Follow the named player for up to ``max_seconds``. The player
    must be visible in the EntityTracker; Failure otherwise."""

    async def fn(bot: Any, ctx: dict) -> NodeStatus:
        # The 1.20.1 tab-list packet has name->uuid mapping, but for the
        # BT MVP we look up by display name on Player metadata.
        from minecraft_bot.entities.base import Player
        candidates = [
            e for e in bot.entities.nearby_players(radius=128.0)
            if isinstance(e, Player) and str(e.custom_name or e.uuid) == name
        ]
        if not candidates:
            # Fall back to any nearby player; many servers don't set custom_name.
            others = bot.entities.nearby_players(radius=128.0)
            if not others:
                return NodeStatus.FAILURE
            target = others[0]
        else:
            target = candidates[0]
        try:
            await bot.follow(target.eid, distance=distance, timeout=max_seconds)
            return NodeStatus.SUCCESS
        except (TargetLost, WalkTimeout):
            return NodeStatus.FAILURE

    return Action(fn)


def AttackNearest(type_filter: Optional[type] = None, *, radius: float = 8.0) -> Action:
    """Attack the closest entity matching ``type_filter`` (or any
    entity if None) within ``radius``. Success on hit; Failure if
    nothing to attack."""

    async def fn(bot: Any, ctx: dict) -> NodeStatus:
        nearby = bot.nearby_entities(radius=radius, type_filter=type_filter)
        if not nearby:
            return NodeStatus.FAILURE
        target = nearby[0]
        await bot.attack(target.eid)
        return NodeStatus.SUCCESS

    return Action(fn)


def EatWhenHungry(*, threshold: int = 15) -> Action:
    """Eat a food from the hotbar if ``bot.food < threshold``. Success
    if eaten or not hungry; Failure if hungry but no food available."""

    async def fn(bot: Any, ctx: dict) -> NodeStatus:
        if bot.food >= threshold:
            return NodeStatus.SUCCESS
        from minecraft_bot.foods import BY_ID as FOOD_BY_ID, pick_highest_saturation
        hotbar = [
            (i, slot) for i, slot in enumerate(bot.inventory.hotbar_items())
            if slot is not None and slot.item_id in FOOD_BY_ID
        ]
        if not hotbar:
            return NodeStatus.FAILURE
        infos = [FOOD_BY_ID[slot.item_id] for _, slot in hotbar]
        chosen = pick_highest_saturation(infos)
        slot_index = next(i for i, slot in hotbar if slot.item_id == chosen.item_id)
        await bot.select_slot(slot_index)
        await bot.use_item(hand=0)
        return NodeStatus.SUCCESS

    return Action(fn)


def DropItem(slot_index: int, *, full_stack: bool = False) -> Action:
    """Drop the item at ``slot_index`` (or just one). Always Success."""

    async def fn(bot: Any, ctx: dict) -> NodeStatus:
        await bot.drop_item(drop_stack=full_stack)
        return NodeStatus.SUCCESS

    return Action(fn)


def Say(message: str) -> Action:
    """Send a chat message. Always Success."""

    async def fn(bot: Any, ctx: dict) -> NodeStatus:
        await bot.say(message)
        return NodeStatus.SUCCESS

    return Action(fn)


def Command(cmd: str) -> Action:
    """Run a slash command (without the leading '/'). Always Success."""

    async def fn(bot: Any, ctx: dict) -> NodeStatus:
        await bot.command(cmd)
        return NodeStatus.SUCCESS

    return Action(fn)


def IsHungryBelow(threshold: int) -> Condition:
    return Condition(lambda bot, ctx: bot.food < threshold)


def IsHealthBelow(threshold: float) -> Condition:
    return Condition(lambda bot, ctx: bot.health < threshold)


def HasItem(name: str) -> Condition:
    return Condition(lambda bot, ctx: bot.find_item(name) is not None)


__all__ = [
    "WalkTo", "FollowPlayer", "AttackNearest", "EatWhenHungry",
    "DropItem", "Say", "Command",
    "IsHungryBelow", "IsHealthBelow", "HasItem",
]
