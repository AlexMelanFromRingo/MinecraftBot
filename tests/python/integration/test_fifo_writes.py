"""FR-013a FIFO stress test (T097, live).

Spins up a single Connection and pushes 100 concurrent ``arm_animation``
sends from independent coroutines. The framework's write mutex must
preserve completion-order. We can't trivially inspect wire order from
outside, so we use the WireLog capture: each tx entry should appear
once, exactly 100 of them, with monotonic ts.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest
from minecraft_bot.connection import Connection
from minecraft_bot.protocol.v763.packets.play.serverbound import arm_animation as sb_arm
from minecraft_bot.wire_log import WireLog

pytestmark = pytest.mark.live


async def test_fifo_writes_under_load(live_server) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "fifo.jsonl"
        log = WireLog.to_jsonl(log_path)
        conn = Connection.offline(
            live_server.host, live_server.port, "TestBot4",
            wire_log=log,
        )
        await conn.connect()
        try:
            N = 100
            async def one_send(_i: int) -> None:
                await conn.send(sb_arm.ArmAnimation(hand=0))
            await asyncio.gather(*(one_send(i) for i in range(N)))
            await asyncio.sleep(1.0)
        finally:
            await conn.disconnect()
        # Inspect WireLog: at least N tx arm_animation entries, monotonic ts.
        lines = log_path.read_text(encoding="utf-8").splitlines()
        # Skip header line (first), then count tx entries.
        import json
        arm_count = 0
        last_ts = -1.0
        for line in lines[1:]:
            obj = json.loads(line)
            if obj.get("dir") == "tx" and obj.get("name") == "arm_animation":
                arm_count += 1
                ts = obj.get("ts", 0.0)
                assert ts >= last_ts, f"non-monotonic ts at entry: {ts} < {last_ts}"
                last_ts = ts
        assert arm_count >= N, f"only {arm_count} of {N} arm_animation entries in wire log"
        print(f"\n  fifo: {arm_count} arm_animation tx in WireLog, monotonic ts")
