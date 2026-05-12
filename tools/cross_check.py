#!/usr/bin/env python3
"""Cross-language byte-parity check (R-08).

For every test vector in ``protocol-data/v763/golden_bytes/primitives.json``,
encode with both Python and (optionally) Rust and assert the bytes match.

Usage::

    python tools/cross_check.py
    python tools/cross_check.py --rust-bin rust/target/release/examples/encode_one
    python tools/cross_check.py --python-only

When ``--rust-bin`` is omitted, it auto-discovers
``rust/target/release/examples/encode_one`` if it exists.

Exit code 0 = all checks passed; 1 = at least one mismatch.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid as _uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = REPO_ROOT / "protocol-data" / "v763" / "golden_bytes"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rust-bin", type=str, default=None,
                        help="Path to the Rust `encode_one` example binary")
    parser.add_argument("--python-only", action="store_true",
                        help="Skip Rust comparison")
    parser.add_argument(
        "--accel", action="store_true",
        help="Include the minecraft_bot_accel PyO3 façade as a third "
             "encoder (T067). Requires `pip install -e python-ext` / "
             "`maturin develop`.",
    )
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

    # Python encode pass.
    python_failures: list[str] = []
    py_total = 0
    for codec_name, vectors in fixtures.items():
        for fx in vectors:
            py_total += 1
            expected = bytes.fromhex(fx["hex"])
            try:
                encoded = _encode_python(codec_name, fx, varint, varlong, string,
                                          uuid_codec, position, identifier, bitset,
                                          nbt, slot, chat_component, Writer, Reader)
            except Exception as exc:  # noqa: BLE001
                python_failures.append(f"{codec_name}: encode error on {fx!r}: {exc}")
                continue
            if encoded != expected:
                python_failures.append(
                    f"{codec_name}: encode mismatch — got {encoded.hex()}, "
                    f"expected {fx['hex']}, fixture={fx!r}"
                )

    print(f"Python: {py_total} fixtures, {len(python_failures)} failures")
    if python_failures:
        for f in python_failures:
            print(f"  PY: {f}", file=sys.stderr)

    # Rust comparison.
    rust_bin = args.rust_bin
    if not args.python_only and rust_bin is None:
        candidate = REPO_ROOT / "rust" / "target" / "release" / "examples" / "encode_one"
        if candidate.exists():
            rust_bin = str(candidate)

    rust_failures: list[str] = []
    rust_total = 0
    if not args.python_only and rust_bin is not None:
        for codec_name, vectors in fixtures.items():
            for fx in vectors:
                rust_total += 1
                req = {"codec": codec_name}
                if codec_name in ("nbt", "slot"):
                    req["hex"] = fx["hex"]
                else:
                    req["value"] = fx["value"]
                try:
                    out = subprocess.run(
                        [rust_bin, json.dumps(req)],
                        check=True, capture_output=True, text=True, timeout=10,
                    )
                    rust_hex = out.stdout.strip()
                except subprocess.CalledProcessError as exc:
                    rust_failures.append(
                        f"{codec_name}: rust crashed — stderr: {exc.stderr.strip()}"
                    )
                    continue
                if rust_hex != fx["hex"]:
                    rust_failures.append(
                        f"{codec_name}: rust mismatch — got {rust_hex}, "
                        f"expected {fx['hex']}, fixture={fx!r}"
                    )
        print(f"Rust:   {rust_total} fixtures, {len(rust_failures)} failures (bin: {rust_bin})")
    elif args.python_only:
        print("Rust:   skipped (--python-only)")
    else:
        print("Rust:   skipped (no --rust-bin and no auto-discovered binary)")

    if rust_failures:
        for f in rust_failures:
            print(f"  RS: {f}", file=sys.stderr)

    # T067 — third encoder: minecraft_bot_accel.
    accel_failures: list[str] = []
    accel_total = 0
    if args.accel:
        try:
            import minecraft_bot_accel as mb_accel  # type: ignore[import-not-found]
            mb_ac_codec = mb_accel.codec
        except ImportError as exc:
            print(f"Accel:  SKIPPED — minecraft_bot_accel not importable: {exc}")
        else:
            for codec_name, vectors in fixtures.items():
                # Currently the accel façade exposes varint + varlong; other
                # codecs are forwarded to the underlying Rust crate via the
                # standalone Rust cross-check, so we only cross-check the
                # subset accel directly exports.
                if codec_name not in ("varint", "varlong"):
                    continue
                ac_codec_mod = getattr(mb_ac_codec, codec_name)
                for fx in vectors:
                    accel_total += 1
                    expected = bytes.fromhex(fx["hex"])
                    try:
                        w = mb_ac_codec.Writer()
                        ac_codec_mod.write(fx["value"], w)
                        encoded = w.bytes()
                    except Exception as exc:  # noqa: BLE001
                        accel_failures.append(
                            f"{codec_name}: accel encode error on {fx!r}: {exc}"
                        )
                        continue
                    if encoded != expected:
                        accel_failures.append(
                            f"{codec_name}: accel mismatch — got {encoded.hex()}, "
                            f"expected {fx['hex']}, fixture={fx!r}"
                        )
            print(f"Accel:  {accel_total} fixtures, {len(accel_failures)} failures")
            if accel_failures:
                for f in accel_failures:
                    print(f"  AC: {f}", file=sys.stderr)
    elif args.python_only:
        pass
    else:
        print("Accel:  skipped (pass --accel to enable)")

    return 1 if (python_failures or rust_failures or accel_failures) else 0


def _encode_python(codec_name, fx, varint, varlong, string, uuid_codec,
                    position, identifier, bitset, nbt, slot, chat_component, Writer, Reader):
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
    elif codec_name == "nbt":
        decoded = nbt.read(Reader(bytes.fromhex(fx["hex"])))
        nbt.write(decoded, w)
    elif codec_name == "slot":
        decoded = slot.read(Reader(bytes.fromhex(fx["hex"])))
        slot.write(decoded, w)
    else:
        raise KeyError(f"unknown codec: {codec_name}")
    return w.bytes()


if __name__ == "__main__":
    raise SystemExit(main())
