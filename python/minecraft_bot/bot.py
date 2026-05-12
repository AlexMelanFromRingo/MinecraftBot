"""High-level Bot API (T032..T039).

The :class:`Bot` composes:

- a :class:`~minecraft_bot.connection.Connection` (from 001)
- a :class:`~minecraft_bot.world.cache.World` cache
- a :class:`~minecraft_bot.physics.PhysicsState`
- three concurrency slots (movement / action / container)
- a typed-event hook registry

Lifecycle::

    async with Bot.offline("server", 25565, "Bot1") as bot:
        await bot.walk_to(100, 64, 100)

``connect()`` spawns a 20-Hz physics ticker that:

1. reads server-sourced state (after every ``synchronize_player_position``),
2. integrates one tick of physics with the current intent,
3. sends a serverbound ``position`` or ``position_look`` packet,
4. dispatches typed events for any watched state-change.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Deque, Optional, Union

from minecraft_bot.connection import Connection, Reconnected
from minecraft_bot.errors import ConnectionClosed, NoPathFound, WalkTimeout
from minecraft_bot.events import (
    ChatMessageEvent, Event, TeleportedEvent, DimensionChangedEvent, RespawnEvent,
)
from minecraft_bot.pathfinding import find_path
from minecraft_bot.physics import (
    PhysicsIntent, PhysicsState, tick as physics_tick,
)
from minecraft_bot.dig import break_seconds
from minecraft_bot.entities.base import Entity, Player
from minecraft_bot.entities.tracker import EntityTracker
from minecraft_bot.errors import DigFailed
from minecraft_bot.foods import (
    BY_ID as _FOOD_BY_ID, FoodInfo, pick_highest_saturation,
)
from minecraft_bot.inventory.item import ItemSlot, item_name as _item_name
from minecraft_bot.inventory.tracker import InventoryTracker
from minecraft_bot.status_effects import StatusEffects
from minecraft_bot.protocol.v763.packets.play.clientbound import (
    block_change as cb_block_change,
    close_window as cb_close_window,
    entity_destroy as cb_entity_destroy,
    entity_effect as cb_entity_effect,
    entity_look as cb_entity_look,
    entity_metadata as cb_entity_metadata,
    entity_move_look as cb_entity_move_look,
    entity_teleport as cb_entity_teleport,
    entity_velocity as cb_entity_velocity,
    experience as cb_experience,
    game_state_change as cb_game_state,
    held_item_slot as cb_held,
    login as cb_login,
    map_chunk as cb_map_chunk,
    multi_block_change as cb_mbc,
    named_entity_spawn as cb_named_spawn,
    open_window as cb_open_window,
    player_chat as cb_player_chat,
    position as cb_position,
    profileless_chat as cb_profileless_chat,
    rel_entity_move as cb_rel_move,
    remove_entity_effect as cb_remove_effect,
    respawn as cb_respawn,
    set_slot as cb_set_slot,
    spawn_entity as cb_spawn_entity,
    system_chat as cb_system_chat,
    unload_chunk as cb_unload,
    update_health as cb_update_health,
    window_items as cb_window_items,
)
from minecraft_bot.protocol.v763.packets.play.serverbound import (
    arm_animation as sb_arm,
    chat_command as sb_command,
    chat_message as sb_chat,
    close_window as sb_close_window,
    held_item_slot as sb_held,
    position as sb_position,
    position_look as sb_position_look,
    use_entity as sb_use_entity,
    use_item as sb_use_item,
)
from minecraft_bot.slots import BotBusy, Slot, guard
from minecraft_bot.world.cache import World

PHYSICS_TICK_DT = 0.05  # seconds = 20 Hz
WALK_TARGET_RADIUS = 1.5   # blocks; close enough to call it "arrived"

# Paper anti-cheat: by default "moved too quickly" trips at delta_squared > 100,
# i.e. 10 blocks/tick. We cap our predicted position to stay within this radius
# of the last server-confirmed position to avoid false positives when local
# physics + chunk-cache lag diverge from the server's view.
MAX_PREDICTION_RADIUS = 5.0   # blocks from server's last-known position


HandlerFn = Callable[[Event], Union[None, Awaitable[None]]]


@dataclass(slots=True)
class _HookEntry:
    event_type: type
    handler: HandlerFn


class Bot:
    """High-level bot built on top of a 001 :class:`Connection`."""

    def __init__(self, connection: Connection) -> None:
        self._conn = connection
        self.world = World()
        self.entities = EntityTracker()
        self.inventory = InventoryTracker()
        self.effects = StatusEffects()

        self._physics = PhysicsState(x=0.0, y=64.0, z=0.5)
        self._yaw = 0.0
        self._pitch = 0.0
        self._intent = PhysicsIntent()
        self._last_position_send = 0.0

        # State mirrored from clientbound packets.
        self._health: float = 20.0
        self._food: int = 20
        self._saturation: float = 5.0
        self._xp_level: int = 0
        self._xp_total: int = 0
        self._xp_bar: float = 0.0
        self._game_mode: Optional[int] = None
        self._held_slot: int = 0
        self._entity_id: Optional[int] = None
        self._world_name: Optional[str] = None
        self._dimension: Optional[str] = None
        self._spawn_position: Optional[tuple[int, int, int]] = None
        self._has_initial_position = False
        self._server_position: Optional[tuple[float, float, float]] = None
        self._auto_eat_task: Optional[asyncio.Task] = None

        # Slot locks (FR-027).
        self.movement_slot = Slot("movement")
        self.action_slot = Slot("action")
        self.container_slot = Slot("container")

        # Event hooks.
        self._hooks: list[_HookEntry] = []
        self._event_queue: Deque[Event] = deque(maxlen=4096)
        self._event_waiters: list[asyncio.Future[Event]] = []

        # Internal tasks + subscription handles.
        self._tick_task: Optional[asyncio.Task] = None
        self._subscriptions: list = []

    # --- factory / lifecycle -------------------------------------------

    @classmethod
    def offline(
        cls, host: str, port: int, username: str, **conn_kwargs: Any,
    ) -> "Bot":
        """Build a Bot around an offline-mode Connection (FR-017b)."""
        conn = Connection.offline(host, port, username, **conn_kwargs)
        return cls(conn)

    @property
    def connection(self) -> Connection:
        return self._conn

    @property
    def is_connected(self) -> bool:
        return self._conn.is_connected

    async def __aenter__(self) -> "Bot":
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        """Connect the underlying socket and start the physics ticker."""
        self._wire_subscriptions()
        await self._conn.connect()
        self._tick_task = asyncio.create_task(self._physics_loop(), name="bot-tick")
        # Wait briefly for the server to push initial position so callers
        # can immediately use bot.x/y/z (best effort; not strict).
        for _ in range(40):  # up to ~2 s
            if self._has_initial_position:
                break
            await asyncio.sleep(0.05)

    async def disconnect(self, reason: Optional[str] = None) -> None:
        eat = self._auto_eat_task
        self._auto_eat_task = None
        if eat is not None:
            eat.cancel()
            try:
                await eat
            except (asyncio.CancelledError, Exception):
                pass
        task = self._tick_task
        self._tick_task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        for sub in self._subscriptions:
            try:
                sub.cancel()
            except Exception:
                pass
        self._subscriptions.clear()
        await self._conn.disconnect(reason)

    # --- read-only properties -----------------------------------------

    @property
    def x(self) -> float: return self._physics.x
    @property
    def y(self) -> float: return self._physics.y
    @property
    def z(self) -> float: return self._physics.z
    @property
    def position(self) -> tuple[float, float, float]:
        return (self._physics.x, self._physics.y, self._physics.z)
    @property
    def yaw(self) -> float: return self._yaw
    @property
    def pitch(self) -> float: return self._pitch
    @property
    def on_ground(self) -> bool: return self._physics.on_ground
    @property
    def health(self) -> float: return self._health
    @property
    def food(self) -> int: return self._food
    @property
    def saturation(self) -> float: return self._saturation
    @property
    def is_dead(self) -> bool: return self._health <= 0
    @property
    def xp_level(self) -> int: return self._xp_level
    @property
    def xp_total(self) -> int: return self._xp_total
    @property
    def game_mode(self) -> Optional[int]: return self._game_mode
    @property
    def held_slot(self) -> int: return self._held_slot
    @property
    def entity_id(self) -> Optional[int]: return self._entity_id
    @property
    def world_name(self) -> Optional[str]: return self._world_name
    @property
    def dimension(self) -> Optional[str]: return self._dimension

    # --- subscription wiring ------------------------------------------

    def _wire_subscriptions(self) -> None:
        c = self._conn
        sub = self._subscriptions.append
        sub(c.on(cb_login.Login, self._on_login))
        sub(c.on(cb_respawn.Respawn, self._on_respawn))
        sub(c.on(cb_position.Position, self._on_position))
        sub(c.on(cb_update_health.UpdateHealth, self._on_health))
        sub(c.on(cb_experience.Experience, self._on_xp))
        sub(c.on(cb_held.HeldItemSlot, self._on_held))
        sub(c.on(cb_game_state.GameStateChange, self._on_game_state))
        sub(c.on(cb_system_chat.SystemChat, self._on_system_chat))
        sub(c.on(cb_player_chat.PlayerChat, self._on_player_chat))
        sub(c.on(cb_profileless_chat.ProfilelessChat, self._on_profileless_chat))
        sub(c.on(cb_map_chunk.MapChunk, self._on_map_chunk))
        sub(c.on(cb_block_change.BlockChange, self._on_block_change))
        sub(c.on(cb_mbc.MultiBlockChange, self._on_multi_block_change))
        sub(c.on(cb_unload.UnloadChunk, self._on_unload_chunk))
        # Entity tracker.
        sub(c.on(cb_spawn_entity.SpawnEntity, self.entities.on_spawn_entity))
        sub(c.on(cb_named_spawn.NamedEntitySpawn, self.entities.on_named_entity_spawn))
        sub(c.on(cb_entity_metadata.EntityMetadata, self.entities.on_entity_metadata))
        sub(c.on(cb_rel_move.RelEntityMove, self.entities.on_rel_entity_move))
        sub(c.on(cb_entity_move_look.EntityMoveLook, self.entities.on_entity_move_look))
        sub(c.on(cb_entity_look.EntityLook, self.entities.on_entity_look))
        sub(c.on(cb_entity_teleport.EntityTeleport, self.entities.on_entity_teleport))
        sub(c.on(cb_entity_velocity.EntityVelocity, self.entities.on_entity_velocity))
        sub(c.on(cb_entity_destroy.EntityDestroy, self.entities.on_entity_destroy))
        # Inventory tracker.
        sub(c.on(cb_window_items.WindowItems, self.inventory.on_window_items))
        sub(c.on(cb_set_slot.SetSlot, self.inventory.on_set_slot))
        sub(c.on(cb_open_window.OpenWindow, self._on_open_window))
        sub(c.on(cb_close_window.CloseWindow, self._on_close_window))
        # Status effects.
        sub(c.on(cb_entity_effect.EntityEffect, self.effects.on_entity_effect))
        sub(c.on(cb_remove_effect.RemoveEntityEffect, self.effects.on_remove_entity_effect))
        sub(c.on(Reconnected, self._on_reconnected))

    # --- packet handlers ----------------------------------------------

    def _on_login(self, p) -> None:
        self._entity_id = p.entity_id
        self.entities.bot_eid = p.entity_id
        self.effects.bot_eid = p.entity_id
        self._game_mode = p.game_mode
        self._world_name = getattr(p, "world_name", None)
        self._dimension = getattr(p, "world_type", None) or self._dimension

    def _on_respawn(self, p) -> None:
        new_dim = p.world_name
        old_dim = self._dimension
        self.world.reset(dimension=new_dim)
        self._game_mode = p.game_mode if hasattr(p, "game_mode") else self._game_mode
        self._world_name = new_dim
        self._dimension = new_dim
        self._health = 20.0
        self._food = 20
        if old_dim != new_dim:
            self._emit(DimensionChangedEvent(old_dimension=old_dim, new_dimension=new_dim))
        self._emit(RespawnEvent(spawn_position=(self._physics.x, self._physics.y, self._physics.z)))

    def _on_position(self, p) -> None:
        """Server-authoritative position sync. Flags (FR-031b):
        bit 0 X relative, bit 1 Y relative, bit 2 Z relative,
        bit 3 yaw relative, bit 4 pitch relative."""
        old_pos = (self._physics.x, self._physics.y, self._physics.z)
        flags = p.flags
        new_x = self._physics.x + p.x if (flags & 0x01) else p.x
        new_y = self._physics.y + p.y if (flags & 0x02) else p.y
        new_z = self._physics.z + p.z if (flags & 0x04) else p.z
        new_yaw = self._yaw + p.yaw if (flags & 0x08) else p.yaw
        new_pitch = self._pitch + p.pitch if (flags & 0x10) else p.pitch

        self._physics = PhysicsState(
            x=new_x, y=new_y, z=new_z,
            vx=0.0, vy=0.0, vz=0.0,
            on_ground=True,
        )
        self._yaw = new_yaw
        self._pitch = new_pitch
        self._has_initial_position = True
        self._server_position = (new_x, new_y, new_z)
        new_pos = (new_x, new_y, new_z)
        if old_pos != new_pos:
            self._emit(TeleportedEvent(
                old_position=old_pos, new_position=new_pos,
                teleport_id=p.teleport_id,
            ))

    def _on_health(self, p) -> None:
        self._health = p.health
        self._food = p.food
        self._saturation = p.food_saturation

    def _on_xp(self, p) -> None:
        self._xp_level = p.level
        self._xp_total = p.total_experience
        self._xp_bar = p.experience_bar

    def _on_held(self, p) -> None:
        self._held_slot = p.slot

    def _on_game_state(self, p) -> None:
        # Reason 3 = change game mode
        if p.reason == 3:
            self._game_mode = int(p.value)

    def _on_system_chat(self, p) -> None:
        text = p.content or ""
        self._emit(ChatMessageEvent(
            sender=None, message=text, chat_type="system", raw=text,
        ))

    def _on_player_chat(self, p) -> None:
        self._emit(ChatMessageEvent(
            sender=str(p.sender), message="", chat_type="player", raw=p.payload.hex(),
        ))

    def _on_profileless_chat(self, p) -> None:
        text = p.message or ""
        self._emit(ChatMessageEvent(
            sender=p.name if hasattr(p, "name") else None,
            message=text, chat_type="profileless", raw=text,
        ))

    def _on_map_chunk(self, p) -> None:
        try:
            self.world.apply_map_chunk(p)
        except Exception:
            pass  # broken chunk; safer to skip than to crash the bot

    def _on_block_change(self, p) -> None:
        self.world.apply_block_change(p)

    def _on_multi_block_change(self, p) -> None:
        self.world.apply_multi_block_change(p)

    def _on_unload_chunk(self, p) -> None:
        self.world.apply_unload_chunk(p)

    def _on_reconnected(self, evt: Reconnected) -> None:
        self._emit(evt)

    def _on_open_window(self, p) -> None:
        self.inventory.on_open_window(p)
        from minecraft_bot.events import ContainerOpenEvent
        self._emit(ContainerOpenEvent(
            window_id=p.window_id,
            container_type=p.inventory_type,
            window_title=p.window_title,
        ))

    def _on_close_window(self, p) -> None:
        self.inventory.on_close_window(p)
        from minecraft_bot.events import ContainerCloseEvent
        self._emit(ContainerCloseEvent(window_id=p.window_id))

    # --- physics tick loop --------------------------------------------

    async def _physics_loop(self) -> None:
        next_t = time.monotonic()
        while True:
            try:
                await asyncio.sleep(max(0.0, next_t - time.monotonic()))
                if not self.is_connected:
                    return
                self.tick()
                await self._maybe_send_position()
            except asyncio.CancelledError:
                return
            except ConnectionClosed:
                return
            except Exception:
                # Best-effort loop: don't let a stray exception kill the tick.
                pass
            next_t += PHYSICS_TICK_DT

    def tick(self) -> PhysicsState:
        """Advance one physics tick (public for offline tests, FR-133).

        Skips simulation in three cases — in each, the bot just sits at
        the server's last-known position and the server stays
        authoritative:

        (a) We haven't received an initial server position yet.
        (b) The chunk under the bot's feet isn't loaded.
        (c) Intent is zero (no movement requested) — vanilla anti-cheat
            ("moved wrongly") triggers when our predicted position
            diverges from the server's idea of where physics would put
            us. Sitting still avoids the whole class of false-positives.
        """
        if not self._has_initial_position:
            return self._physics
        cx, cz = int(self._physics.x) >> 4, int(self._physics.z) >> 4
        if (cx, cz) not in self.world.chunks:
            return self._physics
        intent = self._intent
        idle = (
            intent.dx == 0.0 and intent.dz == 0.0
            and not intent.jump and not intent.sprint
        )
        if idle:
            return self._physics
        in_water = self.world.is_water(
            int(self._physics.x), int(self._physics.y), int(self._physics.z)
        )
        new_state = physics_tick(self._physics, intent, self.world, in_water=in_water)
        self._physics = new_state
        return self._physics

    async def _maybe_send_position(self) -> None:
        """Send the bot's current position to the server, respecting the
        anti-cheat per-tick speed cap.

        Once a send succeeds we move the "last server-known position"
        marker forward — the server has accepted what we said unless it
        sends a Position packet to correct us, in which case ``_on_position``
        will reset the marker.
        """
        if not self._has_initial_position:
            return
        # Clamp the per-tick step relative to the last server-known position
        # so we never trigger Paper's "moved too quickly" (delta^2 > 100).
        if self._server_position is not None:
            sx, sy, sz = self._server_position
            dx = self._physics.x - sx
            dy = self._physics.y - sy
            dz = self._physics.z - sz
            d2 = dx * dx + dy * dy + dz * dz
            cap2 = MAX_PREDICTION_RADIUS ** 2
            if d2 > cap2:
                scale = (cap2 / d2) ** 0.5
                send_x = sx + dx * scale
                send_y = sy + dy * scale
                send_z = sz + dz * scale
            else:
                send_x = self._physics.x
                send_y = self._physics.y
                send_z = self._physics.z
        else:
            send_x = self._physics.x
            send_y = self._physics.y
            send_z = self._physics.z
        try:
            await self._conn.send(sb_position.Position(
                x=send_x, y=send_y, z=send_z,
                on_ground=self._physics.on_ground,
            ))
            # Trust the send: bring the server marker forward.
            self._server_position = (send_x, send_y, send_z)
        except ConnectionClosed:
            pass

    # --- intent helpers -----------------------------------------------

    def _set_intent(self, **kw: Any) -> None:
        # Replace intent fields, keep others.
        cur = self._intent
        merged = {
            "dx": kw.get("dx", cur.dx),
            "dz": kw.get("dz", cur.dz),
            "jump": kw.get("jump", cur.jump),
            "sprint": kw.get("sprint", cur.sprint),
            "sneak": kw.get("sneak", cur.sneak),
        }
        self._intent = PhysicsIntent(**merged)

    # --- look ----------------------------------------------------------

    async def look_at(self, x: float, y: float, z: float) -> None:
        """Rotate the bot to face the world point (x, y, z)."""
        dx = x - self._physics.x
        dy = y - (self._physics.y + 1.6)  # eye height
        dz = z - self._physics.z
        dist_xz = math.hypot(dx, dz)
        yaw = -math.degrees(math.atan2(dx, dz)) % 360.0
        pitch = -math.degrees(math.atan2(dy, dist_xz)) if dist_xz else 0.0
        self._yaw = yaw
        self._pitch = pitch
        await self._conn.send(sb_position_look.PositionLook(
            x=self._physics.x, y=self._physics.y, z=self._physics.z,
            yaw=yaw, pitch=pitch, on_ground=self._physics.on_ground,
        ))

    async def jump(self) -> None:
        """Single-tick jump (best effort)."""
        self._set_intent(jump=True)
        await asyncio.sleep(PHYSICS_TICK_DT * 1.5)
        self._set_intent(jump=False)

    def sneak(self, enabled: bool) -> None:
        self._set_intent(sneak=enabled)

    def sprint(self, enabled: bool) -> None:
        self._set_intent(sprint=enabled)

    async def swing_arm(self, hand: int = 0) -> None:
        """Action slot: animate arm swing (hand=0 main, hand=1 off)."""
        async with guard(self.action_slot):
            await self._conn.send(sb_arm.ArmAnimation(hand=hand))

    # --- attack / interact / use ---------------------------------------

    async def attack(self, eid: int) -> None:
        """Attack the entity ``eid`` (action slot). Also swings arm."""
        async with guard(self.action_slot):
            await self._conn.send(sb_use_entity.UseEntity(
                target=eid, mouse=1,
                x=None, y=None, z=None, hand=None,
                sneaking=self._intent.sneak,
            ))
            await self._conn.send(sb_arm.ArmAnimation(hand=0))

    async def interact_entity(self, eid: int, *, hand: int = 0) -> None:
        """Right-click / interact with an entity (action slot)."""
        async with guard(self.action_slot):
            await self._conn.send(sb_use_entity.UseEntity(
                target=eid, mouse=0,
                x=None, y=None, z=None, hand=hand,
                sneaking=self._intent.sneak,
            ))

    async def use_item(self, hand: int = 0) -> None:
        """Right-click with the currently-held item (action slot)."""
        async with guard(self.action_slot):
            await self._conn.send(sb_use_item.UseItem(
                hand=hand, sequence=0,
            ))

    # --- observe helpers (FR-061..FR-070) ------------------------------

    def find_blocks_nearby(
        self, name: str, *, radius: int = 32, limit: int = 16,
    ) -> list[tuple[int, int, int]]:
        """Find loaded blocks named ``name`` within ``radius`` of the
        bot's current feet position, sorted ascending by distance.
        Returns up to ``limit`` positions."""
        return self.world.find_blocks_nearby(
            name, origin=self.position, radius=radius, limit=limit,
        )

    def nearby_entities(
        self, *, radius: float = 32.0, type_filter: Optional[type] = None,
    ) -> list[Entity]:
        """Entities within ``radius`` of the bot, sorted by distance."""
        return self.entities.nearby_entities(
            self.position, radius=radius, type_filter=type_filter,
        )

    def nearby_players(self, *, radius: float = 32.0) -> list[Player]:
        return self.entities.nearby_players(self.position, radius=radius)

    def distance_to(self, eid: int) -> Optional[float]:
        return self.entities.distance_to(eid, self.position)

    # --- inventory (FR-060..FR-073) ------------------------------------

    @property
    def held_item(self) -> Optional[ItemSlot]:
        """Currently held hotbar slot item (or None if empty)."""
        from minecraft_bot.inventory.tracker import SLOT_HOTBAR_FIRST
        idx = SLOT_HOTBAR_FIRST + self._held_slot
        return self.inventory.player_slots[idx]

    def find_item(self, name: str) -> Optional[int]:
        """Slot index of the first stack matching ``name``, or None."""
        return self.inventory.find_item(name)

    def count_item(self, name: str) -> int:
        """Total count of items named ``name`` across the inventory."""
        return self.inventory.count_item(name)

    async def select_slot(self, hotbar_index: int) -> None:
        """Switch the active hotbar slot (action slot). 0..8."""
        if not 0 <= hotbar_index <= 8:
            raise ValueError(f"hotbar_index must be 0..8, got {hotbar_index}")
        async with guard(self.action_slot):
            await self._conn.send(sb_held.HeldItemSlot(slot_id=hotbar_index))
        # Optimistic update; if server disagrees it'll send set_slot to fix.
        self._held_slot = hotbar_index

    async def drop_item(self, *, drop_stack: bool = False) -> None:
        """Drop the currently-held item: one (Q key) or full stack
        (Ctrl+Q). Uses the player_action serverbound packet."""
        from minecraft_bot.protocol.v763.packets.play.serverbound import (
            block_dig as sb_block_dig,
        )
        async with guard(self.action_slot):
            # block_dig status codes 3=drop stack, 4=drop one
            status = 3 if drop_stack else 4
            await self._conn.send(sb_block_dig.BlockDig(
                status=status,
                location=(0, 0, 0),
                face=0,
                sequence=0,
            ))

    # --- click operations (FR-068..FR-070) -----------------------------

    def _next_state_id(self) -> int:
        """Return the inventory's current ``state_id`` for an outgoing
        click — the server expects us to echo our last seen state_id."""
        return self.inventory.state_id

    async def click_slot(
        self, slot_index: int, *,
        mode: str = "left",
        button: int = 0,
        window_id: Optional[int] = None,
        wait_for_slot: bool = False,
    ) -> None:
        """Send a single window-click packet.

        ``mode`` ∈ {``left``, ``right``, ``shift_left``, ``shift_right``,
        ``middle``, ``drop_one``, ``drop_stack``, ``swap_hotbar`` (button=0..8),
        ``swap_offhand``, ``double``}.

        Inventory state delta is left to the server (it will echo back
        a set_slot if our click didn't produce the expected effect).
        """
        from minecraft_bot import inventory_click as click_helpers
        wid = window_id if window_id is not None else (self.inventory.container_window_id or 0)
        sid = self._next_state_id()

        builders = {
            "left":         lambda: click_helpers.left_click(window_id=wid, state_id=sid, slot_index=slot_index),
            "right":        lambda: click_helpers.right_click(window_id=wid, state_id=sid, slot_index=slot_index),
            "shift_left":   lambda: click_helpers.shift_click(window_id=wid, state_id=sid, slot_index=slot_index),
            "shift_right":  lambda: click_helpers.shift_click(window_id=wid, state_id=sid, slot_index=slot_index),
            "middle":       lambda: click_helpers.middle_click(window_id=wid, state_id=sid, slot_index=slot_index),
            "drop_one":     lambda: click_helpers.drop_one(window_id=wid, state_id=sid, slot_index=slot_index),
            "drop_stack":   lambda: click_helpers.drop_stack(window_id=wid, state_id=sid, slot_index=slot_index),
            "swap_hotbar":  lambda: click_helpers.swap_with_hotbar(
                window_id=wid, state_id=sid, slot_index=slot_index, hotbar_index=button,
            ),
            "swap_offhand": lambda: click_helpers.swap_with_offhand(window_id=wid, state_id=sid, slot_index=slot_index),
            "double":       lambda: click_helpers.double_click(window_id=wid, state_id=sid, slot_index=slot_index),
        }
        if mode not in builders:
            raise ValueError(f"unknown click mode {mode!r}; allowed: {sorted(builders)}")
        pkt = builders[mode]()
        async with guard(self.action_slot, wait_for_slot=wait_for_slot):
            await self._conn.send(pkt)

    async def move_item(
        self, src_slot: int, dst_slot: int, *, window_id: Optional[int] = None,
    ) -> None:
        """Move the entire stack at ``src_slot`` to ``dst_slot`` via
        pick-up + put-down (two left-clicks). Works in both player
        inventory and an open container."""
        await self.click_slot(src_slot, mode="left", window_id=window_id)
        await asyncio.sleep(0.05)
        await self.click_slot(dst_slot, mode="left", window_id=window_id)

    async def quick_move(
        self, slot_index: int, *, window_id: Optional[int] = None,
    ) -> None:
        """Shift-click — auto-shuffle stack between player and container."""
        await self.click_slot(slot_index, mode="shift_left", window_id=window_id)

    async def equip_armor(self, armor_slot: str, src_slot: int) -> None:
        """Move an armor piece from ``src_slot`` to the appropriate armor
        slot. ``armor_slot`` ∈ {``head``, ``chest``, ``legs``, ``feet``}."""
        from minecraft_bot.inventory.tracker import (
            SLOT_ARMOR_HEAD, SLOT_ARMOR_CHEST, SLOT_ARMOR_LEGS, SLOT_ARMOR_FEET,
        )
        target = {
            "head": SLOT_ARMOR_HEAD, "chest": SLOT_ARMOR_CHEST,
            "legs": SLOT_ARMOR_LEGS, "feet": SLOT_ARMOR_FEET,
        }.get(armor_slot)
        if target is None:
            raise ValueError(f"armor_slot must be head/chest/legs/feet, got {armor_slot!r}")
        await self.move_item(src_slot, target, window_id=0)

    async def unequip_armor(self, armor_slot: str, dst_slot: int) -> None:
        """Move equipped armor back to ``dst_slot`` in main inventory."""
        from minecraft_bot.inventory.tracker import (
            SLOT_ARMOR_HEAD, SLOT_ARMOR_CHEST, SLOT_ARMOR_LEGS, SLOT_ARMOR_FEET,
        )
        src = {
            "head": SLOT_ARMOR_HEAD, "chest": SLOT_ARMOR_CHEST,
            "legs": SLOT_ARMOR_LEGS, "feet": SLOT_ARMOR_FEET,
        }.get(armor_slot)
        if src is None:
            raise ValueError(f"armor_slot must be head/chest/legs/feet, got {armor_slot!r}")
        await self.move_item(src, dst_slot, window_id=0)

    async def swap_to_offhand(self, src_slot: int) -> None:
        """Move the item at ``src_slot`` to the off-hand via F-key swap."""
        await self.click_slot(src_slot, mode="swap_offhand", window_id=0)

    # --- container open/close (FR-072) ---------------------------------

    async def _look_at_block(self, x: int, y: int, z: int) -> None:
        """Aim at the centre of block (x, y, z) so block_place lands.

        The sleep gives the server a couple of ticks to apply our new
        look direction before we send the block-click; otherwise the
        server's view of our facing may still be stale and the click
        will be rejected as "out of line of sight"."""
        await self.look_at(x + 0.5, y + 0.5, z + 0.5)
        await asyncio.sleep(0.25)

    def _pick_face_and_cursor(
        self, x: int, y: int, z: int,
    ) -> tuple[int, tuple[float, float, float]]:
        """Choose the block face whose outward normal points toward the
        bot's eye position. Returns ``(face_id, (cx, cy, cz))`` suitable
        for the block_place packet.

        Faces (Minecraft conventions): 0=bottom (-Y), 1=top (+Y),
        2=north (-Z), 3=south (+Z), 4=west (-X), 5=east (+X).
        """
        ex = self._physics.x
        ey = self._physics.y + 1.62   # eye height
        ez = self._physics.z
        bx, by, bz = x + 0.5, y + 0.5, z + 0.5
        dx, dy, dz = ex - bx, ey - by, ez - bz
        # The dominant axis (largest |delta|) chooses the face.
        adx, ady, adz = abs(dx), abs(dy), abs(dz)
        if adx >= ady and adx >= adz:
            if dx >= 0:
                # Bot is east of block — clicked west face? no, east face.
                return 5, (1.0, 0.5, 0.5)
            else:
                return 4, (0.0, 0.5, 0.5)
        if adz >= adx and adz >= ady:
            if dz >= 0:
                return 3, (0.5, 0.5, 1.0)
            else:
                return 2, (0.5, 0.5, 0.0)
        if dy >= 0:
            return 1, (0.5, 1.0, 0.5)
        return 0, (0.5, 0.0, 0.5)

    async def open_block_container(
        self, x: int, y: int, z: int, *,
        timeout: float = 5.0, wait_for_slot: bool = False,
        face: Optional[int] = None,
        cursor: Optional[tuple[float, float, float]] = None,
    ) -> int:
        """Right-click the block at (x, y, z) to open its container UI
        (chest / furnace / crafting table / barrel / shulker / etc.)
        and wait for the server to acknowledge with ``open_window`` +
        the first ``window_items`` packet.

        The bot rotates to face the block first; ``face`` and ``cursor``
        default to whichever face is closest to the bot, derived from
        the bot's current eye position (so the click is geometrically
        valid). Pass explicit values to override (e.g., to click the
        bottom of a hanging shulker box).

        Returns the ``window_id`` of the opened container. Raises
        :class:`BotBusy` if the container slot is taken;
        :class:`asyncio.TimeoutError` if the server doesn't open a
        container within ``timeout``.
        """
        from minecraft_bot.protocol.v763.packets.play.serverbound import (
            block_place as sb_block_place,
        )
        async with guard(self.container_slot, wait_for_slot=wait_for_slot):
            chosen_face, chosen_cursor = (face, cursor) if face is not None and cursor is not None \
                else self._pick_face_and_cursor(x, y, z)
            # Aim at the block, then immediately send the click. We
            # cannot let the physics ticker squeeze a Position-only
            # update between PositionLook and BlockPlace — some Paper
            # configs treat the position-only update as a rotation reset.
            dx = (x + 0.5) - self._physics.x
            dy = (y + 0.5) - (self._physics.y + 1.62)
            dz = (z + 0.5) - self._physics.z
            dist_xz = math.hypot(dx, dz)
            yaw = -math.degrees(math.atan2(dx, dz)) % 360.0
            pitch = -math.degrees(math.atan2(dy, dist_xz)) if dist_xz else 0.0
            self._yaw = yaw
            self._pitch = pitch
            await self._conn.send(sb_position_look.PositionLook(
                x=self._physics.x, y=self._physics.y, z=self._physics.z,
                yaw=yaw, pitch=pitch, on_ground=self._physics.on_ground,
            ))
            await self._conn.send(sb_block_place.BlockPlace(
                hand=0,
                location=(x, y, z),
                direction=chosen_face,
                cursor_x=chosen_cursor[0],
                cursor_y=chosen_cursor[1],
                cursor_z=chosen_cursor[2],
                inside_block=False,
                sequence=0,
            ))
            opened = await self._conn.wait_for(cb_open_window.OpenWindow, timeout=timeout)
            # The server typically sends WindowItems immediately after
            # OpenWindow — wait a short, fixed interval for it to land
            # (registering another wait_for here would race: the packet
            # has often already been dispatched by the time we get here).
            for _ in range(20):  # up to ~1 s
                await asyncio.sleep(0.05)
                if (self.inventory.container_window_id == opened.window_id
                        and self.inventory.container_slots):
                    break
            return opened.window_id

    async def open_chest(self, x: int, y: int, z: int, **kw) -> int:
        return await self.open_block_container(x, y, z, **kw)

    async def open_furnace(self, x: int, y: int, z: int, **kw) -> int:
        return await self.open_block_container(x, y, z, **kw)

    async def open_crafting_table(self, x: int, y: int, z: int, **kw) -> int:
        return await self.open_block_container(x, y, z, **kw)

    async def close_container(self) -> None:
        """Close the currently-open container (container slot)."""
        wid = self.inventory.container_window_id
        if wid is None:
            return
        async with guard(self.container_slot):
            await self._conn.send(sb_close_window.CloseWindow(window_id=wid))
        # Mirror local state immediately; the server doesn't echo a close.
        self.inventory.on_close_window(cb_close_window.CloseWindow(window_id=wid))

    # --- craft + smelt (FR-074..FR-080) --------------------------------

    async def craft(
        self,
        recipe: list[Optional[str]],
        x: int, y: int, z: int,
        *,
        repeat: int = 1,
        timeout: float = 8.0,
    ) -> int:
        """Craft an item using a 3×3 crafting table at (x, y, z).

        ``recipe`` is a 9-element list of item names (or ``None`` for
        empty), laid out row-major as the table grid::

            [ slot1, slot2, slot3,
              slot4, slot5, slot6,
              slot7, slot8, slot9 ]

        The bot opens the crafting table, places each ingredient via a
        pick-up-from-inventory → place-into-grid pair, then shift-clicks
        the result slot ``repeat`` times to pull crafted output into the
        inventory. Returns the count of result items pulled.

        Caller must have the ingredients available in inventory before
        calling; missing ingredients silently produce 0 output.
        """
        if len(recipe) != 9:
            raise ValueError(f"recipe must be 9 elements, got {len(recipe)}")

        wid = await self.open_crafting_table(x, y, z, timeout=timeout)
        try:
            # Slot indices in the crafting table window:
            #   0       = result
            #   1..9    = the 3×3 grid
            #   10..36  = player main inventory (9..35 in player space)
            #   37..45  = player hotbar
            for grid_idx, ingredient_name in enumerate(recipe, start=1):
                if ingredient_name is None:
                    continue
                # Find the ingredient in player inventory.
                src = self.inventory.find_item(ingredient_name)
                if src is None:
                    continue
                # Translate player-space slot (0..45) to container-window slot:
                # in a crafting table, player main is 10..36 (slot 9 → 10..36)
                # and hotbar is 37..45.
                if 9 <= src <= 35:
                    src_in_window = src + 1   # +1 for offset of result
                elif 36 <= src <= 44:
                    src_in_window = src + 1   # 36..44 → 37..45
                else:
                    continue   # armor / craft / offhand — not directly clickable
                # Pick up one from src (right-click splits stack; we use
                # left-click + drop-extras-later for simplicity since the
                # grid takes one item per slot).
                await self.click_slot(src_in_window, mode="left", window_id=wid)
                await asyncio.sleep(0.03)
                # Place ONE into grid_idx (right-click puts one and keeps the rest in cursor).
                await self.click_slot(grid_idx, mode="right", window_id=wid)
                await asyncio.sleep(0.03)
                # Return remaining cursor stack back to src.
                await self.click_slot(src_in_window, mode="left", window_id=wid)
                await asyncio.sleep(0.03)
            # Shift-click the result to harvest.
            collected = 0
            for _ in range(repeat):
                before = self._container_count_after_shift(wid)
                await self.click_slot(0, mode="shift_left", window_id=wid)
                await asyncio.sleep(0.05)
                # Approximation: bump collected by 1 per shift-click; the
                # server returns the actual count via window_items refresh.
                collected += 1
            return collected
        finally:
            await self.close_container()

    def _container_count_after_shift(self, wid: int) -> int:
        """Helper for craft/smelt: count items in player part of the
        container window before the operation (for delta computation)."""
        # Not strictly needed for the current implementation; reserved
        # for future precise result counting via window_items diff.
        return sum(s.count for s in self.inventory.player_slots if s is not None)

    async def smelt(
        self,
        input_item: str, fuel_item: str,
        x: int, y: int, z: int,
        *,
        timeout: float = 8.0,
    ) -> None:
        """Place ``input_item`` and ``fuel_item`` into a furnace at
        (x, y, z) and close the container. The caller polls the
        furnace later (or re-opens it) to harvest the result.

        Furnace slot layout: 0 = input, 1 = fuel, 2 = output, 3..38 =
        player main + hotbar.
        """
        wid = await self.open_furnace(x, y, z, timeout=timeout)
        try:
            for player_slot, target_slot in (
                (self.inventory.find_item(input_item), 0),
                (self.inventory.find_item(fuel_item), 1),
            ):
                if player_slot is None:
                    continue
                # Map player slot -> furnace-window slot (furnace has 3
                # internal slots, then player inventory at 3..38 / hotbar 30..38).
                if 9 <= player_slot <= 35:
                    src_in_window = player_slot - 9 + 3   # 9→3, 35→29
                elif 36 <= player_slot <= 44:
                    src_in_window = player_slot - 36 + 30  # 36→30, 44→38
                else:
                    continue
                # Pick up the whole stack, place it onto the furnace slot.
                await self.click_slot(src_in_window, mode="left", window_id=wid)
                await asyncio.sleep(0.03)
                await self.click_slot(target_slot, mode="left", window_id=wid)
                await asyncio.sleep(0.03)
                # If there's residue on the cursor (shouldn't be for a
                # single-stack move), drop it back.
                if self.inventory.cursor is not None:
                    await self.click_slot(src_in_window, mode="left", window_id=wid)
                    await asyncio.sleep(0.03)
        finally:
            await self.close_container()

    # --- follow (FR-036..FR-038) ---------------------------------------

    async def follow(
        self,
        eid: int,
        *,
        distance: float = 3.0,
        timeout: Optional[float] = None,
        wait_for_slot: bool = False,
        re_path_radius: float = 2.0,
    ) -> None:
        """Track entity ``eid`` keeping ``distance`` blocks behind it.

        Re-paths whenever the target moves more than ``re_path_radius``
        blocks from the position the bot was walking toward. Stops only
        when:

        - the bot is within ``distance + 1`` of the target AND target
          has stopped moving for a few ticks, OR
        - the entity disappears from the tracker → raises :class:`TargetLost`, OR
        - the timeout elapses → raises :class:`WalkTimeout`.
        """
        from minecraft_bot.errors import TargetLost
        async with guard(self.movement_slot, wait_for_slot=wait_for_slot):
            start_t = time.monotonic()
            last_target_pos: Optional[tuple[float, float, float]] = None
            target_lost_count = 0

            while True:
                if timeout is not None and time.monotonic() - start_t > timeout:
                    self._set_intent(dx=0, dz=0)
                    raise WalkTimeout(("entity", eid), time.monotonic() - start_t)

                target = self.entities.find_by_id(eid)
                if target is None:
                    target_lost_count += 1
                    # Allow a brief grace period — entity_move packets may
                    # transiently desync — but bail after ~1.5 s.
                    if target_lost_count > 30:
                        self._set_intent(dx=0, dz=0)
                        raise TargetLost(eid)
                    await asyncio.sleep(0.05)
                    continue
                target_lost_count = 0

                tx, ty, tz = target.x, target.y, target.z
                # Already close enough?
                dx, dz = tx - self._physics.x, tz - self._physics.z
                horiz = math.hypot(dx, dz)
                if horiz <= distance:
                    self._set_intent(dx=0, dz=0)
                    # Stay close: sample again next tick.
                    last_target_pos = (tx, ty, tz)
                    await asyncio.sleep(0.1)
                    continue

                # Decide a goal: distance blocks short of the target
                # (along the line from us to it).
                norm = max(horiz, 1e-6)
                gx = tx - dx / norm * distance
                gz = tz - dz / norm * distance

                # Re-path only when target has moved significantly OR no plan yet.
                need_replan = (
                    last_target_pos is None
                    or math.hypot(tx - last_target_pos[0], tz - last_target_pos[2]) > re_path_radius
                )
                if not need_replan:
                    # Keep current intent and let the previous waypoint
                    # iteration drive movement.
                    await asyncio.sleep(0.1)
                    continue
                last_target_pos = (tx, ty, tz)

                # Plan to one block short of the target. Iterate waypoints
                # for a short window (~3 s), then re-evaluate from the top.
                start = (int(self._physics.x), int(self._physics.y), int(self._physics.z))
                goal = (int(gx), int(ty), int(gz))
                if start == goal:
                    self._set_intent(dx=0, dz=0)
                    await asyncio.sleep(0.1)
                    continue
                try:
                    path = find_path(self.world, start, goal, max_fall=3)
                except NoPathFound:
                    await asyncio.sleep(0.25)
                    continue
                # Walk through up to 3 s worth of waypoints, then re-check.
                window_end = time.monotonic() + 3.0
                for waypoint in path.nodes[1:]:
                    while time.monotonic() < window_end:
                        if timeout is not None and time.monotonic() - start_t > timeout:
                            self._set_intent(dx=0, dz=0)
                            raise WalkTimeout(("entity", eid), time.monotonic() - start_t)
                        wx, wy, wz = waypoint
                        ddx = (wx + 0.5) - self._physics.x
                        ddz = (wz + 0.5) - self._physics.z
                        mag = math.hypot(ddx, ddz)
                        if mag < 0.4:
                            break
                        nxv, nzv = (ddx / mag, ddz / mag)
                        self._set_intent(dx=nxv, dz=nzv, sprint=True)
                        await asyncio.sleep(PHYSICS_TICK_DT)
                    if time.monotonic() >= window_end:
                        break

    # --- dig (FR-081..FR-085) ------------------------------------------

    async def dig(
        self,
        x: int, y: int, z: int,
        *,
        tool: Optional[str] = None,
        timeout_multiplier: float = 2.0,
        wait_for_slot: bool = False,
    ) -> None:
        """Break the block at (x, y, z). Uses the movement slot.

        Sequence: ``block_dig`` status=0 (start) → wait the natural break
        time for the block + held tool → status=2 (finish) →
        ``arm_animation``. If the block hasn't been removed from the
        world cache within ``timeout_multiplier × natural_break_time``,
        raises :class:`DigFailed`.

        If ``tool`` is None, uses the bot's currently-held item.
        """
        from minecraft_bot.protocol.v763.packets.play.serverbound import (
            block_dig as sb_block_dig,
        )
        name = self.world.get_block_name(x, y, z) or "minecraft:air"
        if tool is None:
            held = self.held_item
            tool = held.name if held is not None else None
        natural = break_seconds(name, tool)
        if natural < 0:
            raise DigFailed((x, y, z), reason=f"{name} is unbreakable")
        # Face = top of block (default); look_at the block first.
        async with guard(self.movement_slot, wait_for_slot=wait_for_slot):
            await self._look_at_block(x, y, z)
            face, _ = self._pick_face_and_cursor(x, y, z)
            # Send dig START.
            await self._conn.send(sb_block_dig.BlockDig(
                status=0, location=(x, y, z), face=face, sequence=0,
            ))
            # Continuous arm animation while digging.
            await self._conn.send(sb_arm.ArmAnimation(hand=0))
            # Wait the natural break time.
            await asyncio.sleep(max(0.05, natural))
            # Send dig FINISH.
            await self._conn.send(sb_block_dig.BlockDig(
                status=2, location=(x, y, z), face=face, sequence=0,
            ))
            # Poll world cache for up to timeout_multiplier × natural for
            # the block to actually become air.
            poll_end = time.monotonic() + timeout_multiplier * max(natural, 0.5)
            while time.monotonic() < poll_end:
                current = self.world.get_block(x, y, z)
                if current == 0:
                    return
                await asyncio.sleep(0.05)
            raise DigFailed(
                (x, y, z),
                reason=f"block {name} did not break within {timeout_multiplier * natural:.1f}s",
            )

    # --- auto-eat (FR-088..FR-092) -------------------------------------

    def auto_eat(
        self,
        *,
        threshold: int = 15,
        eat_duration: float = 1.6,
        picker=None,
    ) -> None:
        """Start a background task that eats food whenever
        ``bot.food < threshold``.

        ``picker`` is a callable ``(list[FoodInfo]) -> FoodInfo`` that
        chooses which food to consume from the bot's inventory (default
        ``pick_highest_saturation`` from foods). Pass a custom function
        to enforce a different policy.

        Idempotent: calling auto_eat() twice replaces the previous task.
        Stop with :meth:`stop_auto_eat`.
        """
        self.stop_auto_eat()
        self._auto_eat_task = asyncio.create_task(
            self._auto_eat_loop(threshold, eat_duration, picker or pick_highest_saturation),
            name="bot-auto-eat",
        )

    def stop_auto_eat(self) -> None:
        task = self._auto_eat_task
        self._auto_eat_task = None
        if task is not None:
            task.cancel()

    async def _auto_eat_loop(self, threshold: int, eat_duration: float, picker) -> None:
        while True:
            try:
                await asyncio.sleep(0.25)   # 5 ticks
                if not self.is_connected or self._food >= threshold:
                    continue
                # Find food in inventory; pick by policy.
                hotbar = [
                    (i, slot) for i, slot in enumerate(self.inventory.hotbar_items())
                    if slot is not None and slot.item_id in _FOOD_BY_ID
                ]
                if not hotbar:
                    # Try main inventory food too — but we'd need to swap to
                    # hotbar; for MVP we only eat from hotbar.
                    continue
                infos = [_FOOD_BY_ID[slot.item_id] for _, slot in hotbar]
                chosen = picker(infos)
                if chosen is None:
                    continue
                # Find the slot index of the chosen food.
                slot_index_in_hotbar = next(
                    i for i, slot in hotbar if slot.item_id == chosen.item_id
                )
                await self.select_slot(slot_index_in_hotbar)
                await asyncio.sleep(0.1)
                await self.use_item(hand=0)
                await asyncio.sleep(eat_duration)
            except asyncio.CancelledError:
                return
            except Exception:
                # Don't let one bad tick kill the loop.
                await asyncio.sleep(0.5)

    # --- walk_to (FR-031..FR-035) -------------------------------------

    async def walk_to(
        self,
        x: float, y: float, z: float,
        *,
        timeout: float = 60.0,
        max_fall: int = 3,
        wait_for_slot: bool = False,
    ) -> None:
        """Walk to ``(x, y, z)`` using A* over the World cache and the
        physics ticker.

        Raises :class:`BotBusy` if the movement slot is taken (unless
        ``wait_for_slot=True``), :class:`NoPathFound` if no path
        exists, or :class:`WalkTimeout` on timeout.
        """
        async with guard(self.movement_slot, wait_for_slot=wait_for_slot):
            start_t = time.monotonic()
            goal = (int(x), int(y), int(z))
            while True:
                if time.monotonic() - start_t > timeout:
                    self._set_intent(dx=0, dz=0)
                    raise WalkTimeout((x, y, z), time.monotonic() - start_t)

                # Already there?
                dx, dy, dz = x - self._physics.x, y - self._physics.y, z - self._physics.z
                if math.hypot(dx, dz) < WALK_TARGET_RADIUS and abs(dy) < 2.0:
                    self._set_intent(dx=0, dz=0)
                    return

                # Plan a path from current feet block to the goal block.
                start = (int(self._physics.x), int(self._physics.y), int(self._physics.z))
                try:
                    path = find_path(self.world, start, goal, max_fall=max_fall)
                except NoPathFound:
                    self._set_intent(dx=0, dz=0)
                    raise

                # Walk path: pick the next waypoint and drive intent
                # toward it until close enough, then move to the next.
                for waypoint in path.nodes[1:]:
                    while True:
                        if time.monotonic() - start_t > timeout:
                            self._set_intent(dx=0, dz=0)
                            raise WalkTimeout((x, y, z), time.monotonic() - start_t)
                        wx, wy, wz = waypoint
                        ddx = (wx + 0.5) - self._physics.x
                        ddz = (wz + 0.5) - self._physics.z
                        mag = math.hypot(ddx, ddz)
                        if mag < 0.4:
                            break
                        nx, nz = (ddx / mag, ddz / mag)
                        self._set_intent(dx=nx, dz=nz, sprint=True)
                        await asyncio.sleep(PHYSICS_TICK_DT)
                # After full path, loop and re-plan or exit.

    # --- chat ----------------------------------------------------------

    async def say(self, message: str) -> None:
        """Send a chat message (action slot)."""
        async with guard(self.action_slot):
            now_ms = int(time.time() * 1000)
            await self._conn.send(sb_chat.ChatMessage(
                message=message,
                timestamp=now_ms,
                salt=0,
                signature=None,
                message_count=0,
                acknowledged=b"\x00\x00\x00",
            ))

    async def command(self, cmd: str) -> None:
        """Send a slash command (without the leading '/').

        Payload format (after the command string): timestamp(i64) +
        salt(i64) + varint signatures-count(0) + varint message_count(0)
        + 3-byte acknowledged BitSet. Offline-mode bots send no
        signatures."""
        import struct as _s
        if cmd.startswith("/"):
            cmd = cmd[1:]
        now_ms = int(time.time() * 1000)
        payload = (
            _s.pack(">qq", now_ms, 0) + b"\x00"      # 0 signatures
            + b"\x00"                                 # message_count = 0
            + b"\x00\x00\x00"                         # 3-byte ack bitset
        )
        async with guard(self.action_slot):
            await self._conn.send(sb_command.ChatCommand(
                command=cmd, payload=payload,
            ))

    # --- event hooks --------------------------------------------------

    def on(self, event_type: type) -> Callable[[HandlerFn], HandlerFn]:
        """Decorator: ``@bot.on(EventType) def handler(evt): ...``."""
        def deco(fn: HandlerFn) -> HandlerFn:
            self._hooks.append(_HookEntry(event_type=event_type, handler=fn))
            return fn
        return deco

    def subscribe(self, event_type: type, handler: HandlerFn) -> None:
        self._hooks.append(_HookEntry(event_type=event_type, handler=handler))

    def unsubscribe(self, event_type: type, handler: HandlerFn) -> None:
        self._hooks = [h for h in self._hooks
                       if not (h.event_type is event_type and h.handler is handler)]

    def drain_events(self) -> list[Event]:
        out = list(self._event_queue)
        self._event_queue.clear()
        return out

    async def next_event(
        self, event_type: Optional[type] = None, *, timeout: Optional[float] = None,
    ) -> Event:
        """Await the next event (optionally of a specific type)."""
        end_t = None if timeout is None else time.monotonic() + timeout
        while True:
            for i, evt in enumerate(self._event_queue):
                if event_type is None or isinstance(evt, event_type):
                    del self._event_queue[i]
                    return evt
            wait = None if end_t is None else max(0.0, end_t - time.monotonic())
            fut: asyncio.Future[Event] = asyncio.get_event_loop().create_future()
            self._event_waiters.append(fut)
            try:
                if wait is None:
                    return await fut
                return await asyncio.wait_for(fut, timeout=wait)
            except asyncio.TimeoutError:
                self._event_waiters.remove(fut)
                raise

    def _emit(self, event: Event) -> None:
        # Queue for next_event/drain_events.
        self._event_queue.append(event)
        # Wake any waiters that match.
        still_waiting = []
        for fut in self._event_waiters:
            if fut.done():
                continue
            fut.set_result(event)
        self._event_waiters.clear()
        # Dispatch to hooks (sync immediately, async via create_task).
        for entry in self._hooks:
            if isinstance(event, entry.event_type):
                try:
                    rv = entry.handler(event)
                    if asyncio.iscoroutine(rv):
                        asyncio.create_task(rv)
                except Exception:
                    pass


__all__ = ["Bot", "BotBusy"]
