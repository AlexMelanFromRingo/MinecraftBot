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

import os
import socket
import warnings
from dataclasses import dataclass
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
