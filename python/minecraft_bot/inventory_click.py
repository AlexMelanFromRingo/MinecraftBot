"""High-level helpers that build ``WindowClick`` packets correctly (T026).

The ``window_click`` serverbound packet (id 0x0B) encodes inventory
mouse-clicks. It has six ``mode`` codes × multiple ``mouse_button``
values, and getting the combinations wrong silently desyncs the
server's inventory tracking. This helper module centralises the
combinations so callers don't have to memorise the table.

Mode table (1.20.1)::

    mode  button   meaning
    0     0        left-click  (pick / place full stack)
    0     1        right-click (pick half / place one)
    1     0        shift + left-click  (auto-move stack)
    1     1        shift + right-click (auto-move stack, same effect)
    2     0..8     swap held slot with hotbar slot N
    2     40       swap held slot with off-hand
    3     2        middle-click (creative: clone stack)
    4     0        drop one of selected (if selected != None)
    4     1        drop full stack
    5     0        start left-drag
    5     1        add slot to left-drag
    5     2        end left-drag
    5     4        start right-drag  (5,5 add, 5,6 end)
    5     8        start middle-drag (5,9 add, 5,10 end)
    6     0        double-click (collect-to-cursor)

For all modes the caller must provide the cumulative
``changed_slots`` (the client's optimistic prediction of the
resulting slot contents) and the new ``carried_item`` (what the
cursor holds AFTER the click). Inventory-tracker code in higher
layers will fill these in based on the local inventory snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence

from minecraft_bot.codec import slot as slot_codec
from minecraft_bot.protocol.v763.packets.play.serverbound.window_click import (
    ChangedSlot,
    WindowClick,
)


def _build(
    *,
    window_id: int,
    state_id: int,
    slot_index: int,
    mouse_button: int,
    mode: int,
    changed_slots: Sequence[ChangedSlot] = (),
    carried_item: slot_codec.SlotData | None = None,
) -> WindowClick:
    return WindowClick(
        window_id=window_id,
        state_id=state_id,
        slot_index=slot_index,
        mouse_button=mouse_button,
        mode=mode,
        changed_slots=tuple(changed_slots),
        carried_item=carried_item,
    )


# --- single-slot clicks ---------------------------------------------------


def left_click(
    *, window_id: int, state_id: int, slot_index: int,
    changed_slots: Sequence[ChangedSlot] = (),
    carried_item: slot_codec.SlotData | None = None,
) -> WindowClick:
    """Pick up / drop the full stack at ``slot_index``."""
    return _build(
        window_id=window_id, state_id=state_id, slot_index=slot_index,
        mouse_button=0, mode=0,
        changed_slots=changed_slots, carried_item=carried_item,
    )


def right_click(
    *, window_id: int, state_id: int, slot_index: int,
    changed_slots: Sequence[ChangedSlot] = (),
    carried_item: slot_codec.SlotData | None = None,
) -> WindowClick:
    """Pick up half-stack / drop one item."""
    return _build(
        window_id=window_id, state_id=state_id, slot_index=slot_index,
        mouse_button=1, mode=0,
        changed_slots=changed_slots, carried_item=carried_item,
    )


def shift_click(
    *, window_id: int, state_id: int, slot_index: int,
    changed_slots: Sequence[ChangedSlot] = (),
) -> WindowClick:
    """Quick-move: auto-shuffle the clicked stack to the other side."""
    return _build(
        window_id=window_id, state_id=state_id, slot_index=slot_index,
        mouse_button=0, mode=1,
        changed_slots=changed_slots, carried_item=None,
    )


def middle_click(
    *, window_id: int, state_id: int, slot_index: int,
    changed_slots: Sequence[ChangedSlot] = (),
    carried_item: slot_codec.SlotData | None = None,
) -> WindowClick:
    """Creative-mode clone of the stack."""
    return _build(
        window_id=window_id, state_id=state_id, slot_index=slot_index,
        mouse_button=2, mode=3,
        changed_slots=changed_slots, carried_item=carried_item,
    )


def drop_one(
    *, window_id: int, state_id: int, slot_index: int,
    changed_slots: Sequence[ChangedSlot] = (),
) -> WindowClick:
    """Drop one item from the slot (Q key on hotbar / ctrl-Q in GUI)."""
    return _build(
        window_id=window_id, state_id=state_id, slot_index=slot_index,
        mouse_button=0, mode=4,
        changed_slots=changed_slots, carried_item=None,
    )


def drop_stack(
    *, window_id: int, state_id: int, slot_index: int,
    changed_slots: Sequence[ChangedSlot] = (),
) -> WindowClick:
    """Drop the entire stack from the slot."""
    return _build(
        window_id=window_id, state_id=state_id, slot_index=slot_index,
        mouse_button=1, mode=4,
        changed_slots=changed_slots, carried_item=None,
    )


def swap_with_hotbar(
    *, window_id: int, state_id: int, slot_index: int, hotbar_index: int,
    changed_slots: Sequence[ChangedSlot] = (),
) -> WindowClick:
    """Swap a slot's contents with one of the 9 hotbar slots
    (``hotbar_index`` 0..8). The ``button`` field carries the hotbar
    index; this is the "press 1..9 over a slot" interaction."""
    if not 0 <= hotbar_index <= 8:
        raise ValueError(f"hotbar_index must be 0..8, got {hotbar_index}")
    return _build(
        window_id=window_id, state_id=state_id, slot_index=slot_index,
        mouse_button=hotbar_index, mode=2,
        changed_slots=changed_slots, carried_item=None,
    )


def swap_with_offhand(
    *, window_id: int, state_id: int, slot_index: int,
    changed_slots: Sequence[ChangedSlot] = (),
) -> WindowClick:
    """Press F over a slot — swap with off-hand. Button code is 40."""
    return _build(
        window_id=window_id, state_id=state_id, slot_index=slot_index,
        mouse_button=40, mode=2,
        changed_slots=changed_slots, carried_item=None,
    )


def double_click(
    *, window_id: int, state_id: int, slot_index: int,
    changed_slots: Sequence[ChangedSlot] = (),
    carried_item: slot_codec.SlotData | None = None,
) -> WindowClick:
    """Double-click: collect all matching items into the cursor."""
    return _build(
        window_id=window_id, state_id=state_id, slot_index=slot_index,
        mouse_button=0, mode=6,
        changed_slots=changed_slots, carried_item=carried_item,
    )


# --- drag-distribution helpers -------------------------------------------


def drag_begin(*, window_id: int, state_id: int, button: int = 0) -> WindowClick:
    """Begin a drag. ``button``: 0=left, 4=right, 8=middle."""
    return _build(
        window_id=window_id, state_id=state_id, slot_index=-999,
        mouse_button=button, mode=5,
    )


def drag_add(
    *, window_id: int, state_id: int, slot_index: int, button: int = 1,
) -> WindowClick:
    """Add a slot to the in-progress drag. button: 1 left / 5 right / 9 middle."""
    return _build(
        window_id=window_id, state_id=state_id, slot_index=slot_index,
        mouse_button=button, mode=5,
    )


def drag_end(*, window_id: int, state_id: int, button: int = 2) -> WindowClick:
    """End the drag. button: 2 left / 6 right / 10 middle."""
    return _build(
        window_id=window_id, state_id=state_id, slot_index=-999,
        mouse_button=button, mode=5,
    )


__all__ = [
    "double_click",
    "drag_add",
    "drag_begin",
    "drag_end",
    "drop_one",
    "drop_stack",
    "left_click",
    "middle_click",
    "right_click",
    "shift_click",
    "swap_with_hotbar",
    "swap_with_offhand",
]
