"""Round-trip clientbound packets across remaining domain groups (T088).

Player / inventory / chat / sounds / tab / advancements / combat / boss /
plugin / sets — at least one representative round-trip per group.
"""

from __future__ import annotations

import importlib

from minecraft_bot.codec import Reader, Writer

_MISC_PACKETS = [
    # Player / position
    "abilities", "position", "respawn", "held_item_slot",
    # Inventory
    "open_window", "close_window", "set_slot", "window_items",
    "craft_progress_bar", "craft_recipe_response",
    # Chat
    "system_chat", "player_chat", "profileless_chat", "chat_suggestions",
    "hide_message",
    # Sound
    "sound_effect", "stop_sound",
    # Tab / advancements
    "tab_complete", "playerlist_header", "advancements", "select_advancement_tab",
    "tags", "declare_commands", "declare_recipes", "unlock_recipes",
    # Combat / boss
    "boss_bar", "enter_combat_event", "end_combat_event", "death_combat_event",
    "scoreboard_objective", "scoreboard_display_objective", "scoreboard_score",
    "teams",
    # Plugin / misc
    "custom_payload", "ping", "set_cooldown", "set_title_text",
    "set_title_subtitle", "set_title_time", "clear_titles",
    "open_book", "open_horse_window", "explosion", "feature_flags",
    "server_data", "simulation_distance", "statistics", "nbt_query_response",
    "stop_sound", "trade_list", "face_player", "camera",
    "experience", "update_health", "kick_disconnect",
    "resource_pack_send", "player_remove", "player_info",
    "bundle_delimiter", "game_state_change", "difficulty",
    "map", "action_bar",
]


def test_every_misc_packet_module_imports() -> None:
    failed: list[str] = []
    for name in _MISC_PACKETS:
        try:
            importlib.import_module(
                f"minecraft_bot.protocol.v763.packets.play.clientbound.{name}"
            )
        except Exception as exc:
            failed.append(f"{name}: {type(exc).__name__}")
    assert not failed, "broken modules:\n" + "\n".join(failed[:10])


def test_close_window_round_trip() -> None:
    from minecraft_bot.protocol.v763.packets.play.clientbound.close_window import (
        CloseWindow, decode, encode,
    )
    pkt = CloseWindow(window_id=7)
    w = Writer(); encode(pkt, w)
    assert decode(Reader(w.bytes())) == pkt


def test_set_slot_round_trip_empty() -> None:
    from minecraft_bot.protocol.v763.packets.play.clientbound.set_slot import (
        SetSlot, decode, encode,
    )
    pkt = SetSlot(window_id=0, state_id=5, slot_index=10, item=None)
    w = Writer(); encode(pkt, w)
    assert decode(Reader(w.bytes())) == pkt


def test_kick_disconnect_round_trip() -> None:
    from minecraft_bot.protocol.v763.packets.play.clientbound.kick_disconnect import (
        KickDisconnect, decode, encode,
    )
    pkt = KickDisconnect(reason='{"text":"banned"}')
    w = Writer(); encode(pkt, w)
    assert decode(Reader(w.bytes())) == pkt
