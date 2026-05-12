"""Pytest configuration for the minecraft_bot test suite.

Provides:
- ``live_server`` fixture (session-scoped) that probes the configured Paper
  test server. Tests marked ``@pytest.mark.live`` use this fixture; if the
  server is unreachable, the fixture skips with a loud warning rather than
  failing silently (per research note R-06 and Constitution V).

- Markers ``live`` and ``slow`` are registered in ``python/pyproject.toml``
  ``[tool.pytest.ini_options]``.

Environment variables:
- ``MINECRAFT_BOT_TEST_HOST`` — overrides default ``172.26.160.1``
- ``MINECRAFT_BOT_TEST_PORT`` — overrides default ``25565``
"""

from __future__ import annotations

import importlib
import os
import socket
import warnings
from dataclasses import dataclass
from types import ModuleType
from typing import Iterator

import pytest

DEFAULT_HOST = os.environ.get("MINECRAFT_BOT_TEST_HOST", "172.26.160.1")
DEFAULT_PORT = int(os.environ.get("MINECRAFT_BOT_TEST_PORT", "25565"))
PROBE_TIMEOUT = 2.0  # seconds


@dataclass(frozen=True)
class LiveServer:
    """Reachable test server endpoint."""

    host: str
    port: int


def _probe(host: str, port: int, timeout: float = PROBE_TIMEOUT) -> bool:
    """Return True if a TCP connection to ``host:port`` succeeds within ``timeout``."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


@pytest.fixture(scope="session")
def live_server() -> Iterator[LiveServer]:
    """Yield a :class:`LiveServer` if reachable, otherwise skip with a warning.

    Per R-06: skipping with a loud warning prevents the "tests are green
    but I never ran the live ones" trap.
    """
    if not _probe(DEFAULT_HOST, DEFAULT_PORT):
        warnings.warn(
            f"Live server at {DEFAULT_HOST}:{DEFAULT_PORT} is UNREACHABLE — "
            f"live-marked tests will be SKIPPED, not run. "
            f"This means Constitution V (Live-Server Integration Testing) "
            f"is NOT satisfied for this run. Bring the test server up to "
            f"validate before merging.",
            RuntimeWarning,
            stacklevel=2,
        )
        pytest.skip(
            f"Live test server {DEFAULT_HOST}:{DEFAULT_PORT} not reachable",
            allow_module_level=False,
        )
    yield LiveServer(host=DEFAULT_HOST, port=DEFAULT_PORT)


# Paper's connection throttle (server.properties: ``connection-throttle``)
# defaults to 4000 ms per IP. Live tests that connect in quick succession
# from the same machine get kicked at login with
# ``"Connection throttled! Please wait before reconnecting."``. Sleep
# before every live test to respect the window. Override via
# ``MINECRAFT_BOT_TEST_THROTTLE_DELAY``.
THROTTLE_DELAY = float(os.environ.get("MINECRAFT_BOT_TEST_THROTTLE_DELAY", "5.0"))


@pytest.fixture(autouse=True)
async def _live_throttle_guard(request: pytest.FixtureRequest):
    """Sleep before every live-marked test to avoid Paper's throttle."""
    if "live" in request.keywords:
        import asyncio
        await asyncio.sleep(THROTTLE_DELAY)
    yield


# ---------------------------------------------------------------------------
# 003 — backend fixture for parametrising tests over (python, accel) backends.
#
# Adds a ``--backend`` CLI option (python | accel). The ``backend`` fixture
# imports either ``minecraft_bot`` (the Python reference, default) or
# ``minecraft_bot_accel`` (the native PyO3 façade) and exposes it to tests.
#
# Tests that previously did ``from minecraft_bot import Bot`` should migrate
# to ``from tests.helpers.backend import Bot`` (see T010), which resolves
# the active backend from this fixture.
# ---------------------------------------------------------------------------

VALID_BACKENDS = ("python", "accel")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--backend",
        action="store",
        choices=list(VALID_BACKENDS),
        default="python",
        help="Which backend to import for tests: python (reference) or accel (PyO3).",
    )


@pytest.fixture(scope="session")
def backend_name(pytestconfig: pytest.Config) -> str:
    return str(pytestconfig.getoption("--backend"))


@pytest.fixture(scope="session")
def backend(backend_name: str) -> ModuleType:
    """Import and return the active backend module."""
    module_name = "minecraft_bot" if backend_name == "python" else "minecraft_bot_accel"
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:  # pragma: no cover — surfaces in CI
        pytest.skip(
            f"--backend={backend_name} requested but {module_name!r} is not "
            f"importable: {exc}. Build/install it first (e.g. "
            f"`maturin develop --manifest-path python-ext/Cargo.toml`).",
            allow_module_level=False,
        )
