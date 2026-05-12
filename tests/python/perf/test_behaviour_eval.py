"""Performance: BT tick of depth 4 < 1 ms (SC-010)."""

from __future__ import annotations

import asyncio

from minecraft_bot.behaviour.nodes import (
    Action,
    Condition,
    NodeStatus,
    Selector,
    Sequence,
)


def _build_tree():
    """10-node tree of depth 4: Selector > Sequence > Condition + Action."""

    async def noop(b, c):
        return NodeStatus.SUCCESS

    leaf = Action(noop)
    cond_true = Condition(lambda b, c: True)
    cond_false = Condition(lambda b, c: False)
    inner_seq = Sequence([cond_true, leaf, leaf])
    inner_sel = Selector([cond_false, inner_seq])
    middle = Sequence([cond_true, inner_sel])
    root = Selector([cond_false, middle])
    return root


def test_behaviour_tick_under_1ms(benchmark) -> None:
    tree = _build_tree()

    def one_tick():
        return asyncio.run(tree.tick(None, {}))

    benchmark(one_tick)
    stats = benchmark.stats.stats
    assert (
        stats.median < 0.001
    ), f"BT tick median {stats.median*1000:.3f} ms exceeds 1 ms"
