"""Behaviour-tree primitives (T074).

A minimal but complete BT module:

- :class:`NodeStatus` — Success / Failure / Running.
- :class:`BehaviourNode` — abstract base; ``async tick(bot, ctx)``.
- Composite nodes: :class:`Selector`, :class:`Sequence`.
- Decorators: :class:`Inverter`, :class:`AlwaysSucceed`,
  :class:`RepeatUntilFail`, :class:`Repeat`, :class:`Wait`.
- Leaves: :class:`Condition` (sync predicate), :class:`Action`
  (async coroutine factory).
- :class:`BehaviourRunner` — drives a tree at a fixed tick rate.

The "ctx" parameter is a mutable dict, threaded through the whole
tree, that callers can use for blackboard-style sharing.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Iterable
from enum import Enum
from typing import Any


class NodeStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


# Type aliases for leaf node callables.
ConditionFn = Callable[["Any", dict], bool]
ActionFn = Callable[["Any", dict], Awaitable[NodeStatus]]


class BehaviourNode(ABC):
    """Abstract base for every BT node."""

    @abstractmethod
    async def tick(self, bot: Any, ctx: dict) -> NodeStatus: ...

    def reset(self) -> None:
        """Re-initialise any internal state (called by parent on restart)."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


# --- composite nodes -----------------------------------------------------


class Selector(BehaviourNode):
    """Run children in order, return Success on first success, Failure
    if all fail, Running if a child is still running."""

    __slots__ = ("_current", "children")

    def __init__(self, children: Iterable[BehaviourNode]) -> None:
        self.children: list[BehaviourNode] = list(children)
        self._current: int = 0

    def reset(self) -> None:
        self._current = 0
        for c in self.children:
            c.reset()

    async def tick(self, bot: Any, ctx: dict) -> NodeStatus:
        while self._current < len(self.children):
            child = self.children[self._current]
            status = await child.tick(bot, ctx)
            if status == NodeStatus.SUCCESS:
                self._current = 0   # reset for next round
                return NodeStatus.SUCCESS
            if status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
            self._current += 1   # FAILURE → try next child
        self._current = 0
        return NodeStatus.FAILURE


class Sequence(BehaviourNode):
    """Run children in order, return Failure on first failure, Success
    if all succeed, Running if a child is still running."""

    __slots__ = ("_current", "children")

    def __init__(self, children: Iterable[BehaviourNode]) -> None:
        self.children: list[BehaviourNode] = list(children)
        self._current: int = 0

    def reset(self) -> None:
        self._current = 0
        for c in self.children:
            c.reset()

    async def tick(self, bot: Any, ctx: dict) -> NodeStatus:
        while self._current < len(self.children):
            child = self.children[self._current]
            status = await child.tick(bot, ctx)
            if status == NodeStatus.FAILURE:
                self._current = 0
                return NodeStatus.FAILURE
            if status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
            self._current += 1   # SUCCESS → next child
        self._current = 0
        return NodeStatus.SUCCESS


# --- decorators ----------------------------------------------------------


class Inverter(BehaviourNode):
    """Invert Success ↔ Failure. Running passes through."""

    __slots__ = ("child",)

    def __init__(self, child: BehaviourNode) -> None:
        self.child = child

    def reset(self) -> None:
        self.child.reset()

    async def tick(self, bot: Any, ctx: dict) -> NodeStatus:
        status = await self.child.tick(bot, ctx)
        if status == NodeStatus.SUCCESS:
            return NodeStatus.FAILURE
        if status == NodeStatus.FAILURE:
            return NodeStatus.SUCCESS
        return NodeStatus.RUNNING


class AlwaysSucceed(BehaviourNode):
    """Run child; return Success regardless (unless still Running)."""

    __slots__ = ("child",)

    def __init__(self, child: BehaviourNode) -> None:
        self.child = child

    def reset(self) -> None:
        self.child.reset()

    async def tick(self, bot: Any, ctx: dict) -> NodeStatus:
        status = await self.child.tick(bot, ctx)
        if status == NodeStatus.RUNNING:
            return NodeStatus.RUNNING
        return NodeStatus.SUCCESS


