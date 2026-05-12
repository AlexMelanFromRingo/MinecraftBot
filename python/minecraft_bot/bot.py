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
from minecraft_bot.protocol.v763.packets.play.clientbound import (
    block_change as cb_block_change,
    experience as cb_experience,
    game_state_change as cb_game_state,
    held_item_slot as cb_held,
    login as cb_login,
    map_chunk as cb_map_chunk,
    multi_block_change as cb_mbc,
    player_chat as cb_player_chat,
    position as cb_position,
    profileless_chat as cb_profileless_chat,
    respawn as cb_respawn,
    system_chat as cb_system_chat,
    unload_chunk as cb_unload,
    update_health as cb_update_health,
)
from minecraft_bot.protocol.v763.packets.play.serverbound import (
    arm_animation as sb_arm,
    chat_command as sb_command,
    chat_message as sb_chat,
    position as sb_position,
    position_look as sb_position_look,
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
        sub(c.on(Reconnected, self._on_reconnected))

    # --- packet handlers ----------------------------------------------

    def _on_login(self, p) -> None:
        self._entity_id = p.entity_id
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

        Skips simulation if (a) we haven't received an initial server
        position yet, or (b) the chunk under the bot's feet isn't
        loaded yet — without ground data, our collision detection would
        let the bot fall through the world and diverge from the server.
        """
        if not self._has_initial_position:
            return self._physics
        cx, cz = int(self._physics.x) >> 4, int(self._physics.z) >> 4
        if (cx, cz) not in self.world.chunks:
            return self._physics
        in_water = self.world.is_water(
            int(self._physics.x), int(self._physics.y), int(self._physics.z)
        )
        new_state = physics_tick(self._physics, self._intent, self.world, in_water=in_water)
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

    async def swing_arm(self) -> None:
        """Action slot: animate arm swing (hand=0 main)."""
        async with guard(self.action_slot):
            await self._conn.send(sb_arm.ArmAnimation(hand=0))

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
