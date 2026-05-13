"""T013 — signature-shape parity.

For every shared method name, compare arity and parameter names. pyo3
descriptors often don't expose `inspect.signature`, in which case the
collector reports `(0, ())` and the check is skipped for that name.

Type annotations are NOT compared here — they're tracked through
SIGNATURE_TYPE_EQUIVALENTS in _parity_meta.py and verified by the
per-method packet-trace tests in Phase 3.
"""

from __future__ import annotations

import pytest

import minecraft_bot
import minecraft_bot_accel

from tests.python.parity._method_collector import collect_public_methods


_PARITY_COMPLETE = False


pytestmark = pytest.mark.xfail(
    not _PARITY_COMPLETE,
    reason="004 in progress — full Bot parity lands at T077.",
    strict=False,
)


def _bot_class(module) -> type:
    if hasattr(module, "Bot"):
        return module.Bot
    return module.bot.Bot


def test_signature_arity_and_names():
    py = collect_public_methods(_bot_class(minecraft_bot))
    accel = collect_public_methods(_bot_class(minecraft_bot_accel))

    shared = set(py.keys()) & set(accel.keys())
    diffs: list[str] = []
    for name in sorted(shared):
        p, a = py[name], accel[name]
        # Skip if either side did not expose a real signature.
        if p.arity == 0 and not p.param_names:
            continue
        if a.arity == 0 and not a.param_names:
            continue
        if p.arity != a.arity:
            diffs.append(
                f"  {name}: arity python={p.arity}, accel={a.arity} "
                f"(py params={p.param_names}, accel params={a.param_names})"
            )
        elif p.param_names != a.param_names:
            diffs.append(
                f"  {name}: param names differ\n"
                f"      python: {p.param_names}\n"
                f"      accel:  {a.param_names}"
            )

    assert not diffs, "Signature parity broken:\n" + "\n".join(diffs)
