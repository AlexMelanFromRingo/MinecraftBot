"""Backend-aware re-exports for the parametrised test suite.

Usage::

    from tests.helpers.backend import Bot, Connection, Reader, Writer

The active backend is decided by the pytest ``--backend`` CLI option
(see ``tests/python/conftest.py``). At collection time we don't yet
know which backend the user picked, so this module performs lazy
attribute lookup: every public name is resolved on first access from
the currently-imported backend module.

This is good enough for the test suite: pytest collects test
*functions* from this file's importers, and by the time a test body
executes the backend has been picked.

When the user runs ``pytest --backend accel`` but
``minecraft_bot_accel`` is not installed, the ``backend`` fixture in
conftest skips the entire session loudly — so this module only sees
backends that successfully import.
"""

from __future__ import annotations

import importlib
import os
import sys
from types import ModuleType
from typing import Any


def _detect_backend_name() -> str:
    """Determine which backend to use, falling back to env var or python.

    Order of precedence:
    1. ``MINECRAFT_BOT_TEST_BACKEND`` env var (useful outside pytest).
    2. pytest's parsed CLI option, if pytest is currently running.
    3. Default ``"python"``.
    """
    env = os.environ.get("MINECRAFT_BOT_TEST_BACKEND")
    if env in ("python", "accel"):
        return env

    # pytest stores parsed config on sys.modules['_pytest.config'] when
    # running. Look up the active --backend option if available; if not
    # (e.g., a direct python -c invocation), fall through to default.
    try:
        import _pytest.config

        cfg = getattr(_pytest.config, "_pytest_config", None)
        if cfg is not None:
            val = cfg.getoption("--backend", default="python")
            if val in ("python", "accel"):
                return val
    except Exception:
        pass

    return "python"


_BACKEND_NAME = _detect_backend_name()
_MODULE_NAME = "minecraft_bot" if _BACKEND_NAME == "python" else "minecraft_bot_accel"


def _backend() -> ModuleType:
    if _MODULE_NAME not in sys.modules:
        importlib.import_module(_MODULE_NAME)
    return sys.modules[_MODULE_NAME]


def __getattr__(name: str) -> Any:
    mod = _backend()
    try:
        return getattr(mod, name)
    except AttributeError as exc:
        raise AttributeError(
            f"backend {_MODULE_NAME!r} does not expose {name!r}"
        ) from exc


def backend_name() -> str:
    """Return the active backend identifier (``'python'`` or ``'accel'``)."""
    return _BACKEND_NAME


def backend_module() -> ModuleType:
    """Return the imported backend module."""
    return _backend()
