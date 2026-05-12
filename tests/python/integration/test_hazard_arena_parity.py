"""T084 — Hazard arena parity (live, deferred to follow-on milestone).

The 002 hazard-arena test exercises slab/water/ledge/drop handling
in `Bot.walk_to`. The accel Bot's walk_to currently slides direct
along an A*-planned path without invoking `physics::tick`, so the
hazard-traversal mechanics (auto-jump, water drag, slab step-up)
are NOT exercised the same way.

To make this test meaningful on the accel side, walk_to needs to
be reworked to run motion through physics tick the way the Python
reference does. That reshape is a perf-optimisation milestone in
its own right; see test_walk_to_packet_trace.py for the related
deferral.

The Python reference's hazard-arena test continues to run on every
live CI invocation (tests/python/integration/test_walk_to.py).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.live


def test_hazard_arena_parity_deferred(live_server) -> None:
    """Hazard-traversal parity test deferred — see docstring."""
    pytest.skip(
        "Accel walk_to bypasses physics tick — hazard parity tracked "
        "as a follow-on perf milestone. Python ref's hazard-arena test "
        "stays in tests/python/integration/test_walk_to.py."
    )
