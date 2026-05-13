"""T012 — introspection parity gate.

Compares the public method set of `minecraft_bot.Bot` against
`minecraft_bot_accel.Bot`. The symmetric difference (minus
`PYTHON_ONLY_METHODS`) must be empty. The test is intentionally
xfail until 004 Group I lands; it becomes a hard gate once all
60 methods are ported.
"""

from __future__ import annotations

import pytest

import minecraft_bot_accel
from minecraft_bot.bot import Bot as PyBot

from tests.python.parity._method_collector import (
    MethodSpec,
    collect_public_methods,
)


# Flipped to True at 004 close-out: introspection now passes
# 65 == 65 across both backends with the PYTHON_ONLY + ACCEL_ONLY
# allow-lists honoured.
_PARITY_COMPLETE = True


pytestmark = pytest.mark.xfail(
    not _PARITY_COMPLETE,
    reason="004 in progress — full Bot parity lands at T077.",
    strict=False,
)


def test_method_name_sets_match():
    """The Python and accel backends must expose the same public method
    names (excluding the PYTHON_ONLY allow-list).
    """
    py_methods = collect_public_methods(PyBot)
    accel_methods = collect_public_methods(minecraft_bot_accel.Bot)

    py_names = set(py_methods.keys())
    accel_names = set(accel_methods.keys())

    missing_on_accel = sorted(py_names - accel_names)
    extra_on_accel = sorted(accel_names - py_names)

    msg = (
        f"Bot API parity broken.\n"
        f"  Missing on minecraft_bot_accel.Bot: {missing_on_accel}\n"
        f"  Extra on minecraft_bot_accel.Bot:  {extra_on_accel}"
    )
    assert not missing_on_accel and not extra_on_accel, msg


def test_method_kinds_match():
    """Each shared name must have a compatible kind.

    pyo3-bound `#[pymethods]` show up to Python introspection as
    plain ``method`` even when they return coroutine awaitables —
    `inspect.iscoroutinefunction` returns False on the builtin
    descriptor. So the parity rule is:

    * property  <->  property            (sync getter on both sides)
    * method    <->  method/async_method (callable + awaitable shape)
    * async_method <-> method/async_method

    Property mismatches are still errors; sync/async builtin mix is OK.
    """
    py = collect_public_methods(PyBot)
    accel = collect_public_methods(minecraft_bot_accel.Bot)

    shared = set(py.keys()) & set(accel.keys())
    diffs: list[tuple[str, MethodSpec, MethodSpec]] = []
    for name in sorted(shared):
        p, a = py[name], accel[name]
        py_is_prop = p.kind == "property"
        accel_is_prop = a.kind == "property"
        if py_is_prop != accel_is_prop:
            diffs.append((name, p, a))

    msg = "\n".join(
        f"  {n}: python={p.kind!r}, accel={a.kind!r}" for n, p, a in diffs
    )
    assert not diffs, f"Method-kind property/non-property mismatch:\n{msg}"
