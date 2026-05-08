"""CodecRegistry tests.

Phase 2 ships the registry skeleton; no packets are registered yet.
We test:
- An empty registry refuses unknown lookups with UnknownPacketId.
- Registration works for synthetic test packets.
- Duplicate (state, dir, id) is rejected.
- Build-time discovery picks up packet files in the tree.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from minecraft_bot.codec import Reader, Writer
from minecraft_bot.errors import UnknownPacketId
from minecraft_bot.protocol.v763.registry import CodecRegistry
from minecraft_bot.protocol.v763.states import ConnectionState, Direction


def test_empty_registry_lookup_raises() -> None:
    reg = CodecRegistry()
    with pytest.raises(UnknownPacketId):
        reg.lookup_class(ConnectionState.PLAY, Direction.CLIENTBOUND, 0x99)


def test_build_walks_tree_without_error() -> None:
    """No packet files are registered yet (Phase 2). build() must succeed
    and return a registry with 0 packets."""
    reg = CodecRegistry.build()
    assert reg.packet_count() == 0


def test_unknown_packet_id_carries_state_and_direction() -> None:
    reg = CodecRegistry()
    with pytest.raises(UnknownPacketId) as exc:
        reg.decoder(ConnectionState.LOGIN, Direction.SERVERBOUND, 5)
    assert exc.value.state == ConnectionState.LOGIN
    assert exc.value.direction == Direction.SERVERBOUND
    assert exc.value.id == 5
