#!/usr/bin/env python3
"""Cross-language byte-parity check.

For every test vector in ``protocol-data/v763/golden_bytes/primitives.json``,
encode with the Python implementation and assert the output matches the
golden hex. The Rust comparison (R-08) wires in once the Rust crate
ships its codecs (Phase 8); this Phase-2 scaffold validates Python
against the fixtures and is ready to extend.

Exit code 0 = all checks passed; 1 = at least one mismatch.

Usage::

    python tools/cross_check.py [--rust-bin <path>] [--python-only]
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid as _uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = REPO_ROOT / "protocol-data" / "v763" / "golden_bytes"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rust-bin", type=str, default=None)
    parser.add_argument("--python-only", action="store_true")
    args = parser.parse_args(argv)

    primitives_path = GOLDEN_DIR / "primitives.json"
    if not primitives_path.exists():
        print(f"FATAL: golden fixtures missing at {primitives_path}", file=sys.stderr)
        return 1

    sys.path.insert(0, str(REPO_ROOT / "python"))
    from minecraft_bot.codec import Reader, Writer  # noqa: E402
    from minecraft_bot.codec import (  # noqa: E402
        bitset, chat_component, identifier, nbt, position, slot, string,
        uuid as uuid_codec, varint, varlong,
    )

    fixtures = json.loads(primitives_path.read_text(encoding="utf-8"))

    failures: list[str] = []
    total = 0

    for codec_name, vectors in fixtures.items():
        for fx in vectors:
            total += 1
            expected = bytes.fromhex(fx["hex"])
            try:
                encoded = _encode_python(codec_name, fx, varint, varlong, string,
                                          uuid_codec, position, identifier, bitset,
                                          nbt, slot, chat_component, Writer)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{codec_name}: encode error on {fx!r}: {exc}")
                continue
            if encoded != expected:
                failures.append(
                    f"{codec_name}: encode mismatch — got {encoded.hex()}, "
                    f"expected {fx['hex']}, fixture={fx!r}"
                )
                continue
            try:
                decoded = _decode_python(codec_name, expected, varint, varlong, string,
                                          uuid_codec, position, identifier, bitset,
                                          nbt, slot, chat_component, Reader)
                _ = decoded  # round-trip is implicit; we just need no exception
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{codec_name}: decode error on {fx['hex']}: {exc}")

    if args.python_only or args.rust_bin is None:
        print(f"python-only: checked {total} fixtures, {len(failures)} failures")
    else:
        print(f"TODO Phase 8: invoke {args.rust_bin} for parity comparison")

    if failures:
        print("FAILURES:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1
    return 0


def _encode_python(codec_name: str, fx: dict, varint, varlong, string, uuid_codec,
                    position, identifier, bitset, nbt, slot, chat_component, Writer) -> bytes:
    """Dispatch to the right codec's write() given a fixture."""
    w = Writer()
    if codec_name == "varint":
        varint.write(fx["value"], w)
    elif codec_name == "varlong":
        varlong.write(fx["value"], w)
    elif codec_name == "string":
        string.write(fx["value"], w)
    elif codec_name == "uuid":
        uuid_codec.write(_uuid.UUID(fx["value"]), w)
    elif codec_name == "position":
        position.write(tuple(fx["value"]), w)
    elif codec_name == "identifier":
        identifier.write(fx["value"], w)
    elif codec_name == "bitset":
        bitset.write(set(fx["value"]), w)
    elif codec_name == "chat_component":
        chat_component.write(fx["value"], w)
    elif codec_name == "nbt" or codec_name == "slot":
        # These fixtures only carry hex (no value form); we re-encode by
        # decoding the hex first, then encoding. That's a lossless
        # round-trip iff our decode/encode are mutual inverses.
        from minecraft_bot.codec import Reader as _Reader
        if codec_name == "nbt":
            decoded = nbt.read(_Reader(bytes.fromhex(fx["hex"])))
            nbt.write(decoded, w)
        else:
            decoded = slot.read(_Reader(bytes.fromhex(fx["hex"])))
            slot.write(decoded, w)
    else:
        raise KeyError(f"unknown codec: {codec_name}")
    return w.bytes()


def _decode_python(codec_name: str, raw: bytes, varint, varlong, string, uuid_codec,
                    position, identifier, bitset, nbt, slot, chat_component, Reader):
    r = Reader(raw)
    if codec_name == "varint":
        return varint.read(r)
    if codec_name == "varlong":
        return varlong.read(r)
    if codec_name == "string":
        return string.read(r)
    if codec_name == "uuid":
        return uuid_codec.read(r)
    if codec_name == "position":
        return position.read(r)
    if codec_name == "identifier":
        return identifier.read(r)
    if codec_name == "bitset":
        return bitset.read(r)
    if codec_name == "chat_component":
        return chat_component.read(r)
    if codec_name == "nbt":
        return nbt.read(r)
    if codec_name == "slot":
        return slot.read(r)
    raise KeyError(f"unknown codec: {codec_name}")


if __name__ == "__main__":
    raise SystemExit(main())
