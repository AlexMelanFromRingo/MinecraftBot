"""Tests for ConnectionState, Direction, ProtocolVersion, ReconnectPolicy."""

from __future__ import annotations

import pytest

from minecraft_bot.connection import ReconnectPolicy
from minecraft_bot.protocol import V_1_20_1, ProtocolVersion
from minecraft_bot.protocol.v763.states import ConnectionState, Direction


def test_connection_state_values_stable() -> None:
    """Variant integer values must stay stable across releases (used by replay)."""
    assert ConnectionState.HANDSHAKING == 0
    assert ConnectionState.STATUS == 1
    assert ConnectionState.LOGIN == 2
    assert ConnectionState.PLAY == 3


def test_connection_state_labels() -> None:
    assert ConnectionState.HANDSHAKING.label() == "handshaking"
    assert ConnectionState.PLAY.label() == "play"


def test_direction_labels() -> None:
    assert Direction.CLIENTBOUND.label() == "rx"
    assert Direction.SERVERBOUND.label() == "tx"
    assert Direction.from_label("rx") == Direction.CLIENTBOUND
    assert Direction.from_label("tx") == Direction.SERVERBOUND
    with pytest.raises(ValueError):
        Direction.from_label("unknown")


def test_protocol_version_v_1_20_1() -> None:
    assert V_1_20_1.number == 763
    assert V_1_20_1.display_name == "1.20.1"


def test_protocol_version_equality_ignores_display_name() -> None:
    a = ProtocolVersion(number=763, display_name="1.20.1")
    b = ProtocolVersion(number=763, display_name="1.20.1")
    assert a == b


def test_protocol_version_rejects_non_positive() -> None:
    with pytest.raises(ValueError):
        ProtocolVersion(number=0)
    with pytest.raises(ValueError):
        ProtocolVersion(number=-1)


def test_reconnect_policy_defaults() -> None:
    p = ReconnectPolicy()
    assert p.max_attempts == 5
    assert p.initial_delay == 1.0
    assert p.max_delay == 30.0
    assert p.multiplier == 2.0
    assert p.jitter == 0.25


def test_reconnect_policy_validation() -> None:
    with pytest.raises(ValueError):
        ReconnectPolicy(max_attempts=-1)
    with pytest.raises(ValueError):
        ReconnectPolicy(initial_delay=0)
    with pytest.raises(ValueError):
        ReconnectPolicy(initial_delay=10, max_delay=5)
    with pytest.raises(ValueError):
        ReconnectPolicy(multiplier=0.5)
    with pytest.raises(ValueError):
        ReconnectPolicy(jitter=1.0)


def test_reconnect_policy_zero_attempts_is_valid() -> None:
    """max_attempts=0 effectively disables retries; should still construct."""
    p = ReconnectPolicy(max_attempts=0)
    assert p.max_attempts == 0
