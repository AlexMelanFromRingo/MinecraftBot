#!/usr/bin/env python3
"""Capture a full WireLog from a live Paper session and write it to a
``.jsonl`` file under ``protocol-data/v763/live_captures/`` (or wherever
``--out`` points).

Used to produce the golden-byte fixtures that drive cross-language byte
parity (R-08) and to harvest realistic test data for round-trip tests.

Usage::

    python tools/capture_session.py \\
        --host 172.26.160.1 --port 25565 --username CaptureBot \\
        --duration 60 \\
        --out protocol-data/v763/live_captures/baseline.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "python"))


async def _capture(
    host: str, port: int, username: str, duration: float, out_path: Path,
) -> int:
    from minecraft_bot.connection import Connection
    from minecraft_bot.wire_log import WireLog

    out_path.parent.mkdir(parents=True, exist_ok=True)
    log = WireLog.to_jsonl(out_path)
    bot = Connection.offline(host=host, port=port, username=username, wire_log=log)
    try:
        await bot.connect()
        print(f"connected as {username}, state={bot.state.name}, "
              f"entity_id={bot.entity_id}, world={bot.world_name}", file=sys.stderr)
        await asyncio.sleep(duration)
    finally:
        await bot.disconnect()
        try:
            log.sink.close()  # type: ignore[union-attr]
        except AttributeError:
            pass

    print(f"wrote capture to {out_path}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="172.26.160.1")
    parser.add_argument("--port", type=int, default=25565)
    parser.add_argument("--username", default="CaptureBot")
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--out", required=True, type=str)
    args = parser.parse_args(argv)

    return asyncio.run(_capture(
        host=args.host, port=args.port, username=args.username,
        duration=args.duration, out_path=Path(args.out),
    ))


if __name__ == "__main__":
    raise SystemExit(main())
