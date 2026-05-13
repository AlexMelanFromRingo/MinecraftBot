"""T013 — signature-shape parity.

For every shared method name, compare arity and parameter names. pyo3
descriptors often don't expose `inspect.signature`, in which case the
collector reports `(0, ())` and the check is skipped for that name.

Type annotations are NOT compared here — they're tracked through
SIGNATURE_TYPE_EQUIVALENTS in _parity_meta.py and verified by the
per-method packet-trace tests in Phase 3.
"""

from __future__ import annotations

import minecraft_bot_accel
import pytest
from minecraft_bot.bot import Bot as PyBot

from tests.python.parity._method_collector import collect_public_methods

_PARITY_COMPLETE = True


pytestmark = pytest.mark.xfail(
    not _PARITY_COMPLETE,
    reason="004 in progress — full Bot parity lands at T077.",
    strict=False,
)


def test_accel_signature_is_subset_of_python():
    """Accel arity must be <= Python's.

    Accel may accept fewer optional kwargs than Python; it must never
    require more. Param names are not asserted here — they're
    cross-tested by `test_accel_param_names_compatible` below.
    """
    py = collect_public_methods(PyBot)
    accel = collect_public_methods(minecraft_bot_accel.Bot)

    shared = set(py.keys()) & set(accel.keys())
    diffs: list[str] = []
    for name in sorted(shared):
        p, a = py[name], accel[name]
        if p.arity == 0 and not p.param_names:
            continue
        if a.arity == 0 and not a.param_names:
            continue
        if a.arity > p.arity:
            diffs.append(
                f"  {name}: accel exposes MORE params than Python "
                f"(py={p.arity}, accel={a.arity})\n"
                f"      py:    {p.param_names}\n"
                f"      accel: {a.param_names}"
            )
    assert not diffs, "Accel signatures wider than Python:\n" + "\n".join(diffs)


def test_accel_param_names_compatible():
    """Every accel parameter name must exist on the Python side.

    Accel may have fewer params; the ones it has must match Python's
    naming (or the user's keyword call breaks on import swap).
    """
    py = collect_public_methods(PyBot)
    accel = collect_public_methods(minecraft_bot_accel.Bot)

    shared = set(py.keys()) & set(accel.keys())
    diffs: list[str] = []
    for name in sorted(shared):
        p, a = py[name], accel[name]
        if not a.param_names or not p.param_names:
            continue
        unknown = set(a.param_names) - set(p.param_names)
        if unknown:
            diffs.append(
                f"  {name}: accel has params Python doesn't: {sorted(unknown)}\n"
                f"      py:    {p.param_names}\n"
                f"      accel: {a.param_names}"
            )
    assert not diffs, "Accel param names not in Python:\n" + "\n".join(diffs)
