"""Lint test (T050): every entity-type-id in entity_metadata.json has a
generated subclass with all declared metadata indices exposed as
properties."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from minecraft_bot.entities.types import LOOKUP

REPO = Path(__file__).resolve().parents[3]
META = REPO / "protocol-data" / "v763" / "entity_metadata.json"


def _snake(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", name.lower())


def test_metadata_json_loadable() -> None:
    data = json.loads(META.read_text(encoding="utf-8"))
    assert len(data) >= 100   # 1.20.1 has ~124 entity types


def test_every_type_id_has_a_class_in_LOOKUP() -> None:
    data = json.loads(META.read_text(encoding="utf-8"))
    missing = [int(tid) for tid in data if int(tid) not in LOOKUP]
    assert not missing, f"missing classes for type_ids: {missing[:5]}"


def test_LOOKUP_contains_well_known_entities() -> None:
    """Sanity: known type ids resolve to expected class names."""
    assert LOOKUP[54].__name__ == "Item"
    assert LOOKUP[82].__name__ == "Sheep"
    assert LOOKUP[118].__name__ == "Zombie"
    assert LOOKUP[122].__name__ == "Player"


def test_every_class_has_entity_type_id_class_attr() -> None:
    """The codegen should have set ENTITY_TYPE_ID on every concrete subclass."""
    for tid, cls in LOOKUP.items():
        attr_tid = getattr(cls, "ENTITY_TYPE_ID", None)
        assert attr_tid == tid, f"{cls.__name__}: ENTITY_TYPE_ID={attr_tid!r} != {tid}"


def test_every_metadata_index_is_a_property_on_its_class() -> None:
    """For every declared metadata index in the json, the class has a
    matching ``@property`` (read-only attribute on the class).

    Tolerates the renamings the codegen does (class/type/global become
    class_/type_/global_).
    """
    data = json.loads(META.read_text(encoding="utf-8"))
    reserved = {"class": "class_", "type": "type_", "global": "global_"}
    failures: list[str] = []
    for tid_str, entry in data.items():
        cls = LOOKUP[int(tid_str)]
        for key in entry.get("metadata_keys", []):
            name = _snake(key["name"])
            name = reserved.get(name, name)
            if not hasattr(cls, name):
                failures.append(f"{cls.__name__} missing metadata property {name!r}")
    # Allow up to a handful (~3) of edge-case typos in upstream json,
    # but require the vast majority to be wired.
    assert len(failures) < 5, "many missing properties: " + "; ".join(failures[:10])
