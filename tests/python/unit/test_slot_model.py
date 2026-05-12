"""Slot model unit tests (T011)."""

from __future__ import annotations

import asyncio

import pytest

from minecraft_bot.slots import BotBusy, Slot, guard


async def test_acquire_release_basic() -> None:
    s = Slot("movement")
    assert not s.held
    await s.acquire()
    assert s.held
    s.release()
    assert not s.held


async def test_contended_raises_bot_busy() -> None:
    s = Slot("movement")
    await s.acquire()
    with pytest.raises(BotBusy):
        await s.acquire(wait_for_slot=False)
    s.release()


async def test_contended_waits_when_requested() -> None:
    s = Slot("movement")
    await s.acquire()

    waited = asyncio.Event()
    acquired_second = asyncio.Event()

    async def second() -> None:
        waited.set()
        await s.acquire(wait_for_slot=True)
        acquired_second.set()
        s.release()

    task = asyncio.create_task(second())
    await waited.wait()
    assert not acquired_second.is_set(), "second should still be waiting"
    s.release()
    await asyncio.wait_for(acquired_second.wait(), timeout=1.0)
    await task


async def test_guard_context_manager_releases_on_exit() -> None:
    s = Slot("action")
    async with guard(s):
        assert s.held
    assert not s.held


async def test_guard_releases_on_exception() -> None:
    s = Slot("action")
    with pytest.raises(RuntimeError):
        async with guard(s):
            assert s.held
            raise RuntimeError("boom")
    assert not s.held


async def test_three_slots_compose_freely() -> None:
    """Movement / action / container slots compose without blocking each other."""
    mvm = Slot("movement")
    act = Slot("action")
    ctn = Slot("container")

    await mvm.acquire()
    # Acquiring the other two while movement is held must succeed.
    await act.acquire()
    await ctn.acquire()
    assert mvm.held and act.held and ctn.held
    mvm.release(); act.release(); ctn.release()
    assert not (mvm.held or act.held or ctn.held)


def test_bot_busy_carries_slot_name() -> None:
    exc = BotBusy("movement")
    assert exc.slot_name == "movement"
    assert "movement" in str(exc)
