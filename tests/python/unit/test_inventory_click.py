"""Click-helper builder tests (T026)."""

from __future__ import annotations

import pytest
from minecraft_bot import inventory_click as click
from minecraft_bot.protocol.v763.packets.play.serverbound.window_click import (
    WindowClick,
)


def test_left_click_mode_button() -> None:
    p = click.left_click(window_id=1, state_id=0, slot_index=10)
    assert isinstance(p, WindowClick)
    assert p.mode == 0 and p.mouse_button == 0
    assert p.slot_index == 10


def test_right_click_mode_button() -> None:
    p = click.right_click(window_id=1, state_id=0, slot_index=10)
    assert p.mode == 0 and p.mouse_button == 1


def test_shift_click_mode_button() -> None:
    p = click.shift_click(window_id=1, state_id=0, slot_index=10)
    assert p.mode == 1 and p.mouse_button == 0


def test_drop_one_vs_drop_stack() -> None:
    one = click.drop_one(window_id=1, state_id=0, slot_index=10)
    stack = click.drop_stack(window_id=1, state_id=0, slot_index=10)
    assert one.mode == 4 and one.mouse_button == 0
    assert stack.mode == 4 and stack.mouse_button == 1


def test_swap_with_hotbar_index_in_button_field() -> None:
    p = click.swap_with_hotbar(window_id=1, state_id=0, slot_index=10, hotbar_index=5)
    assert p.mode == 2 and p.mouse_button == 5


def test_swap_with_offhand_uses_button_40() -> None:
    p = click.swap_with_offhand(window_id=1, state_id=0, slot_index=10)
    assert p.mode == 2 and p.mouse_button == 40


def test_hotbar_index_validation() -> None:
    with pytest.raises(ValueError):
        click.swap_with_hotbar(window_id=1, state_id=0, slot_index=10, hotbar_index=9)


def test_double_click_mode_6() -> None:
    p = click.double_click(window_id=1, state_id=0, slot_index=10)
    assert p.mode == 6 and p.mouse_button == 0


def test_drag_lifecycle_button_codes() -> None:
    begin = click.drag_begin(window_id=1, state_id=0, button=0)
    add = click.drag_add(window_id=1, state_id=0, slot_index=10, button=1)
    end = click.drag_end(window_id=1, state_id=0, button=2)
    assert begin.mode == 5 and begin.mouse_button == 0
    assert add.mode == 5 and add.mouse_button == 1
    assert end.mode == 5 and end.mouse_button == 2
    assert begin.slot_index == -999
    assert end.slot_index == -999
