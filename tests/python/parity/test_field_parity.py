"""T044 — Field-level parity between Python dataclasses and accel pyclasses.

For every concrete entity in `data-model.md` parity table that the
accel package currently exposes, introspect Python's
`__dataclass_fields__` and the accel pyclass's getter-exposed
attributes, and assert the sets match.

Surface still landing in later phases is **whitelisted** in
`DEFERRED_TYPES` — these typed structs aren't yet on accel.
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest

# Types we've shipped + the (python module, attribute) → accel attribute.
EXPOSED_PARITY: list[dict] = [
    {
        "py_module": "minecraft_bot.physics",
        "py_name": "PhysicsState",
        "accel_module": "minecraft_bot_accel.physics",
        "accel_name": "PhysicsState",
    },
    {
        "py_module": "minecraft_bot.physics",
        "py_name": "PhysicsIntent",
        "accel_module": "minecraft_bot_accel.physics",
        "accel_name": "PhysicsIntent",
    },
]

# Types not yet on the accel side; the test SKIPs for each. These get
# moved to EXPOSED_PARITY as new pyclasses land.
DEFERRED_TYPES: list[tuple[str, str]] = [
    ("minecraft_bot.observation", "Observation"),
    ("minecraft_bot.inventory.item", "ItemSlot"),
    ("minecraft_bot.entities.base", "Entity"),
    ("minecraft_bot.status_effects", "EffectEntry"),
]


def _accel_attrs(pyclass) -> set[str]:
    """Return the set of names that look like field-getters on a pyclass.

    PyO3 `#[getter]` ends up as `getset_descriptor` on the class;
    Python `@property` ends up as `property`. Accept both.
    """
    attrs: set[str] = set()
    method_types = ("builtin_function_or_method", "method_descriptor", "function")
    for name, member in inspect.getmembers(pyclass):
        if name.startswith("_"):
            continue
        if name in ("from_dict", "to_dict"):
            continue
        type_name = type(member).__name__
        if type_name in method_types:
            continue
        # property (pure-Python), getset_descriptor (PyO3 #[getter]) accepted.
        attrs.add(name)
    return attrs


@pytest.mark.parametrize("rec", EXPOSED_PARITY, ids=lambda r: r["py_name"])
def test_field_parity(rec: dict) -> None:
    py_mod = __import__(rec["py_module"], fromlist=[rec["py_name"]])
    accel_mod = __import__(rec["accel_module"], fromlist=[rec["accel_name"]])
    py_cls = getattr(py_mod, rec["py_name"])
    accel_cls = getattr(accel_mod, rec["accel_name"])

    py_fields = {f.name for f in dataclasses.fields(py_cls)}
    ac_fields = _accel_attrs(accel_cls)

    missing = py_fields - ac_fields
    extra = ac_fields - py_fields
    assert not missing, (
        f"{rec['py_name']}: accel is missing fields: {sorted(missing)}\n"
        f"  python fields: {sorted(py_fields)}\n"
        f"  accel fields:  {sorted(ac_fields)}"
    )
    # `extra` is allowed — accel may add convenience getters not on
    # the Python dataclass (e.g., `level` on EffectEntry).


@pytest.mark.parametrize(
    "py_module, py_name", DEFERRED_TYPES, ids=lambda x: x if isinstance(x, str) else ""
)
def test_deferred_types_marked_skip(py_module: str, py_name: str) -> None:
    """These dataclasses don't have an accel counterpart yet —
    move them to EXPOSED_PARITY once the corresponding PyO3 wrap
    ships. This test just records the expectation."""
    pytest.skip(
        f"{py_module}.{py_name}: accel pyclass not yet shipped "
        f"(track in tasks T047-T050; see api-surface.md)"
    )
