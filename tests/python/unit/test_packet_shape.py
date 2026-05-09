"""Lint every packet file matches the contract from
``contracts/python-api.md`` Packet shape:

- exports ``PACKET_ID: int``
- declares at least one frozen dataclass
- exports ``decode(reader: Reader) -> Packet``
- exports ``encode(packet: Packet, writer: Writer) -> None``

This catches drift in the per-packet structure across the 176 files.
"""

from __future__ import annotations

import importlib
import inspect
from dataclasses import is_dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKETS_ROOT = REPO_ROOT / "python" / "minecraft_bot" / "protocol" / "v763" / "packets"


def _packet_modules() -> list[str]:
    """Discover every packet module under v763/packets/."""
    mods: list[str] = []
    for py in PACKETS_ROOT.rglob("*.py"):
        if py.name == "__init__.py":
            continue
        # Convert filesystem path to dotted module path.
        rel = py.relative_to(REPO_ROOT / "python")
        dotted = ".".join(rel.with_suffix("").parts)
        mods.append(dotted)
    return sorted(mods)


_MODULES = _packet_modules()


@pytest.mark.parametrize("module_name", _MODULES)
def test_packet_module_shape(module_name: str) -> None:
    mod = importlib.import_module(module_name)

    # 1) PACKET_ID is a non-negative int.
    pid = getattr(mod, "PACKET_ID", None)
    assert isinstance(pid, int) and pid >= 0, (
        f"{module_name}: PACKET_ID missing or invalid (got {pid!r})"
    )

    # 2) Has at least one frozen dataclass declared in this module.
    frozen = [
        v for v in vars(mod).values()
        if isinstance(v, type) and is_dataclass(v) and v.__module__ == mod.__name__
        and getattr(v, "__dataclass_params__", None) is not None
        and v.__dataclass_params__.frozen  # type: ignore[attr-defined]
    ]
    assert frozen, f"{module_name}: no frozen dataclass declared"

    # 3) decode/encode functions exist and have the right arity.
    decode = getattr(mod, "decode", None)
    encode = getattr(mod, "encode", None)
    assert callable(decode), f"{module_name}: decode missing or not callable"
    assert callable(encode), f"{module_name}: encode missing or not callable"

    decode_params = inspect.signature(decode).parameters
    assert len(decode_params) == 1, (
        f"{module_name}: decode must take exactly one parameter (got {len(decode_params)})"
    )

    encode_params = inspect.signature(encode).parameters
    assert len(encode_params) == 2, (
        f"{module_name}: encode must take exactly two parameters (got {len(encode_params)})"
    )


def test_packet_count_matches_registry() -> None:
    """Total packet files == registry packet count."""
    from minecraft_bot.protocol.v763.registry import CodecRegistry
    reg = CodecRegistry.build()
    assert reg.packet_count() == len(_MODULES), (
        f"registry has {reg.packet_count()} packets but file system has {len(_MODULES)}"
    )
