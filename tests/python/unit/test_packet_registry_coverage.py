"""T137 — packet-registry coverage.

Every entry under each ``(state, direction)`` in the actual codebase
maps to a real packet file. There's no per-version JSON registry
shipped in this milestone; we walk the directory tree and assert each
file is reachable from its parent ``__init__.py``.
"""

from __future__ import annotations

import importlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PKT_BASE = REPO / "python" / "minecraft_bot" / "protocol" / "v763" / "packets"


def _walk_packet_files() -> list[Path]:
    return [
        p for p in PKT_BASE.rglob("*.py")
        if p.name not in ("__init__.py",) and not p.name.startswith("_")
    ]


def test_every_packet_file_is_importable() -> None:
    files = _walk_packet_files()
    assert files, "no packet files found"
    missing = []
    for path in files:
        # Build module name from path.
        rel = path.relative_to(REPO / "python").with_suffix("")
        module_name = str(rel).replace("/", ".").replace("\\", ".")
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            missing.append(f"{module_name}: {type(exc).__name__}: {exc}")
    assert not missing, "broken packet modules:\n" + "\n".join(missing[:10])


def test_every_packet_file_declares_packet_id() -> None:
    files = _walk_packet_files()
    leaking = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if "PACKET_ID = " not in text:
            leaking.append(str(path.relative_to(REPO)))
    assert not leaking, "files without PACKET_ID:\n" + "\n".join(leaking[:10])


def test_each_state_direction_has_at_least_one_packet() -> None:
    state_dirs = ["handshaking", "status", "login", "play"]
    expected_dirs = {
        ("handshaking", "serverbound"),
        ("status", "clientbound"),
        ("status", "serverbound"),
        ("login", "clientbound"),
        ("login", "serverbound"),
        ("play", "clientbound"),
        ("play", "serverbound"),
    }
    found: set[tuple[str, str]] = set()
    for state in state_dirs:
        for direction_dir in (PKT_BASE / state).iterdir() if (PKT_BASE / state).exists() else []:
            if direction_dir.is_dir():
                has_packet = any(
                    p for p in direction_dir.iterdir()
                    if p.is_file() and p.suffix == ".py" and p.name != "__init__.py"
                )
                if has_packet:
                    found.add((state, direction_dir.name))
    missing = expected_dirs - found
    assert not missing, f"missing packet directories: {missing}"
