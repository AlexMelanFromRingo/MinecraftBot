"""SC-009: decode-and-dispatch latency budget verification.

Spec target: median ≤ 5 ms, p99 ≤ 25 ms on commodity hardware (Ryzen 5
/ Core i5 class) for the bytes-on-wire → typed-value-handed-to-developer
path.

This test uses ``pytest-benchmark`` to time a representative
high-frequency packet (entity_head_rotation, the most common
clientbound packet by volume in our captures). The "decode-and-dispatch"
path here is: VarInt for packet id, registry lookup, decoder call.

Skipped if ``pytest-benchmark`` is not installed.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skipif(
    not pytest.importorskip("pytest_benchmark", reason="needs pytest-benchmark")
    is not None,
    reason="needs pytest-benchmark",
)


def _decode_one_packet(reader_cls, varint_mod, registry, raw):
    """Inlined dispatch: VarInt id read + registry lookup + decode."""
    r = reader_cls(raw)
    pid = varint_mod.read(r)
    decoder = registry.decoder(_PLAY, _CB, pid)
    payload = raw[r.position() :]
    return decoder(reader_cls(payload))


# Module-level imports kept lazy so the top-level pytestmark can decide.
from minecraft_bot.codec import (
    Reader as _Reader,
)
from minecraft_bot.codec import (
    Writer as _Writer,
)
from minecraft_bot.codec import (
    varint as _varint,
)
from minecraft_bot.protocol.v763.packets.play.clientbound import (
    entity_head_rotation as _ehr,
)
from minecraft_bot.protocol.v763.registry import CodecRegistry
from minecraft_bot.protocol.v763.states import (
    ConnectionState as _PLAY_S,
)
from minecraft_bot.protocol.v763.states import (
    Direction as _DIR,
)

_PLAY = _PLAY_S.PLAY
_CB = _DIR.CLIENTBOUND


def _build_payload() -> bytes:
    """Encode an entity_head_rotation packet body (id varint + payload)."""
    pkt = _ehr.EntityHeadRotation(entity_id=42, head_yaw=64)
    body = _Writer()
    _varint.write(_ehr.PACKET_ID, body)
    _ehr.encode(pkt, body)
    return body.bytes()


def test_decode_latency_under_budget(benchmark) -> None:
    """Median decode-and-dispatch on a hot packet must be < 5 ms."""
    registry = CodecRegistry.build()
    raw = _build_payload()

    def runner() -> object:
        return _decode_one_packet(_Reader, _varint, registry, raw)

    result = benchmark(runner)
    # Sanity: the runner returned a typed packet.
    assert isinstance(result, _ehr.EntityHeadRotation)
    # pytest-benchmark stats live on benchmark.stats; assert median.
    median_us = benchmark.stats.stats.median * 1_000_000
    p99_us = benchmark.stats.stats.max * 1_000_000  # max is conservative-p99
    print(
        f"\n>> decode entity_head_rotation: median={median_us:.1f}us, max={p99_us:.1f}us"
    )
    assert (
        benchmark.stats.stats.median < 0.005
    ), f"median {benchmark.stats.stats.median*1000:.2f}ms exceeds 5ms budget"