class RepeatUntilFail(BehaviourNode):
    """Re-tick child while it returns Success or Running. Stops on Failure."""

    __slots__ = ("child",)

    def __init__(self, child: BehaviourNode) -> None:
        self.child = child

    def reset(self) -> None:
        self.child.reset()

    async def tick(self, bot: Any, ctx: dict) -> NodeStatus:
        status = await self.child.tick(bot, ctx)
        if status == NodeStatus.FAILURE:
            return NodeStatus.SUCCESS
        # SUCCESS or RUNNING -> keep running
        if status == NodeStatus.SUCCESS:
            self.child.reset()
        return NodeStatus.RUNNING


class Repeat(BehaviourNode):
    """Run child up to ``count`` times, succeeds when count reached."""

    __slots__ = ("_remaining", "child", "count")

    def __init__(self, child: BehaviourNode, count: int) -> None:
        self.child = child
        self.count = count
        self._remaining = count

    def reset(self) -> None:
        self._remaining = self.count
        self.child.reset()

    async def tick(self, bot: Any, ctx: dict) -> NodeStatus:
        if self._remaining == 0:
            return NodeStatus.SUCCESS
        status = await self.child.tick(bot, ctx)
        if status == NodeStatus.RUNNING:
            return NodeStatus.RUNNING
        if status == NodeStatus.SUCCESS:
            self._remaining -= 1
            self.child.reset()
            return NodeStatus.RUNNING if self._remaining > 0 else NodeStatus.SUCCESS
        return NodeStatus.FAILURE


class Wait(BehaviourNode):
    """Return Running for ``duration`` seconds, then Success once."""

    __slots__ = ("_started_at", "duration")

    def __init__(self, duration: float) -> None:
        self.duration = duration
        self._started_at: float | None = None

    def reset(self) -> None:
        self._started_at = None

    async def tick(self, bot: Any, ctx: dict) -> NodeStatus:
        if self._started_at is None:
            self._started_at = time.monotonic()
        if time.monotonic() - self._started_at >= self.duration:
            self._started_at = None
            return NodeStatus.SUCCESS
        return NodeStatus.RUNNING


# --- leaves --------------------------------------------------------------


class Condition(BehaviourNode):
    """Pure-sync predicate. Returns Success/Failure on each tick."""

    __slots__ = ("predicate",)

    def __init__(self, predicate: ConditionFn) -> None:
        self.predicate = predicate

    async def tick(self, bot: Any, ctx: dict) -> NodeStatus:
        return NodeStatus.SUCCESS if self.predicate(bot, ctx) else NodeStatus.FAILURE


class Action(BehaviourNode):
    """Async action. ``fn(bot, ctx)`` may return a NodeStatus or
    ``None`` (treated as Success when the coroutine completes)."""

    __slots__ = ("fn",)

    def __init__(self, fn: ActionFn) -> None:
        self.fn = fn

    async def tick(self, bot: Any, ctx: dict) -> NodeStatus:
        result = await self.fn(bot, ctx)
        if result is None:
            return NodeStatus.SUCCESS
        return result


# --- runner --------------------------------------------------------------


class BehaviourRunner:
    """Drive a BT at a fixed tick rate."""

    __slots__ = ("tick_dt",)

    def __init__(self, *, tick_dt: float = 0.1) -> None:
        self.tick_dt = tick_dt

    async def run(
        self,
        root: BehaviourNode,
        bot: Any,
        *,
        max_ticks: int | None = None,
        stop_when: ConditionFn | None = None,
    ) -> NodeStatus:
        """Tick the tree until it returns SUCCESS or FAILURE (or
        ``max_ticks`` reached, or ``stop_when(bot, ctx)`` returns True).
        """
        ctx: dict = {}
        last_status = NodeStatus.RUNNING
        n = 0
        while True:
            last_status = await root.tick(bot, ctx)
            if last_status != NodeStatus.RUNNING:
                return last_status
            n += 1
            if max_ticks is not None and n >= max_ticks:
                return last_status
            if stop_when is not None and stop_when(bot, ctx):
                return last_status
            await asyncio.sleep(self.tick_dt)


__all__ = [
    "Action",
    "AlwaysSucceed",
    "BehaviourNode",
    "BehaviourRunner",
    "Condition",
    "Inverter",
    "NodeStatus",
    "Repeat",
    "RepeatUntilFail",
    "Selector",
    "Sequence",
    "Wait",
]
