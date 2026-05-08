#!/usr/bin/env python3
"""Capture a full WireLog from a live Paper session and write it to a
``.jsonl`` file under ``protocol-data/v763/live_captures/``.

Used to produce the golden-byte fixtures that drive cross-language byte
parity (R-08) and to harvest realistic test data for round-trip tests.

Usage::

    python tools/capture_session.py \\
        --host 172.26.160.1 --port 25565 --username CaptureBot \\
        --duration 60 \\
        --out protocol-data/v763/live_captures/baseline.jsonl

Real implementation lands once Connection lifecycle (Phase 3 / T058) is
in place. For Phase 2 this is a stub — it just exits with a TODO.
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="172.26.160.1")
    parser.add_argument("--port", type=int, default=25565)
    parser.add_argument("--username", default="CaptureBot")
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--out", required=True, type=str)
    parser.parse_args(argv)

    print(
        "TODO: T084 / T098 — connect via Connection.offline(...) with a "
        "WireLog.to_jsonl(out) sink, sleep(duration), disconnect. Requires "
        "Phase 3 Connection class.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
