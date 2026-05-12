"""Bot 3-slot concurrency model (FR-027).

The Bot has three concurrency "slots" that compose freely with each
other but serialise calls within each:

- **movement** — long-running ``walk_to`` / ``follow`` / ``dig`` /
  ``swim_to`` / ``fly_to``. Mutually exclusive with itself.
- **action** — instant-effect ``attack`` / ``interact_entity`` /
  ``look_at`` / ``swing_arm`` / ``use_item`` / ``say`` / single
  ``click_slot``. Serialises in-flight encode+send.
- **container** — ``open_chest`` / ``open_furnace`` /
  ``open_crafting_table`` and the clicks inside, until
  ``close_container``. Mutually exclusive with itself.

A contending caller raises :class:`BotBusy` unless invoked with
``wait_for_slot=True``, in which case it queues on the slot's lock.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from minecraft_bot.errors import ProtocolError


class BotBusy(ProtocolError):
    """Raised when a Bot slot is already held and the caller requested
    non-waiting behaviour (``wait_for_slot=False``, the default)."""

    def __init__(self, slot_name: str):
        super().__init__(f"Bot slot {slot_name!r} is busy")
        self.slot_name = slot_name


class Slot:
    """An asyncio.Lock-backed slot with friendly ``BotBusy`` semantics."""

    __slots__ = ("name", "_lock", "_owner_task")

    def __init__(self, name: str) -> None:
        self.name = name
        self._lock = asyncio.Lock()
        self._owner_task: Optional[asyncio.Task] = None

    @property
    def held(self) -> bool:
        return self._lock.locked()

    async def acquire(self, *, wait_for_slot: bool = False) -> None:
        """Acquire the slot. Raises :class:`BotBusy` if held and
        ``wait_for_slot`` is False."""
        if self._lock.locked() and not wait_for_slot:
            raise BotBusy(self.name)
        await self._lock.acquire()
        self._owner_task = asyncio.current_task()

    def release(self) -> None:
        self._owner_task = None
        self._lock.release()

    def __repr__(self) -> str:
        return f"Slot({self.name}, held={self._lock.locked()})"


class _SlotContext:
    """Async-context-manager wrapper around a Slot for use with
    ``async with bot._movement_slot.guard(wait_for_slot=True): ...``."""

    __slots__ = ("_slot", "_wait")

    def __init__(self, slot: Slot, wait: bool) -> None:
        self._slot = slot
        self._wait = wait

    async def __aenter__(self) -> Slot:
        await self._slot.acquire(wait_for_slot=self._wait)
        return self._slot

    async def __aexit__(self, *exc) -> None:
        self._slot.release()


def guard(slot: Slot, *, wait_for_slot: bool = False) -> _SlotContext:
    """Return an async context manager that acquires/releases ``slot``."""
    return _SlotContext(slot, wait_for_slot)


__all__ = ["BotBusy", "Slot", "guard"]
