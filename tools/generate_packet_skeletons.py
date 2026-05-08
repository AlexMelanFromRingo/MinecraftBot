#!/usr/bin/env python3
"""One-shot codegen: per-packet stub files from ``packet_registry.json``.

This script is **not** invoked at build time. Run it once when bringing
up a new protocol version (or when extending coverage); after that, the
per-packet files are owned by humans (Constitution II — One Packet, One
File). It refuses to overwrite an existing file unless ``--force``.

Usage::

    python tools/generate_packet_skeletons.py \\
        --version v763 \\
        [--state {handshaking,status,login,play}] \\
        [--direction {clientbound,serverbound}] \\
        [--language {python,rust}] \\
        [--force] [--dry-run]

By default it processes all states and both directions for the
selected language.

Each generated stub looks like (Python)::

    \"\"\"Auto-generated packet stub for `<name>` ...\"\"\"
    from dataclasses import dataclass
    from minecraft_bot.codec import Reader, Writer

    PACKET_ID = 0x05

    @dataclass(frozen=True, slots=True)
    class <CamelName>:
        pass  # TODO: add fields per protocol spec

    def decode(reader: Reader) -> <CamelName>:
        raise NotImplementedError("TODO: implement decode")

    def encode(packet: <CamelName>, writer: Writer) -> None:
        raise NotImplementedError("TODO: implement encode")
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# minecraft-data direction strings:
_DIR_MD_TO_LABEL = {"toClient": "clientbound", "toServer": "serverbound"}


def snake_to_camel(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


def extract_packet_mapping(registry: dict, state: str, direction_md: str) -> dict[int, str]:
    """Pull ``{packet_id: packet_name}`` out of the protocol.json container."""
    state_data = registry.get(state, {})
    direction_data = state_data.get(direction_md)
    if not direction_data:
        return {}
    packet = direction_data["types"]["packet"]
    # packet is ["container", [{"name":"name","type":["mapper",{...}]}, ...]]
    container_fields = packet[1]
    name_field = container_fields[0]
    if name_field["name"] != "name":
        return {}
    mapper = name_field["type"]
    if mapper[0] != "mapper":
        return {}
    raw_mappings = mapper[1]["mappings"]
    return {int(hex_id, 16): name for hex_id, name in raw_mappings.items()}


PYTHON_TEMPLATE = '''"""Packet `{name}` ({state}/{direction}, id 0x{id:02x}).

Auto-generated stub by ``tools/generate_packet_skeletons.py``. Field
list and codec bodies are TODO; fill them in by hand from the
authoritative source (live-server probe > minecraft-data > minecraft.wiki).
"""

from __future__ import annotations

from dataclasses import dataclass

from minecraft_bot.codec import Reader, Writer

PACKET_ID = 0x{id:02x}


@dataclass(frozen=True, slots=True)
class {camel_name}:
    """TODO: add fields per protocol spec."""


def decode(reader: Reader) -> {camel_name}:
    raise NotImplementedError("TODO: decode {name}")


def encode(packet: {camel_name}, writer: Writer) -> None:
    raise NotImplementedError("TODO: encode {name}")
'''


RUST_TEMPLATE = '''//! Packet `{name}` ({state}/{direction}, id 0x{id:02x}).
//!
//! Auto-generated stub. Field list and codec bodies are TODO; fill them
//! in from the authoritative source (live-server probe > minecraft-data
//! > minecraft.wiki).

use crate::codec::{{Reader, Writer}};
use crate::errors::ProtocolError;

#[derive(Debug, Clone, PartialEq)]
pub struct {camel_name} {{
    // TODO: add fields per protocol spec.
}}

impl {camel_name} {{
    pub const PACKET_ID: i32 = 0x{id:02x};
}}

pub fn decode(_reader: &mut dyn Reader) -> Result<{camel_name}, ProtocolError> {{
    Err(ProtocolError::DecodeError("TODO: decode {name}".into()))
}}

pub fn encode(_packet: &{camel_name}, _writer: &mut dyn Writer) -> Result<(), ProtocolError> {{
    Err(ProtocolError::EncodeError("TODO: encode {name}".into()))
}}
'''


def python_path(version: str, state: str, direction: str, name: str) -> Path:
    return REPO_ROOT / "python" / "minecraft_bot" / "protocol" / version / "packets" / state / direction / f"{name}.py"


def rust_path(version: str, state: str, direction: str, name: str) -> Path:
    return REPO_ROOT / "rust" / "src" / "protocol" / version / "packets" / state / direction / f"{name}.rs"


def render_python(state: str, direction: str, packet_id: int, name: str) -> str:
    return PYTHON_TEMPLATE.format(
        name=name, state=state, direction=direction, id=packet_id,
        camel_name=snake_to_camel(name),
    )


def render_rust(state: str, direction: str, packet_id: int, name: str) -> str:
    return RUST_TEMPLATE.format(
        name=name, state=state, direction=direction, id=packet_id,
        camel_name=snake_to_camel(name),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="v763")
    parser.add_argument(
        "--state", choices=["handshaking", "status", "login", "play"], default=None,
        help="Limit to one state (default: all)",
    )
    parser.add_argument(
        "--direction", choices=["clientbound", "serverbound"], default=None,
        help="Limit to one direction (default: both)",
    )
    parser.add_argument("--language", choices=["python", "rust"], default="python")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing files")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    registry_path = REPO_ROOT / "protocol-data" / args.version / "packet_registry.json"
    if not registry_path.exists():
        print(f"FATAL: registry snapshot not found at {registry_path}", file=sys.stderr)
        return 2
    registry = json.loads(registry_path.read_text(encoding="utf-8"))

    states = [args.state] if args.state else ["handshaking", "status", "login", "play"]
    directions = (
        [args.direction] if args.direction else ["clientbound", "serverbound"]
    )

    written = 0
    skipped_existing = 0
    skipped_empty = 0
    for state in states:
        for direction in directions:
            md_dir = "toClient" if direction == "clientbound" else "toServer"
            mapping = extract_packet_mapping(registry, state, md_dir)
            if not mapping:
                skipped_empty += 1
                continue
            for pid, name in sorted(mapping.items()):
                if args.language == "python":
                    target = python_path(args.version, state, direction, name)
                    body = render_python(state, direction, pid, name)
                else:
                    target = rust_path(args.version, state, direction, name)
                    body = render_rust(state, direction, pid, name)

                if target.exists() and not args.force:
                    skipped_existing += 1
                    continue
                if args.dry_run:
                    print(f"[dry-run] would write {target.relative_to(REPO_ROOT)}")
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body, encoding="utf-8")
                written += 1

    summary = (
        f"{args.language} codegen: wrote {written}, "
        f"skipped {skipped_existing} (existing), "
        f"{skipped_empty} empty (state,direction) groups"
    )
    if args.dry_run:
        summary = "[dry-run] " + summary
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
