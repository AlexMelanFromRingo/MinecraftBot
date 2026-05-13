"""US3 — Send every action a bot needs (live).

Spec acceptance scenarios:

1. Send chat message — appears in server chat (echoed back as
   ``player_chat`` / ``system_chat`` to the sender).
2. Send a movement-update — server's reported position matches.
3. Send an attack/swing action — server registers it (we assert the
   serverbound packet was framed and written without error; verifying
   the *server* received it is harder without RCON).

The Paper server at the configured address is expected to have
``enforces-secure-chat=false`` (default for offline mode).
"""

from __future__ import annotations

import asyncio
import time

import pytest
from minecraft_bot.connection import Connection
from minecraft_bot.protocol.v763.packets.play.serverbound import arm_animation as p_sb_arm
from minecraft_bot.protocol.v763.packets.play.serverbound import (
    chat_message as p_sb_chat,
)
from minecraft_bot.protocol.v763.packets.play.serverbound import (
    entity_action as p_sb_eact,
)
from minecraft_bot.protocol.v763.packets.play.serverbound import (
    held_item_slot as p_sb_hotbar,
)
from minecraft_bot.protocol.v763.packets.play.serverbound import (
    position_look as p_sb_poslook,
)
from minecraft_bot.wire_log import WireLog

pytestmark = pytest.mark.live


async def test_send_actions_round_trip(live_server) -> None:
    """Send a battery of actions and confirm the framework framed each
    one without raising. Confirms US3 write-side coverage."""
    log = WireLog.in_memory()
    bot = Connection.offline(
        host=live_server.host, port=live_server.port,
        username="ITSend1", wire_log=log,
    )
    await bot.connect()
    try:
        # Each send() must framing-succeed; FIFO lock guarantees ordering.
        await bot.send(p_sb_arm.ArmAnimation(hand=0))
        await bot.send(p_sb_hotbar.HeldItemSlot(slot_id=5))
        await bot.send(p_sb_eact.EntityAction(
            entity_id=bot.entity_id or 0, action_id=0, jump_boost=0,
        ))  # start sneak
        await bot.send(p_sb_eact.EntityAction(
            entity_id=bot.entity_id or 0, action_id=1, jump_boost=0,
        ))  # stop sneak
        # Send a position update slightly off the spawn — server should
        # echo a Position packet back if it accepted.
        await bot.send(p_sb_poslook.PositionLook(
            x=0.5, y=64.0, z=0.5, yaw=0.0, pitch=0.0, on_ground=True,
        ))
        # Brief wait for any server-pushed effects.
        await asyncio.sleep(1.0)
    finally:
        await bot.disconnect()

    tx = [e for e in log.entries() if e.direction.label() == "tx"]
    tx_names = [e.name for e in tx]
    # Must have at least: arm_animation, held_item_slot, 2x entity_action, position_look
    # plus the framework's own settings, custom_payload (brand), confirm_teleportation.
    assert "arm_animation" in tx_names, f"arm_animation missing from {tx_names}"
    assert "held_item_slot" in tx_names, f"held_item_slot missing from {tx_names}"
    assert "entity_action" in tx_names
    assert "position_look" in tx_names


async def test_send_chat_message_appears_via_wirelog(live_server) -> None:
    """Send a chat message and confirm the framework wrote a chat_message
    serverbound packet. We don't try to parse the server's echo (Paper
    may or may not echo depending on configuration); the assertion is
    on what we *sent* via WireLog."""
    log = WireLog.in_memory()
    bot = Connection.offline(
        host=live_server.host, port=live_server.port,
        username="ITSend2", wire_log=log,
    )
    await bot.connect()
    try:
        msg = f"hello-from-itsend2 {int(time.time())}"
        await bot.send(p_sb_chat.ChatMessage(
            message=msg,
            timestamp=int(time.time() * 1000),
            salt=0,
            signature=None,           # offline mode: unsigned
            message_count=0,
            acknowledged=b"\x00\x00\x00",
        ))
        await asyncio.sleep(0.5)
    finally:
        await bot.disconnect()

    tx_chats = [
        e for e in log.entries()
        if e.direction.label() == "tx" and e.name == "chat_message"
    ]
    assert len(tx_chats) == 1, f"expected 1 chat_message tx, got {len(tx_chats)}"


async def test_fifo_send_ordering(live_server) -> None:
    """FR-013a: concurrent send() calls from N coroutines arrive on the
    wire in completion order. Sends a flood of ``arm_animation`` packets
    from 5 coroutines, then asserts:

      1. Every send made it to the WireLog (no drops).
      2. The bot is **still connected** at the end (Paper didn't reject
         us for the flood).

    We use ``arm_animation`` instead of ``keep_alive`` because Paper's
    anti-cheat treats unsolicited serverbound keep_alive packets as
    abuse and immediately kicks the bot (observed during earlier runs
    in the 2026-05-09 server log: "ITFifo1 lost connection: Timed out"
    within one second of joining). ``arm_animation`` is a swing-arm
    event the client can send freely at any time.
    """
    log = WireLog.in_memory()
    bot = Connection.offline(
        host=live_server.host, port=live_server.port,
        username="ITFifo1", wire_log=log,
    )
    from minecraft_bot.protocol.v763.packets.play.serverbound import (
        arm_animation as p_sb_arm,
    )

    await bot.connect()
    try:
        n_per_task = 10
        n_tasks = 5

        async def producer(task_idx: int) -> None:
            for _ in range(n_per_task):
                # Hand alternates 0/1 so the wire content varies; FIFO
                # ordering is verified by the framework, not by content.
                await bot.send(p_sb_arm.ArmAnimation(hand=task_idx % 2))

        await asyncio.gather(*(producer(i) for i in range(n_tasks)))
        # Brief settle window for the WireLog sink to flush.
        await asyncio.sleep(0.5)

        # The server must not have kicked us during the flood.
        assert bot.is_connected, (
            "bot lost connection during arm_animation flood — possible "
            "anti-cheat trip; check server log for 'Timed out' / 'kicked'"
        )
    finally:
        await bot.disconnect()

    tx_arm = [
        e for e in log.entries()
        if e.direction.label() == "tx" and e.name == "arm_animation"
    ]
    assert len(tx_arm) == n_tasks * n_per_task, (
        f"expected exactly {n_tasks * n_per_task} arm_animation tx, got {len(tx_arm)}"
    )
