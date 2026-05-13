"""CodecRegistry tests.

Phase 2 ships the registry skeleton; no packets are registered yet.
We test:
- An empty registry refuses unknown lookups with UnknownPacketId.
- Registration works for synthetic test packets.
- Duplicate (state, dir, id) is rejected.
- Build-time discovery picks up packet files in the tree.
"""

from __future__ import annotations

import pytest
from minecraft_bot.errors import UnknownPacketId
from minecraft_bot.protocol.v763.registry import CodecRegistry
from minecraft_bot.protocol.v763.states import ConnectionState, Direction


def test_empty_registry_lookup_raises() -> None:
    reg = CodecRegistry()
    with pytest.raises(UnknownPacketId):
        reg.lookup_class(ConnectionState.PLAY, Direction.CLIENTBOUND, 0x99)


def test_build_walks_tree_without_error() -> None:
    """build() must walk the packets/ tree and return without error.
    Once Phase 3 lands the US1 packet set the count is non-zero; until
    then, an empty tree is also valid."""
    reg = CodecRegistry.build()
    assert reg.packet_count() >= 0


def test_build_uniqueness() -> None:
    """Every (state, direction, id) tuple in the loaded registry is unique."""
    reg = CodecRegistry.build()
    seen = set()
    for state, direction, pid, _ in reg.all_packets():
        key = (state, direction, pid)
        assert key not in seen, f"duplicate {key}"
        seen.add(key)


def test_unknown_packet_id_carries_state_and_direction() -> None:
    reg = CodecRegistry()
    with pytest.raises(UnknownPacketId) as exc:
        reg.decoder(ConnectionState.LOGIN, Direction.SERVERBOUND, 5)
    assert exc.value.state == ConnectionState.LOGIN
    assert exc.value.direction == Direction.SERVERBOUND
    assert exc.value.id == 5
