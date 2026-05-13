"""Round-trip tests for the 23 US1 packets (handshake, status, login, play subset).

For every packet under ``protocol/v763/packets/`` reachable in the
US1 flow, construct a sample value, encode then decode, and assert
equality. This is the per-packet form of FR-013.
"""

from __future__ import annotations

import uuid as _uuid

import pytest
from minecraft_bot.codec import Reader, Writer, nbt
from minecraft_bot.errors import ValueOutOfRange
from minecraft_bot.protocol.v763.packets.handshaking.serverbound import (
    legacy_server_list_ping as h_legacy,
)
from minecraft_bot.protocol.v763.packets.handshaking.serverbound import set_protocol
from minecraft_bot.protocol.v763.packets.login.clientbound import compress as l_compress
from minecraft_bot.protocol.v763.packets.login.clientbound import (
    disconnect as l_disconnect,
)
from minecraft_bot.protocol.v763.packets.login.clientbound import (
    encryption_begin as l_enc_cb,
)
from minecraft_bot.protocol.v763.packets.login.clientbound import (
    login_plugin_request,
    success,
)
from minecraft_bot.protocol.v763.packets.login.serverbound import (
    encryption_begin as l_enc_sb,
)
from minecraft_bot.protocol.v763.packets.login.serverbound import (
    login_plugin_response,
    login_start,
)
from minecraft_bot.protocol.v763.packets.play.clientbound import (
    custom_payload as p_cb_cp,
)
from minecraft_bot.protocol.v763.packets.play.clientbound import keep_alive as p_cb_ka
from minecraft_bot.protocol.v763.packets.play.clientbound import (
    kick_disconnect as p_cb_kd,
)
from minecraft_bot.protocol.v763.packets.play.clientbound import login as p_cb_login
from minecraft_bot.protocol.v763.packets.play.clientbound import position as p_cb_pos
from minecraft_bot.protocol.v763.packets.play.serverbound import (
    custom_payload as p_sb_cp,
)
from minecraft_bot.protocol.v763.packets.play.serverbound import keep_alive as p_sb_ka
from minecraft_bot.protocol.v763.packets.play.serverbound import settings as p_sb_set
from minecraft_bot.protocol.v763.packets.play.serverbound import (
    teleport_confirm as p_sb_tc,
)
from minecraft_bot.protocol.v763.packets.status.clientbound import (
    ping as s_cb_ping,
)
from minecraft_bot.protocol.v763.packets.status.clientbound import (
    server_info,
)
from minecraft_bot.protocol.v763.packets.status.serverbound import ping as s_sb_ping
from minecraft_bot.protocol.v763.packets.status.serverbound import ping_start


def round_trip(module, value) -> None:
    w = Writer()
    module.encode(value, w)
    r = Reader(w.bytes())
    decoded = module.decode(r)
    assert decoded == value, f"round-trip mismatch for {type(value).__name__}"
    assert r.remaining() == 0, "decoder didn't consume all bytes"


# --- handshaking ----------------------------------------------------------


def test_set_protocol() -> None:
    round_trip(set_protocol, set_protocol.SetProtocol(
        protocol_version=763, server_host="172.26.160.1",
        server_port=25565, next_state=2,
    ))


def test_legacy_server_list_ping() -> None:
    round_trip(h_legacy, h_legacy.LegacyServerListPing(payload=b"\x01"))


# --- status ---------------------------------------------------------------


def test_server_info() -> None:
    round_trip(server_info, server_info.ServerInfo(response='{"version":{"name":"1.20.1","protocol":763}}'))


def test_clientbound_ping() -> None:
    round_trip(s_cb_ping, s_cb_ping.Ping(time=1714867200000))


def test_serverbound_ping_start() -> None:
    round_trip(ping_start, ping_start.PingStart())


def test_serverbound_ping() -> None:
    round_trip(s_sb_ping, s_sb_ping.Ping(time=1714867200000))


# --- login ----------------------------------------------------------------


def test_login_disconnect() -> None:
    round_trip(l_disconnect, l_disconnect.Disconnect(reason='{"text":"go away"}'))


def test_clientbound_encryption_begin() -> None:
    round_trip(l_enc_cb, l_enc_cb.EncryptionBegin(
        server_id="server", public_key=b"\x30\x82\x00", verify_token=b"\x01\x02\x03\x04",
    ))


def test_success_no_properties() -> None:
    round_trip(success, success.Success(
        uuid=_uuid.UUID("11111111-2222-3333-4444-555555555555"),
        username="Bot", properties=(),
    ))


def test_success_with_signed_property() -> None:
    prop = success.Property(name="textures", value="base64", signature="sig")
    round_trip(success, success.Success(
        uuid=_uuid.UUID("11111111-2222-3333-4444-555555555555"),
        username="Bot", properties=(prop,),
    ))


