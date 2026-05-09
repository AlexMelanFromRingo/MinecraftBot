"""US2 — Decode every clientbound packet (live).

Spec acceptance:
- During a 60-second offline-mode session against the configured Paper
  server, 100% of received packets decode into typed values.
- Zero UnknownPacketId log entries.
- ≥ 25 distinct packet types observed.

Requires the live server fixture.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter

import pytest

from minecraft_bot.connection import Connection
from minecraft_bot.wire_log import WireLog

pytestmark = pytest.mark.live


class _UnknownIdCatcher(logging.Handler):
    """Captures decode-loop "unknown play clientbound id" debug logs."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.unknown: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if "unknown play clientbound id" in msg or "UnknownPacketId" in msg:
            self.unknown.append(msg)


async def test_decode_coverage(live_server) -> None:
    """60-second session; every received packet decoded; no unknown ids."""
    catcher = _UnknownIdCatcher()
    proto_logger = logging.getLogger("minecraft_bot.protocol")
    prev_level = proto_logger.level
    proto_logger.setLevel(logging.DEBUG)
    proto_logger.addHandler(catcher)

    log = WireLog.in_memory(capacity=10000)
    bot = Connection.offline(
        host=live_server.host, port=live_server.port,
        username="ITDecode", wire_log=log,
    )
    try:
        await bot.connect()
        await asyncio.sleep(60)
    finally:
        await bot.disconnect()
        proto_logger.removeHandler(catcher)
        proto_logger.setLevel(prev_level)

    rx_entries = [e for e in log.entries() if e.direction.label() == "rx"]
    distinct_types = Counter(e.name for e in rx_entries if e.name is not None)

    print(f"\n>> received {len(rx_entries)} packets across {len(distinct_types)} distinct types")
    print(">> top types:", ", ".join(f"{n}:{c}" for n, c in distinct_types.most_common(10)))

    if catcher.unknown:
        print(">> UNKNOWN PACKET LOG ENTRIES:")
        for u in catcher.unknown:
            print(f"   {u}")

    assert len(rx_entries) > 0, "no clientbound packets received"
    assert len(distinct_types) >= 25, (
        f"only {len(distinct_types)} distinct packet types observed; "
        f"expected >= 25 for a populated server"
    )
    assert not catcher.unknown, (
        f"{len(catcher.unknown)} 'unknown packet id' log entries observed; "
        f"first: {catcher.unknown[0]}"
    )
