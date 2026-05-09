"""Connection lifecycle.

Implements the public :class:`Connection` per
``specs/001-protocol-foundation/contracts/python-api.md``: factory
``Connection.offline(...)``, ``connect()`` / ``disconnect()`` lifecycle,
:meth:`send` (FIFO-ordered), hook registration (``on``, ``off``,
``wait_for``), keep-alive and teleport-confirm auto-reply (FR-005,
FR-006), opt-in auto-reconnect (FR-007a).

Online-mode authentication is **out of scope** for this milestone
(FR-017b); a clientbound :class:`EncryptionBegin` in offline mode
raises :class:`~minecraft_bot.errors.LoginFailed` with a clear
message.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import logging
import random
import uuid as _uuid_stdlib
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from minecraft_bot.codec import Reader, Writer, varint
from minecraft_bot.errors import (
    ConnectionClosed,
    ConnectionDropped,
    DecodeError,
    HandshakeFailed,
    KickedByServer,
    LoginFailed,
    PeerReset,
    ProtocolError,
    UnknownPacketId,
)
from minecraft_bot.framer import Framer
from minecraft_bot.protocol import V_1_20_1, ProtocolVersion
from minecraft_bot.protocol.v763.packets.handshaking.serverbound import (
    set_protocol as p_set_protocol,
)
from minecraft_bot.protocol.v763.packets.login.clientbound import compress as p_l_cb_compress
from minecraft_bot.protocol.v763.packets.login.clientbound import disconnect as p_l_cb_disconnect
from minecraft_bot.protocol.v763.packets.login.clientbound import (
    encryption_begin as p_l_cb_encryption,
)
from minecraft_bot.protocol.v763.packets.login.clientbound import (
    login_plugin_request as p_l_cb_lpr,
)
from minecraft_bot.protocol.v763.packets.login.clientbound import success as p_l_cb_success
from minecraft_bot.protocol.v763.packets.login.serverbound import login_start as p_l_sb_login_start
from minecraft_bot.protocol.v763.packets.login.serverbound import (
    login_plugin_response as p_l_sb_lpr,
)
from minecraft_bot.protocol.v763.packets.play.clientbound import keep_alive as p_p_cb_ka
from minecraft_bot.protocol.v763.packets.play.clientbound import (
    kick_disconnect as p_p_cb_kick,
)
from minecraft_bot.protocol.v763.packets.play.clientbound import login as p_p_cb_login
from minecraft_bot.protocol.v763.packets.play.clientbound import position as p_p_cb_pos
from minecraft_bot.protocol.v763.packets.play.serverbound import keep_alive as p_p_sb_ka
from minecraft_bot.protocol.v763.packets.play.serverbound import (
    teleport_confirm as p_p_sb_tc,
)
from minecraft_bot.protocol.v763.registry import CodecRegistry
from minecraft_bot.protocol.v763.states import ConnectionState, Direction
from minecraft_bot.wire_log import WireLog

_log = logging.getLogger("minecraft_bot.protocol.connection")

# Module-shared registry — built once per process. Read-only after
# construction; safe to share across multiple Connection instances per
# FR-017a (multi-bot readiness).
_REGISTRY: Optional[CodecRegistry] = None


def _registry() -> CodecRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = CodecRegistry.build()
    return _REGISTRY


# --- ReconnectPolicy (re-exported here for convenience) -------------------


@dataclass(frozen=True, slots=True)
class ReconnectPolicy:
    """Exponential-backoff parameters for opt-in auto-reconnect (FR-007a).

    See ``contracts/python-api.md``. Only consulted when
    ``Connection.offline(..., auto_reconnect=True)``.
    """

    max_attempts: int = 5
    initial_delay: float = 1.0
    max_delay: float = 30.0
    multiplier: float = 2.0
    jitter: float = 0.25

    def __post_init__(self) -> None:
        if self.max_attempts < 0:
            raise ValueError(f"max_attempts must be >= 0 (got {self.max_attempts})")
        if self.initial_delay <= 0:
            raise ValueError(f"initial_delay must be > 0 (got {self.initial_delay})")
        if self.max_delay < self.initial_delay:
            raise ValueError(
                f"max_delay ({self.max_delay}) must be >= initial_delay ({self.initial_delay})"
            )
        if self.multiplier < 1.0:
            raise ValueError(f"multiplier must be >= 1.0 (got {self.multiplier})")
        if not 0.0 <= self.jitter < 1.0:
            raise ValueError(f"jitter must be in [0, 1) (got {self.jitter})")


# --- Reconnected event ----------------------------------------------------


@dataclass(frozen=True, slots=True)
class Reconnected:
    """Synthetic event-packet emitted after a successful auto-reconnect cycle.

    Subscribers can hook this to rebuild any state the framework just
    discarded between sessions (FR-007a — per-connection state always
    reset on reconnect).
    """

    attempts: int
    elapsed: float


# --- Subscription handle --------------------------------------------------


@dataclass(slots=True)
class Subscription:
    packet_type: type
    handler: Callable[..., Any]
    _connection: "Connection" = field(repr=False)

    def cancel(self) -> None:
        self._connection.off(self)


# --- Connection -----------------------------------------------------------


class Connection:
    """Public Bot connection. See ``contracts/python-api.md``.

    Construct via :meth:`Connection.offline` (factory). Direct
    ``__init__`` is not part of the public API.
    """

    # ------ construction ---------------------------------------------------

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        version: ProtocolVersion,
        auto_reconnect: bool,
        reconnect_policy: Optional[ReconnectPolicy],
        write_buffer_size: int,
        wire_log: Optional[WireLog],
    ) -> None:
        if version.number != 763:
            raise ValueError(
                f"only protocol 763 (Minecraft 1.20.1) is implemented; got {version.number}"
            )
        if write_buffer_size <= 0:
            raise ValueError("write_buffer_size must be > 0")
        if not username:
            raise ValueError("username is required")

        self._host = host
        self._port = port
        self._username = username
        self._version = version
        self._auto_reconnect = auto_reconnect
        self._reconnect_policy = reconnect_policy or ReconnectPolicy()
        self._write_buffer_size = write_buffer_size
        self._wire_log = wire_log

        self._state = ConnectionState.HANDSHAKING
        self._compression_threshold: int = -1
        self._registry = _registry()

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._framer = Framer(compression_threshold=-1)

        self._write_lock = asyncio.Lock()
        self._decode_task: Optional[asyncio.Task[None]] = None
        self._closed = asyncio.Event()
        self._closed.set()  # starts in closed state

        # subscribers: packet_type -> list of handlers
        self._handlers: dict[type, list[Callable[..., Any]]] = {}
        # one-shot wait_for futures: list of (packet_type, predicate, future)
        self._waiters: list[tuple[type, Optional[Callable[..., bool]], asyncio.Future[Any]]] = []

        # Per-session derived state. Reset between sessions on reconnect.
        self._entity_id: Optional[int] = None
        self._game_mode: Optional[int] = None
        self._world_name: Optional[str] = None

        self._loop_error: Optional[BaseException] = None

    @classmethod
    def offline(
        cls,
        host: str,
        port: int,
        username: str,
        *,
        version: ProtocolVersion = V_1_20_1,
        auto_reconnect: bool = False,
        reconnect_policy: Optional[ReconnectPolicy] = None,
        write_buffer_size: int = 1024,
        wire_log: Optional[WireLog] = None,
    ) -> "Connection":
        """Construct an offline-mode Connection (FR-017b)."""
        return cls(
            host=host, port=port, username=username, version=version,
            auto_reconnect=auto_reconnect, reconnect_policy=reconnect_policy,
            write_buffer_size=write_buffer_size, wire_log=wire_log,
        )

    # ------ public read-only properties ------------------------------------

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def version(self) -> ProtocolVersion:
        return self._version

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def username(self) -> str:
        return self._username

    @property
    def compression_threshold(self) -> int:
        return self._compression_threshold

    @property
    def is_connected(self) -> bool:
        return not self._closed.is_set() and self._writer is not None and not self._writer.is_closing()

    @property
    def wire_log(self) -> Optional[WireLog]:
        return self._wire_log

    @property
    def entity_id(self) -> Optional[int]:
        return self._entity_id

    @property
    def game_mode(self) -> Optional[int]:
        return self._game_mode

    @property
    def world_name(self) -> Optional[str]:
        return self._world_name

    # ------ async context manager -----------------------------------------

    async def __aenter__(self) -> "Connection":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.is_connected:
            await self.disconnect()

    # ------ lifecycle ------------------------------------------------------

    async def connect(self) -> None:
        """Open TCP, run handshake → login → play."""
        if self._auto_reconnect:
            await self._connect_with_reconnect()
            return
        await self._connect_once()

    async def _connect_once(self) -> None:
        try:
            self._reader, self._writer = await asyncio.open_connection(self._host, self._port)
        except OSError as exc:
            raise ConnectionDropped(f"TCP connect failed: {exc}") from exc

        self._closed.clear()
        self._loop_error = None
        self._reset_session_state()

        if self._wire_log is not None:
            self._wire_log.start_session(
                version=self._version.number,
                host=self._host, port=self._port, username=self._username,
            )

        try:
            await self._send_handshake()
            self._state = ConnectionState.LOGIN
            self._framer.compression_threshold = -1
            self._compression_threshold = -1
            await self._send_login_start()
            await self._run_login_loop()
            # state is now PLAY
            self._decode_task = asyncio.create_task(
                self._play_decode_loop(), name=f"mc-bot:{self._username}:decode",
            )
            # Wait for the LoginPlay packet so connect() returns with
            # entity_id/world_name populated. Without this, the first 50ms
            # post-connect see a "PLAY but data unset" race.
            try:
                await self.wait_for(p_p_cb_login.Login, timeout=10.0)
            except asyncio.TimeoutError as exc:
                raise LoginFailed(
                    "did not receive Login (Play) packet within 10s of "
                    "transitioning to PLAY state"
                ) from exc
        except BaseException:
            if self._decode_task is not None and not self._decode_task.done():
                self._decode_task.cancel()
                try:
                    await self._decode_task
                except (asyncio.CancelledError, BaseException):
                    pass
                self._decode_task = None
            await self._close_socket_quiet()
            self._closed.set()
            raise

    async def _connect_with_reconnect(self) -> None:
        attempt = 0
        delay = self._reconnect_policy.initial_delay
        started = asyncio.get_event_loop().time()
        while True:
            try:
                await self._connect_once()
                if attempt > 0:
                    elapsed = asyncio.get_event_loop().time() - started
                    self._dispatch(Reconnected(attempts=attempt, elapsed=elapsed))
                return
            except (ConnectionDropped, HandshakeFailed, LoginFailed) as exc:
                if attempt >= self._reconnect_policy.max_attempts:
                    raise
                attempt += 1
                jitter = 1.0 + random.uniform(
                    -self._reconnect_policy.jitter, self._reconnect_policy.jitter,
                )
                wait = min(delay * jitter, self._reconnect_policy.max_delay)
                _log.info(
                    "connect failed (%s); retry %d/%d in %.2fs",
                    exc, attempt, self._reconnect_policy.max_attempts, wait,
                )
                await asyncio.sleep(wait)
                delay = min(delay * self._reconnect_policy.multiplier,
                            self._reconnect_policy.max_delay)

    async def disconnect(self, reason: Optional[str] = None) -> None:
        """Close the connection cleanly. Idempotent."""
        if self._closed.is_set():
            return
        self._closed.set()
        if self._decode_task is not None and not self._decode_task.done():
            self._decode_task.cancel()
            try:
                await self._decode_task
            except (asyncio.CancelledError, BaseException):
                pass
            self._decode_task = None
        await self._close_socket_quiet()
        if reason:
            _log.info("disconnect: %s", reason)

    async def _close_socket_quiet(self) -> None:
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except (OSError, ConnectionError):
                pass
            self._writer = None
            self._reader = None

    def _reset_session_state(self) -> None:
        self._entity_id = None
        self._game_mode = None
        self._world_name = None
        self._state = ConnectionState.HANDSHAKING

    # ------ send (FIFO) ----------------------------------------------------

    async def send(self, packet: Any) -> None:
        """Encode and write a serverbound packet under the FIFO write lock."""
        if not self.is_connected:
            raise ConnectionClosed("send() on a closed Connection")

        try:
            state, direction, packet_id = self._registry.lookup_id(type(packet))
        except KeyError as exc:
            raise ProtocolError(f"unregistered packet type: {type(packet).__name__}") from exc
        if direction != Direction.SERVERBOUND:
            raise ProtocolError(f"send() on non-serverbound packet: {type(packet).__name__}")

        # Encode body OUTSIDE the lock per R-03.
        body_writer = Writer()
        varint.write(packet_id, body_writer)
        encoder = self._registry.encoder(type(packet))
        encoder(packet, body_writer)
        body = body_writer.bytes()
        framed = self._framer.encode(body)

        async with self._write_lock:
            if self._writer is None or self._writer.is_closing():
                raise ConnectionClosed("writer disappeared between encode and send")
            self._writer.write(framed)
            await self._writer.drain()

        if self._wire_log is not None:
            self._wire_log.record(
                direction=Direction.SERVERBOUND, state=state,
                packet_id=packet_id,
                raw=body[len(self._encode_id_only(packet_id)):],
                name=type(packet).__module__.rsplit(".", 1)[-1],
            )

    @staticmethod
    def _encode_id_only(packet_id: int) -> bytes:
        w = Writer(); varint.write(packet_id, w); return w.bytes()

    # ------ subscription / hooks ------------------------------------------

    def on(self, packet_type: type, handler: Callable[..., Any]) -> Subscription:
        """Register a sync or async handler for ``packet_type``. Returns a
        :class:`Subscription` whose ``cancel()`` removes it."""
        self._handlers.setdefault(packet_type, []).append(handler)
        return Subscription(packet_type=packet_type, handler=handler, _connection=self)

    def off(self, sub: Subscription) -> None:
        handlers = self._handlers.get(sub.packet_type, [])
        try:
            handlers.remove(sub.handler)
        except ValueError:
            pass

    async def wait_for(
        self,
        packet_type: type,
        *,
        timeout: Optional[float] = None,
        predicate: Optional[Callable[[Any], bool]] = None,
    ) -> Any:
        """One-shot: returns the next packet of ``packet_type`` (matching
        ``predicate`` if given) or raises ``asyncio.TimeoutError``."""
        loop = asyncio.get_event_loop()
        fut: asyncio.Future[Any] = loop.create_future()
        entry = (packet_type, predicate, fut)
        self._waiters.append(entry)
        try:
            if timeout is None:
                return await fut
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            try:
                self._waiters.remove(entry)
            except ValueError:
                pass

    # ------ wire-log helper ----------------------------------------------

    def _wire_log_packet(
        self, direction: Direction, state: ConnectionState, packet_id: int,
        raw_body: bytes, decoded: Any,
    ) -> None:
        if self._wire_log is None:
            return
        try:
            name = type(decoded).__module__.rsplit(".", 1)[-1]
        except Exception:
            name = None
        self._wire_log.record(
            direction=direction, state=state, packet_id=packet_id,
            raw=raw_body, name=name, fields=None,  # fields=None for now (lossy)
        )

    # ------ login flow ----------------------------------------------------

    async def _send_handshake(self) -> None:
        packet = p_set_protocol.SetProtocol(
            protocol_version=self._version.number,
            server_host=self._host, server_port=self._port, next_state=2,  # 2 = LOGIN
        )
        await self._send_raw(packet, ConnectionState.HANDSHAKING)

    async def _send_login_start(self) -> None:
        packet = p_l_sb_login_start.LoginStart(
            username=self._username, player_uuid=offline_uuid(self._username),
        )
        await self._send_raw(packet, ConnectionState.LOGIN)

    async def _send_raw(self, packet: Any, state: ConnectionState) -> None:
        """Encode + send while we're still in HANDSHAKING/LOGIN — uses the
        same FIFO lock and framer as the public send()."""
        try:
            _, direction, packet_id = self._registry.lookup_id(type(packet))
        except KeyError as exc:
            raise ProtocolError(f"unregistered packet type: {type(packet).__name__}") from exc

        body_writer = Writer()
        varint.write(packet_id, body_writer)
        encoder = self._registry.encoder(type(packet))
        encoder(packet, body_writer)
        body = body_writer.bytes()
        framed = self._framer.encode(body)

        async with self._write_lock:
            if self._writer is None:
                raise ConnectionClosed("writer disappeared")
            self._writer.write(framed)
            await self._writer.drain()

        if self._wire_log is not None:
            id_only = self._encode_id_only(packet_id)
            self._wire_log.record(
                direction=direction, state=state, packet_id=packet_id,
                raw=body[len(id_only):],
                name=type(packet).__module__.rsplit(".", 1)[-1],
            )

    async def _run_login_loop(self) -> None:
        """Pump packets until Success transitions us to PLAY, or we error."""
        while True:
            packet = await self._read_one_typed(ConnectionState.LOGIN, Direction.CLIENTBOUND)
            if isinstance(packet, p_l_cb_disconnect.Disconnect):
                raise KickedByServer(packet.reason)
            if isinstance(packet, p_l_cb_compress.Compress):
                self._compression_threshold = packet.threshold
                self._framer.compression_threshold = packet.threshold
                continue
            if isinstance(packet, p_l_cb_encryption.EncryptionBegin):
                raise LoginFailed(
                    "server requested encryption (online-mode); offline-mode "
                    "connection cannot proceed. Use Connection.online_microsoft "
                    "(deferred to a future milestone)."
                )
            if isinstance(packet, p_l_cb_lpr.LoginPluginRequest):
                # Default: respond with no data (channel not understood).
                await self._send_raw(
                    p_l_sb_lpr.LoginPluginResponse(message_id=packet.message_id, data=None),
                    ConnectionState.LOGIN,
                )
                continue
            if isinstance(packet, p_l_cb_success.Success):
                self._state = ConnectionState.PLAY
                return
            # Unexpected packet type during login; surface for diagnostics.
            _log.warning("unexpected packet during login: %s", type(packet).__name__)

    async def _read_one_typed(
        self, state: ConnectionState, direction: Direction,
    ) -> Any:
        """Read one packet from the wire, decode against ``state`` registry."""
        # Fill the framer until try_extract returns something.
        while True:
            body = self._framer.try_extract()
            if body is not None:
                break
            chunk = await self._reader.read(4096)  # type: ignore[union-attr]
            if not chunk:
                raise ConnectionDropped("EOF during login")
            self._framer.feed(chunk)

        # Split id varint off the body.
        reader = Reader(body)
        try:
            packet_id = varint.read(reader)
        except DecodeError as exc:
            raise HandshakeFailed(f"malformed packet header: {exc}") from exc
        try:
            decoder = self._registry.decoder(state, direction, packet_id)
        except UnknownPacketId:
            _log.warning(
                "ignoring unknown clientbound packet during %s: id=0x%02x",
                state.name.lower(), packet_id,
            )
            return None
        try:
            payload = body[reader.position():]
            decoded = decoder(Reader(payload))
        except DecodeError as exc:
            raise HandshakeFailed(f"decode error in {state.name}/0x{packet_id:02x}: {exc}") from exc

        if self._wire_log is not None:
            self._wire_log.record(
                direction=direction, state=state, packet_id=packet_id,
                raw=payload, name=type(decoded).__module__.rsplit(".", 1)[-1],
            )

        return decoded

    # ------ play decode loop -----------------------------------------------

    async def _play_decode_loop(self) -> None:
        """Long-running decode-and-dispatch task.

        Auto-replies for KeepAlive (FR-005) and Position (FR-006) run BEFORE
        any user hook fan-out (R-07).
        """
        try:
            while not self._closed.is_set():
                body = self._framer.try_extract()
                if body is None:
                    chunk = await self._reader.read(4096)  # type: ignore[union-attr]
                    if not chunk:
                        raise ConnectionDropped("EOF on play stream")
                    self._framer.feed(chunk)
                    continue
                await self._handle_play_body(body)
        except asyncio.CancelledError:
            return
        except (ConnectionResetError, BrokenPipeError) as exc:
            self._loop_error = PeerReset(str(exc))
        except (ConnectionDropped, ProtocolError) as exc:
            self._loop_error = exc
        except OSError as exc:
            self._loop_error = ConnectionDropped(str(exc))
        finally:
            self._closed.set()

    async def _handle_play_body(self, body: bytes) -> None:
        reader = Reader(body)
        try:
            packet_id = varint.read(reader)
        except DecodeError:
            return  # malformed; skip
        try:
            decoder = self._registry.decoder(
                ConnectionState.PLAY, Direction.CLIENTBOUND, packet_id,
            )
        except UnknownPacketId:
            _log.debug("unknown play clientbound id 0x%02x; skipping", packet_id)
            return
        payload = body[reader.position():]
        try:
            decoded = decoder(Reader(payload))
        except DecodeError as exc:
            _log.warning("decode error on play 0x%02x: %s", packet_id, exc)
            return

        if self._wire_log is not None:
            self._wire_log.record(
                direction=Direction.CLIENTBOUND, state=ConnectionState.PLAY,
                packet_id=packet_id, raw=payload,
                name=type(decoded).__module__.rsplit(".", 1)[-1],
            )

        # --- critical-path auto-replies (R-07) ------------------------------
        if isinstance(decoded, p_p_cb_ka.KeepAlive):
            try:
                await self.send(p_p_sb_ka.KeepAlive(keep_alive_id=decoded.keep_alive_id))
            except ConnectionClosed:
                return
        elif isinstance(decoded, p_p_cb_pos.Position):
            try:
                await self.send(p_p_sb_tc.TeleportConfirm(teleport_id=decoded.teleport_id))
            except ConnectionClosed:
                return
        elif isinstance(decoded, p_p_cb_login.Login):
            self._entity_id = decoded.entity_id
            self._game_mode = decoded.game_mode
            self._world_name = decoded.world_name
        elif isinstance(decoded, p_p_cb_kick.KickDisconnect):
            self._loop_error = KickedByServer(decoded.reason)
            self._closed.set()
            return

        self._dispatch(decoded)

    # ------ subscriber fan-out --------------------------------------------

    def _dispatch(self, packet: Any) -> None:
        """Synchronously invoke handlers, then resolve any matching wait_for futures."""
        for handler in list(self._handlers.get(type(packet), [])):
            try:
                result = handler(packet)
                if inspect.isawaitable(result):
                    asyncio.create_task(_drive_async(result, _log))
            except Exception:
                _log.exception("handler raised on %s", type(packet).__name__)
        # waiters
        for entry in list(self._waiters):
            packet_type, predicate, fut = entry
            if isinstance(packet, packet_type):
                if predicate is not None and not predicate(packet):
                    continue
                if not fut.done():
                    fut.set_result(packet)


def offline_uuid(username: str) -> _uuid_stdlib.UUID:
    """Compute the standard offline-mode UUID for ``username``.

    The Notchian formula is ``MD5("OfflinePlayer:" + username)`` with
    UUID version-3 and variant bits forced. Matches the value the
    server derives when a client supplies no profile UUID.
    """
    raw = bytearray(hashlib.md5(("OfflinePlayer:" + username).encode("utf-8")).digest())
    raw[6] = (raw[6] & 0x0F) | 0x30  # version 3
    raw[8] = (raw[8] & 0x3F) | 0x80  # variant
    return _uuid_stdlib.UUID(bytes=bytes(raw))


async def _drive_async(coro: Awaitable[Any], log: logging.Logger) -> None:
    try:
        await coro
    except Exception:
        log.exception("async handler raised")


__all__ = [
    "Connection", "ReconnectPolicy", "Reconnected", "Subscription",
    "offline_uuid",
]
