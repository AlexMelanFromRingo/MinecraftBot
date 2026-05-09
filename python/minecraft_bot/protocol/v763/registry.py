"""Per-protocol-version codec registry.

Walks ``packets/{state}/{direction}/*.py``, imports each module that
declares ``PACKET_ID`` and exactly one frozen dataclass, and builds two
maps:

- ``by_id``    : ``(state, direction, packet_id) -> packet class``
- ``by_class`` : ``packet class -> (state, direction, packet_id)``

Every packet module must export:

- ``PACKET_ID: int`` — numeric ID for the (state, direction) tuple
  implied by the file's path.
- a frozen dataclass type — the packet's named-fields representation
- ``decode(reader: Reader) -> <PacketCls>`` — pure function
- ``encode(packet: <PacketCls>, writer: Writer) -> None`` — pure function

Extra modules whose name starts with ``_`` (e.g., ``_helpers.py``) are
skipped.

Per FR-022 / FR-017a, the registry is built once per protocol version
at construction time, holds no mutable state thereafter, and is safe to
share across multiple ``Connection`` instances. An optional
``protocol-data/v763/overrides.json`` file lets the live-server probe
override individual packet IDs that disagree with the upstream
minecraft-data snapshot — its format is documented in
``protocol-data/v763/README.md``.
"""

from __future__ import annotations

import importlib
import json
import logging
import pkgutil
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from types import ModuleType
from typing import Optional

from minecraft_bot.errors import UnknownPacketId
from minecraft_bot.protocol.v763.states import ConnectionState, Direction

_log = logging.getLogger("minecraft_bot.protocol.codec")

_PACKETS_PACKAGE = "minecraft_bot.protocol.v763.packets"
_REPO_ROOT = Path(__file__).resolve().parents[5]
_OVERRIDES_PATH = _REPO_ROOT / "protocol-data" / "v763" / "overrides.json"


@dataclass(frozen=True, slots=True)
class _Slot:
    """One entry in the registry: (state, direction, id) -> packet class + codec funcs."""

    state: ConnectionState
    direction: Direction
    packet_id: int
    packet_class: type
    decode_fn: object  # callable, but typed loosely to avoid circular import
    encode_fn: object


