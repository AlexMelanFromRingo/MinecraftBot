"""Behaviour-tree primitives tests (T077)."""

from __future__ import annotations

import asyncio

import pytest

from minecraft_bot.behaviour.nodes import (
    Action, AlwaysSucceed, BehaviourRunner, Condition, Inverter,
    NodeStatus, Repeat, RepeatUntilFail, Selector, Sequence, Wait,
)


# --- Condition / Action ----------------------------------------------------


def test_condition_true_returns_success() -> None:
    node = Condition(lambda b, c: True)
    assert asyncio.run(node.tick(None, {})) == NodeStatus.SUCCESS


def test_condition_false_returns_failure() -> None:
    node = Condition(lambda b, c: False)
    assert asyncio.run(node.tick(None, {})) == NodeStatus.FAILURE


def test_action_can_return_status() -> None:
    async def act(b, c):
        return NodeStatus.SUCCESS
    assert asyncio.run(Action(act).tick(None, {})) == NodeStatus.SUCCESS


def test_action_with_none_return_treated_as_success() -> None:
    async def act(b, c):
        c["ran"] = True
    ctx = {}
    assert asyncio.run(Action(act).tick(None, ctx)) == NodeStatus.SUCCESS
    assert ctx["ran"] is True


# --- Selector --------------------------------------------------------------


def test_selector_returns_success_on_first_success() -> None:
    visited = []
    def make(name, status):
        async def act(b, c):
            visited.append(name)
            return status
        return Action(act)
    sel = Selector([
        make("a", NodeStatus.FAILURE),
        make("b", NodeStatus.SUCCESS),
        make("c", NodeStatus.FAILURE),
    ])
    result = asyncio.run(sel.tick(None, {}))
    assert result == NodeStatus.SUCCESS
    assert visited == ["a", "b"]   # c never ran


def test_selector_returns_failure_if_all_fail() -> None:
    def fail(b, c):
        return False
    sel = Selector([Condition(fail), Condition(fail)])
    assert asyncio.run(sel.tick(None, {})) == NodeStatus.FAILURE


# --- Sequence --------------------------------------------------------------


def test_sequence_returns_success_when_all_succeed() -> None:
    seq = Sequence([
        Condition(lambda b, c: True),
        Condition(lambda b, c: True),
    ])
    assert asyncio.run(seq.tick(None, {})) == NodeStatus.SUCCESS


def test_sequence_short_circuits_on_failure() -> None:
    visited = []
    def make(name, ok):
        async def act(b, c):
            visited.append(name)
            return NodeStatus.SUCCESS if ok else NodeStatus.FAILURE
        return Action(act)
    seq = Sequence([
        make("a", True),
        make("b", False),
        make("c", True),
    ])
    asyncio.run(seq.tick(None, {}))
    assert visited == ["a", "b"]


# --- Decorators ------------------------------------------------------------


def test_inverter_flips_status() -> None:
    inv = Inverter(Condition(lambda b, c: True))
    assert asyncio.run(inv.tick(None, {})) == NodeStatus.FAILURE
    inv2 = Inverter(Condition(lambda b, c: False))
    assert asyncio.run(inv2.tick(None, {})) == NodeStatus.SUCCESS


def test_always_succeed_converts_failure_to_success() -> None:
    node = AlwaysSucceed(Condition(lambda b, c: False))
    assert asyncio.run(node.tick(None, {})) == NodeStatus.SUCCESS


def test_repeat_counts_n_then_succeeds() -> None:
    counter = {"n": 0}
    async def inc(b, c):
        counter["n"] += 1
        return NodeStatus.SUCCESS
    rep = Repeat(Action(inc), count=3)
    asyncio.run(_run_to_terminal(rep))
    assert counter["n"] == 3


def test_wait_returns_running_then_success() -> None:
    w = Wait(duration=0.05)
    async def go():
        s1 = await w.tick(None, {})
        assert s1 == NodeStatus.RUNNING
        await asyncio.sleep(0.08)
        s2 = await w.tick(None, {})
        assert s2 == NodeStatus.SUCCESS
    asyncio.run(go())


# --- Runner ---------------------------------------------------------------


def test_runner_ticks_until_terminal_status() -> None:
    counter = {"n": 0}
    async def acc(b, c):
        counter["n"] += 1
        return NodeStatus.SUCCESS if counter["n"] >= 3 else NodeStatus.RUNNING
    runner = BehaviourRunner(tick_dt=0.0)
    result = asyncio.run(runner.run(Action(acc), bot=None))
    assert result == NodeStatus.SUCCESS
    assert counter["n"] == 3


def test_runner_respects_max_ticks() -> None:
    async def always_running(b, c):
        return NodeStatus.RUNNING
    runner = BehaviourRunner(tick_dt=0.0)
    result = asyncio.run(runner.run(Action(always_running), bot=None, max_ticks=5))
    assert result == NodeStatus.RUNNING


# --- helpers -------------------------------------------------------------


async def _run_to_terminal(node):
    while True:
        s = await node.tick(None, {})
        if s != NodeStatus.RUNNING:
            return s