def test_success_with_unsigned_property() -> None:
    prop = success.Property(name="textures", value="base64", signature=None)
    round_trip(success, success.Success(
        uuid=_uuid.UUID("11111111-2222-3333-4444-555555555555"),
        username="Bot", properties=(prop,),
    ))


def test_compress() -> None:
    round_trip(l_compress, l_compress.Compress(threshold=256))
    round_trip(l_compress, l_compress.Compress(threshold=-1))
    round_trip(l_compress, l_compress.Compress(threshold=0))


def test_login_plugin_request() -> None:
    round_trip(login_plugin_request, login_plugin_request.LoginPluginRequest(
        message_id=42, channel="forge:handshake", data=b"\xde\xad\xbe\xef",
    ))


def test_login_start_with_uuid() -> None:
    round_trip(login_start, login_start.LoginStart(
        username="Bot", player_uuid=_uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
    ))


def test_login_start_no_uuid() -> None:
    round_trip(login_start, login_start.LoginStart(username="Anon", player_uuid=None))


def test_serverbound_encryption_begin() -> None:
    round_trip(l_enc_sb, l_enc_sb.EncryptionBegin(
        shared_secret=b"\xab" * 16, verify_token=b"\xcd" * 4,
    ))


def test_login_plugin_response_with_data() -> None:
    round_trip(login_plugin_response, login_plugin_response.LoginPluginResponse(
        message_id=42, data=b"\x01\x02\x03",
    ))


def test_login_plugin_response_no_data() -> None:
    round_trip(login_plugin_response, login_plugin_response.LoginPluginResponse(
        message_id=42, data=None,
    ))


# --- play -----------------------------------------------------------------


def test_clientbound_keep_alive() -> None:
    round_trip(p_cb_ka, p_cb_ka.KeepAlive(keep_alive_id=1234567890))


def test_serverbound_keep_alive() -> None:
    round_trip(p_sb_ka, p_sb_ka.KeepAlive(keep_alive_id=1234567890))


def test_position() -> None:
    round_trip(p_cb_pos, p_cb_pos.Position(
        x=0.5, y=64.0, z=-12.5, yaw=180.0, pitch=0.0, flags=0, teleport_id=1,
    ))


def test_teleport_confirm() -> None:
    round_trip(p_sb_tc, p_sb_tc.TeleportConfirm(teleport_id=42))


def test_kick_disconnect() -> None:
    round_trip(p_cb_kd, p_cb_kd.KickDisconnect(reason='{"text":"banned"}'))


def test_clientbound_custom_payload() -> None:
    round_trip(p_cb_cp, p_cb_cp.CustomPayload(channel="minecraft:brand", data=b"vanilla"))


def test_serverbound_custom_payload() -> None:
    round_trip(p_sb_cp, p_sb_cp.CustomPayload(channel="minecraft:brand", data=b"minecraft_bot"))


def test_settings_default() -> None:
    round_trip(p_sb_set, p_sb_set.Settings(
        locale="en_us", view_distance=10, chat_flags=0, chat_colors=True,
        skin_parts=0x7F, main_hand=1,
        enable_text_filtering=False, enable_server_listing=True,
    ))


def test_settings_invalid_skin_parts() -> None:
    with pytest.raises(ValueOutOfRange):
        Writer()
        s = p_sb_set.Settings(
            locale="en", view_distance=10, chat_flags=0, chat_colors=True,
            skin_parts=999, main_hand=1,
            enable_text_filtering=False, enable_server_listing=True,
        )
        w = Writer(); p_sb_set.encode(s, w)


def test_login_play_minimal() -> None:
    round_trip(p_cb_login, p_cb_login.Login(
        entity_id=42, is_hardcore=False, game_mode=0, previous_game_mode=-1,
        world_names=("minecraft:overworld",),
        dimension_codec=nbt.NbtCompound(items=(("simple", nbt.NbtByte(1)),)),
        world_type="minecraft:overworld", world_name="minecraft:overworld",
        hashed_seed=0, max_players=20, view_distance=10,
        simulation_distance=10, reduced_debug_info=False,
        enable_respawn_screen=True, is_debug=False, is_flat=False,
        death=None, portal_cooldown=0,
    ))


def test_login_play_with_death() -> None:
    round_trip(p_cb_login, p_cb_login.Login(
        entity_id=99, is_hardcore=True, game_mode=1, previous_game_mode=0,
        world_names=("minecraft:overworld", "minecraft:the_nether"),
        dimension_codec=None,
        world_type="minecraft:the_nether", world_name="minecraft:the_nether",
        hashed_seed=12345, max_players=10, view_distance=8,
        simulation_distance=6, reduced_debug_info=True,
        enable_respawn_screen=False, is_debug=False, is_flat=True,
        death=p_cb_login.DeathLocation(
            dimension_name="minecraft:overworld", location=(100, 64, -50),
        ),
        portal_cooldown=0,
    ))
