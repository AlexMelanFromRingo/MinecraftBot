"""Constitution VI verification: zero runtime dependencies in the core.

Walk every ``.py`` file under ``python/minecraft_bot/``, parse it,
collect every ``import`` and ``from ... import`` statement, and assert
that every imported top-level module is either:
  - a Python stdlib module, OR
  - a submodule of ``minecraft_bot`` itself.

A violation means a third-party dependency has crept into the core.
"""

from __future__ import annotations

import ast
import sys
import sysconfig
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CORE_ROOT = REPO_ROOT / "python" / "minecraft_bot"


def _stdlib_modules() -> set[str]:
    """Return the set of stdlib top-level module names for this Python."""
    # Python 3.10+ exposes sys.stdlib_module_names directly.
    if hasattr(sys, "stdlib_module_names"):
        return set(sys.stdlib_module_names)
    # Fallback (shouldn't be needed for 3.11+).
    stdlib_dir = Path(sysconfig.get_paths()["stdlib"])
    return {
        p.stem if p.is_file() else p.name
        for p in stdlib_dir.iterdir()
        if not p.name.startswith("_")
    }


_STDLIB = _stdlib_modules()


def _imported_top_modules(source: str) -> set[str]:
    """Pull the top-level (first-segment) name out of every import."""
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                names.add(node.module.split(".")[0])
    return names


def _is_allowed(module_name: str) -> bool:
    if module_name == "minecraft_bot":
        return True
    if module_name in _STDLIB:
        return True
    return False


@pytest.mark.parametrize("py_file", sorted(p for p in CORE_ROOT.rglob("*.py")))
def test_no_third_party_imports_in_core(py_file: Path) -> None:
    """Every import in the core is stdlib or a sibling minecraft_bot module."""
    source = py_file.read_text(encoding="utf-8")
    for mod in _imported_top_modules(source):
        assert _is_allowed(mod), (
            f"non-stdlib import {mod!r} in {py_file.relative_to(REPO_ROOT)}"
        )
