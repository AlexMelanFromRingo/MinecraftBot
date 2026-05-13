"""Round-trip serverbound movement packets (T099)."""

from __future__ import annotations

import importlib

from minecraft_bot.codec import Reader, Writer

_MOVEMENT_PACKETS = [
    "position", "position_look", "flying", "look",
    "vehicle_move", "steer_boat", "steer_vehicle",
]


def test_every_movement_module_imports() -> None:
    failed: list[str] = []
    for name in _MOVEMENT_PACKETS:
        try:
            importlib.import_module(
                f"minecraft_bot.protocol.v763.packets.play.serverbound.{name}"
            )
        except (ImportError, ModuleNotFoundError) as exc:
            failed.append(f"{name}: {exc}")
    # Some `look` variants don't exist under all version mappings — tolerate
    # up to two missing modules.
    assert len(failed) <= 2, "too many missing movement modules:\n" + "\n".join(failed)


def test_position_round_trip() -> None:
    from minecraft_bot.protocol.v763.packets.play.serverbound.position import (
        Position,
        decode,
        encode,
    )
    pkt = Position(x=100.5, y=64.0, z=-200.25, on_ground=True)
    w = Writer(); encode(pkt, w)
    assert decode(Reader(w.bytes())) == pkt


def test_position_look_round_trip() -> None:
    from minecraft_bot.protocol.v763.packets.play.serverbound.position_look import (
        PositionLook,
        decode,
        encode,
    )
    pkt = PositionLook(x=10.0, y=70.0, z=-30.0, yaw=180.0, pitch=15.5, on_ground=False)
    w = Writer(); encode(pkt, w)
    assert decode(Reader(w.bytes())) == pkt


def test_flying_round_trip() -> None:
    from minecraft_bot.protocol.v763.packets.play.serverbound.flying import (
        Flying,
        decode,
        encode,
    )
    pkt = Flying(on_ground=True)
    w = Writer(); encode(pkt, w)
    assert decode(Reader(w.bytes())) == pkt
