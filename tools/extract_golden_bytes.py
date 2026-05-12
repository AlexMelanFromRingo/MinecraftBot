#!/usr/bin/env python3
"""Extract per-packet golden-bytes from a captured ``.jsonl`` (T085/T098).

For each unique packet name in the WireLog, write the FIRST observed
raw payload to::

    protocol-data/v763/golden_bytes/packets/{direction}/{name}.json

Each output file is a JSON array of representative payloads. New
captures append additional samples (if they differ).

Usage::

    PYTHONPATH=python python tools/extract_golden_bytes.py \\
        --input protocol-data/v763/live_captures/us2_baseline.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_BASE = REPO / "protocol-data" / "v763" / "golden_bytes" / "packets"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--limit-per-packet", type=int, default=3,
                   help="Max payloads stored per packet name (default 3).")
    args = p.parse_args(argv)

    if not args.input.exists():
        print(f"FATAL: {args.input} not found", file=sys.stderr)
        return 1

    seen: dict[tuple[str, str], list[str]] = {}
    n_lines = 0
    with args.input.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if "meta" in obj:
                continue
            n_lines += 1
            name = obj.get("name")
            direction = obj.get("dir")
            raw = obj.get("raw")
            if name is None or direction is None or raw is None:
                continue
            dir_label = "clientbound" if direction == "rx" else "serverbound"
            key = (dir_label, name)
            payloads = seen.setdefault(key, [])
            if raw not in payloads and len(payloads) < args.limit_per_packet:
                payloads.append(raw)

    written = 0
    for (dir_label, name), payloads in sorted(seen.items()):
        out_path = OUT_BASE / dir_label / f"{name}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Merge with existing payloads if present.
        existing: list[str] = []
        if out_path.exists():
            try:
                existing = json.loads(out_path.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        merged = list(dict.fromkeys(existing + payloads))[:args.limit_per_packet]
        out_path.write_text(
            json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written += 1

    print(f"processed {n_lines} entries, wrote {written} per-packet fixture files "
          f"under {OUT_BASE.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
