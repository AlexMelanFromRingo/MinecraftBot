"""Round-trip serverbound action/inventory/chat/misc packets (T100)."""

from __future__ import annotations

import importlib

from minecraft_bot.codec import Reader, Writer

_MISC_PACKETS = [
    "abilities", "arm_animation", "block_dig", "block_place",
    "chat_command", "chat_message", "chat_session_update",
    "client_command", "close_window", "craft_recipe_request",
    "edit_book", "enchant_item", "entity_action", "held_item_slot",
    "keep_alive", "lock_difficulty", "message_acknowledgement",
    "name_item", "pick_item", "pong", "query_entity_nbt",
    "recipe_book", "resource_pack_receive", "set_difficulty",
    "settings", "spectate", "tab_complete", "teleport_confirm",
    "update_command_block", "update_command_block_minecart",
    "update_jigsaw_block", "update_sign", "update_structure_block",
    "use_entity", "use_item", "window_click", "custom_payload",
    "displayed_recipe", "set_creative_slot",
]


def test_every_misc_serverbound_module_imports_or_absent() -> None:
    failed: list[str] = []
    for name in _MISC_PACKETS:
        try:
            importlib.import_module(
                f"minecraft_bot.protocol.v763.packets.play.serverbound.{name}"
            )
        except (ImportError, ModuleNotFoundError):
            # Some names are mapping aliases; tolerate the absence.
            pass
        except Exception as exc:
            failed.append(f"{name}: {type(exc).__name__}: {exc}")
    assert not failed, "import errors:\n" + "\n".join(failed[:10])


def test_arm_animation_round_trip() -> None:
    from minecraft_bot.protocol.v763.packets.play.serverbound.arm_animation import (
        ArmAnimation,
        decode,
        encode,
    )
    for hand in (0, 1):
        pkt = ArmAnimation(hand=hand)
        w = Writer(); encode(pkt, w)
        assert decode(Reader(w.bytes())) == pkt


def test_keep_alive_round_trip() -> None:
    from minecraft_bot.protocol.v763.packets.play.serverbound.keep_alive import (
        KeepAlive,
        decode,
        encode,
    )
    pkt = KeepAlive(keep_alive_id=0x123456789ABCDEF0)
    w = Writer(); encode(pkt, w)
    assert decode(Reader(w.bytes())) == pkt


def test_teleport_confirm_round_trip() -> None:
    from minecraft_bot.protocol.v763.packets.play.serverbound.teleport_confirm import (
        TeleportConfirm,
        decode,
        encode,
    )
    pkt = TeleportConfirm(teleport_id=42)
    w = Writer(); encode(pkt, w)
    assert decode(Reader(w.bytes())) == pkt


def test_held_item_slot_round_trip() -> None:
    from minecraft_bot.protocol.v763.packets.play.serverbound.held_item_slot import (
        HeldItemSlot,
        decode,
        encode,
    )
    pkt = HeldItemSlot(slot_id=4)
    w = Writer(); encode(pkt, w)
    assert decode(Reader(w.bytes())) == pkt


def test_use_item_round_trip() -> None:
    from minecraft_bot.protocol.v763.packets.play.serverbound.use_item import (
        UseItem,
        decode,
        encode,
    )
    pkt = UseItem(hand=0, sequence=7)
    w = Writer(); encode(pkt, w)
    assert decode(Reader(w.bytes())) == pkt