class CodecRegistry:
    """Maps ``(state, direction, packet_id)`` to packet classes for one
    :class:`~minecraft_bot.protocol.ProtocolVersion`.

    Build it once::

        registry = CodecRegistry.build()

    It walks the ``packets/`` tree at construction time, so it is
    inexpensive to keep around but slightly expensive to rebuild.
    Multiple :class:`Connection` instances share a single registry
    safely (read-only after construction).
    """

    def __init__(
        self,
        slots: tuple[_Slot, ...] = (),
    ) -> None:
        self._by_id: dict[tuple[ConnectionState, Direction, int], _Slot] = {}
        self._by_class: dict[type, _Slot] = {}
        for s in slots:
            self._add(s)

    @classmethod
    def build(cls) -> "CodecRegistry":
        """Walk the ``packets/`` tree, build the registry."""
        reg = cls()
        reg._discover()
        reg._apply_overrides()
        _log.debug(
            "v763 CodecRegistry built: %d packets",
            len(reg._by_id),
        )
        return reg

    # --- public lookup ----------------------------------------------------

    def lookup_class(
        self, state: ConnectionState, direction: Direction, packet_id: int
    ) -> type:
        """Return the packet class registered for the triple, or raise
        :class:`UnknownPacketId`."""
        slot = self._by_id.get((state, direction, packet_id))
        if slot is None:
            raise UnknownPacketId(state=state, direction=direction, id=packet_id)
        return slot.packet_class

    def lookup_id(self, packet_class: type) -> tuple[ConnectionState, Direction, int]:
        """Return ``(state, direction, id)`` for ``packet_class``."""
        slot = self._by_class.get(packet_class)
        if slot is None:
            raise KeyError(f"{packet_class.__name__} not registered")
        return (slot.state, slot.direction, slot.packet_id)

    def decoder(self, state: ConnectionState, direction: Direction, packet_id: int) -> object:
        slot = self._by_id.get((state, direction, packet_id))
        if slot is None:
            raise UnknownPacketId(state=state, direction=direction, id=packet_id)
        return slot.decode_fn

    def encoder(self, packet_class: type) -> object:
        slot = self._by_class.get(packet_class)
        if slot is None:
            raise KeyError(f"{packet_class.__name__} not registered")
        return slot.encode_fn

    def packet_count(self) -> int:
        return len(self._by_id)

    def all_packets(self) -> list[tuple[ConnectionState, Direction, int, type]]:
        return [
            (s.state, s.direction, s.packet_id, s.packet_class)
            for s in self._by_id.values()
        ]

    # --- internals --------------------------------------------------------

    def _add(self, slot: _Slot) -> None:
        key = (slot.state, slot.direction, slot.packet_id)
        if key in self._by_id:
            existing = self._by_id[key].packet_class.__name__
            raise ValueError(
                f"duplicate packet at {key}: {existing} and {slot.packet_class.__name__}"
            )
        if slot.packet_class in self._by_class:
            raise ValueError(
                f"packet class registered twice: {slot.packet_class.__name__}"
            )
        self._by_id[key] = slot
        self._by_class[slot.packet_class] = slot

    def _discover(self) -> None:
        try:
            packets_pkg = importlib.import_module(_PACKETS_PACKAGE)
        except ImportError as exc:  # pragma: no cover — package missing
            raise RuntimeError(f"packets package not importable: {exc}") from exc

        for state in ConnectionState:
            for direction in Direction:
                state_dir_name = (
                    f"{_PACKETS_PACKAGE}.{state.name.lower()}.{_dir_segment(direction)}"
                )
                try:
                    pkg = importlib.import_module(state_dir_name)
                except ModuleNotFoundError:
                    continue  # this (state, direction) combo doesn't exist yet
                self._discover_in(pkg, state, direction)

    def _discover_in(
        self, pkg: ModuleType, state: ConnectionState, direction: Direction
    ) -> None:
        if not hasattr(pkg, "__path__"):  # pragma: no cover — defensive
            return
        for finder, name, ispkg in pkgutil.iter_modules(pkg.__path__):
            if ispkg or name.startswith("_"):
                continue
            mod = importlib.import_module(f"{pkg.__name__}.{name}")
            slot = _slot_from_module(mod, state, direction)
            if slot is not None:
                self._add(slot)

    def _apply_overrides(self) -> None:
        if not _OVERRIDES_PATH.exists():
            return
        try:
            data = json.loads(_OVERRIDES_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover
            _log.warning("ignoring malformed overrides.json: %s", exc)
            return
        # data shape: {"play": {"clientbound": {"keep_alive": 0x24, ...}}, ...}
        for state_name, dirs in data.items():
            try:
                state = ConnectionState[state_name.upper()]
            except KeyError:
                _log.warning("overrides: unknown state %r", state_name)
                continue
            for dir_label, mapping in dirs.items():
                try:
                    direction = (
                        Direction.CLIENTBOUND
                        if dir_label == "clientbound"
                        else Direction.SERVERBOUND
                    )
                except KeyError:
                    _log.warning("overrides: unknown direction %r", dir_label)
                    continue
                for packet_name, new_id in mapping.items():
                    self._override(state, direction, packet_name, new_id)

    def _override(
        self,
        state: ConnectionState,
        direction: Direction,
        packet_name: str,
        new_id: int,
    ) -> None:
        # Find the slot whose packet_class.__module__ ends with packet_name
        for key, slot in list(self._by_id.items()):
            if slot.state != state or slot.direction != direction:
                continue
            module_name = slot.packet_class.__module__
            if module_name.split(".")[-1] != packet_name:
                continue
            # Re-register under new id
            del self._by_id[key]
            new_slot = _Slot(
                state=slot.state,
                direction=slot.direction,
                packet_id=new_id,
                packet_class=slot.packet_class,
                decode_fn=slot.decode_fn,
                encode_fn=slot.encode_fn,
            )
            self._by_id[(state, direction, new_id)] = new_slot
            self._by_class[slot.packet_class] = new_slot
            _log.info(
                "override: %s/%s/%s id %d -> %d",
                state.label(), _dir_segment(direction), packet_name,
                slot.packet_id, new_id,
            )
            return
        _log.warning(
            "override: no packet %s/%s/%s found to override",
            state.label(), _dir_segment(direction), packet_name,
        )


def _dir_segment(direction: Direction) -> str:
    return "clientbound" if direction == Direction.CLIENTBOUND else "serverbound"


def _slot_from_module(
    mod: ModuleType, state: ConnectionState, direction: Direction
) -> Optional[_Slot]:
    """Inspect a packet module and pull out its declared packet class.

    A module is recognised as a packet definition iff it exports
    ``PACKET_ID: int`` and exactly one frozen dataclass type. ``decode``
    and ``encode`` are looked up by name; if missing, the module is
    skipped with a warning.
    """
    pid = getattr(mod, "PACKET_ID", None)
    if not isinstance(pid, int):
        return None

    candidates = [
        v for v in vars(mod).values()
        if isinstance(v, type)
        and is_dataclass(v)
        and v.__module__ == mod.__name__
        and getattr(v, "__dataclass_params__", None) is not None
        and v.__dataclass_params__.frozen  # type: ignore[attr-defined]
    ]
    if not candidates:
        _log.warning(
            "module %s declares PACKET_ID but has no frozen dataclasses; skipping",
            mod.__name__,
        )
        return None

    if len(candidates) == 1:
        packet_class = candidates[0]
    else:
        # Multiple frozen dataclasses (e.g. helper types like ``Property``
        # alongside the main packet class): prefer the one whose name
        # matches the module's CamelCase form (``success.py`` -> ``Success``).
        module_basename = mod.__name__.rsplit(".", 1)[-1]
        expected_camel = "".join(p.capitalize() for p in module_basename.split("_"))
        match = next(
            (c for c in candidates if c.__name__ == expected_camel),
            None,
        )
        if match is None:
            _log.warning(
                "module %s has %d frozen dataclasses %s but none match the "
                "expected name %s; skipping",
                mod.__name__, len(candidates),
                [c.__name__ for c in candidates], expected_camel,
            )
            return None
        packet_class = match
    decode_fn = getattr(mod, "decode", None)
    encode_fn = getattr(mod, "encode", None)
    if decode_fn is None or encode_fn is None:
        _log.warning(
            "module %s missing decode/encode; skipping",
            mod.__name__,
        )
        return None

    # Sanity: make sure the dataclass has at least one field (else it's
    # almost certainly a placeholder, not a real packet).
    if not fields(packet_class):
        _log.debug("module %s has empty dataclass; allowed", mod.__name__)

    return _Slot(
        state=state,
        direction=direction,
        packet_id=pid,
        packet_class=packet_class,
        decode_fn=decode_fn,
        encode_fn=encode_fn,
    )


__all__ = ["CodecRegistry"]
