"""Unit tests for Bot inventory action API (click_slot, move_item,
equip_armor, swap_to_offhand, craft, smelt).

These tests don't hit a real server — they mock the Connection's
``send`` method and assert the packets the Bot composes.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest
from minecraft_bot.bot import Bot
from minecraft_bot.protocol.v763.packets.play.serverbound.held_item_slot import (
    HeldItemSlot,
)
from minecraft_bot.protocol.v763.packets.play.serverbound.window_click import (
    WindowClick,
)


def _bot_with_mock_conn() -> tuple[Bot, MagicMock]:
    """Build a Bot whose Connection.send is mocked so we can intercept sends."""
    bot = Bot.offline("server", 25565, "T")
    sent: list[Any] = []

    async def fake_send(packet: Any) -> None:
        sent.append(packet)

    bot._conn.send = fake_send   # type: ignore[assignment]
    return bot, sent


def test_click_slot_left_mode_emits_window_click() -> None:
    bot, sent = _bot_with_mock_conn()
    asyncio.run(bot.click_slot(5, mode="left"))
    assert len(sent) == 1
    pkt = sent[0]
    assert isinstance(pkt, WindowClick)
    assert pkt.mode == 0 and pkt.mouse_button == 0
    assert pkt.slot_index == 5


def test_click_slot_swap_hotbar_carries_index_in_button() -> None:
    bot, sent = _bot_with_mock_conn()
    asyncio.run(bot.click_slot(20, mode="swap_hotbar", button=4))
    pkt = sent[0]
    assert pkt.mode == 2 and pkt.mouse_button == 4


def test_click_slot_swap_offhand_button_40() -> None:
    bot, sent = _bot_with_mock_conn()
    asyncio.run(bot.click_slot(15, mode="swap_offhand"))
    pkt = sent[0]
    assert pkt.mode == 2 and pkt.mouse_button == 40


def test_click_slot_drop_one_vs_stack() -> None:
    bot, sent = _bot_with_mock_conn()
    asyncio.run(bot.click_slot(0, mode="drop_one"))
    asyncio.run(bot.click_slot(0, mode="drop_stack"))
    assert sent[0].mode == 4 and sent[0].mouse_button == 0
    assert sent[1].mode == 4 and sent[1].mouse_button == 1


def test_click_slot_unknown_mode_raises() -> None:
    bot, _ = _bot_with_mock_conn()
    with pytest.raises(ValueError):
        asyncio.run(bot.click_slot(0, mode="explode"))


def test_move_item_sends_two_left_clicks() -> None:
    bot, sent = _bot_with_mock_conn()
    asyncio.run(bot.move_item(9, 36))
    assert len(sent) == 2
    assert all(p.mode == 0 and p.mouse_button == 0 for p in sent)
    assert sent[0].slot_index == 9
    assert sent[1].slot_index == 36


def test_quick_move_is_shift_click() -> None:
    bot, sent = _bot_with_mock_conn()
    asyncio.run(bot.quick_move(20))
    assert sent[0].mode == 1


def test_equip_armor_routes_to_correct_slot() -> None:
    bot, sent = _bot_with_mock_conn()
    asyncio.run(bot.equip_armor("head", src_slot=9))
    # move_item sends pickup + place
    assert sent[1].slot_index == 5   # SLOT_ARMOR_HEAD


def test_equip_armor_unknown_part_raises() -> None:
    bot, _ = _bot_with_mock_conn()
    with pytest.raises(ValueError):
        asyncio.run(bot.equip_armor("hat", src_slot=9))


def test_unequip_armor_routes_to_dst() -> None:
    bot, sent = _bot_with_mock_conn()
    asyncio.run(bot.unequip_armor("feet", dst_slot=12))
    assert sent[0].slot_index == 8   # SLOT_ARMOR_FEET
    assert sent[1].slot_index == 12


def test_select_slot_sends_held_item_slot() -> None:
    bot, sent = _bot_with_mock_conn()
    asyncio.run(bot.select_slot(3))
    assert any(isinstance(p, HeldItemSlot) and p.slot_id == 3 for p in sent)
    assert bot.held_slot == 3


def test_select_slot_out_of_range_raises() -> None:
    bot, _ = _bot_with_mock_conn()
    with pytest.raises(ValueError):
        asyncio.run(bot.select_slot(9))
    with pytest.raises(ValueError):
        asyncio.run(bot.select_slot(-1))


def test_swap_to_offhand_uses_swap_offhand_mode() -> None:
    bot, sent = _bot_with_mock_conn()
    asyncio.run(bot.swap_to_offhand(15))
    assert sent[0].mode == 2 and sent[0].mouse_button == 40
