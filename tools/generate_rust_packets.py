#!/usr/bin/env python3
"""Generate Rust packet modules from the Python source-of-truth.

For each Python packet at
``python/minecraft_bot/protocol/v763/packets/{state}/{direction}/{name}.py``
this tool emits a Rust file at the mirrored path
``rust/src/protocol/v763/packets/{state}/{direction}/{name}.rs`` with:

- a struct matching the Python dataclass fields,
- ``decode(reader) -> Result<Self>`` replaying the codec sequence,
- ``impl Clientbound/Serverbound Packet`` with ``encode`` doing the
  reverse.

The Python files follow a tight convention — we parse the AST and
replay the decode body call-by-call. Unsupported patterns leave a
``// TODO`` marker the generator counts; hand-port these.

Usage::

    PYTHONPATH=python python tools/generate_rust_packets.py
    PYTHONPATH=python python tools/generate_rust_packets.py --state play --dir clientbound
    PYTHONPATH=python python tools/generate_rust_packets.py --packet keep_alive
"""

from __future__ import annotations

import argparse
import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
PY_BASE = REPO / "python" / "minecraft_bot" / "protocol" / "v763" / "packets"
RS_BASE = REPO / "rust" / "src" / "protocol" / "v763" / "packets"


# --- Type mapping --------------------------------------------------------


@dataclass
class CodecCall:
    """One serialised value: codec name + Rust type."""

    codec: str          # the rust codec module path or struct literal
    rust_type: str      # e.g. "i32"
    field_name: str     # destination field
    extra_args: str = ""  # extra args to read() (e.g. max_length)


# Simple codec → (read_expr_template, write_expr_template, rust_type) map.
# Templates use $field and $writer placeholders. Read templates produce a
# single Rust expression that may use the ? operator.
_CODECS: dict[str, tuple[str, str, str]] = {
    "varint": ("varint::read(reader)?", "varint::write(self.$field, writer)?;", "i32"),
    "varlong": ("varlong::read(reader)?", "varlong::write(self.$field, writer)?;", "i64"),
    "string": ("string::read(reader)?", "string::write(&self.$field, writer)?;", "String"),
    "uuid": ("uuid_c::read(reader)?", "uuid_c::write(&self.$field, writer)?;", "Uuid"),
    "identifier": ("identifier::read(reader)?", "identifier::write(&self.$field, writer)?;", "String"),
    "chat_component": ("chat_component::read(reader)?", "chat_component::write(&self.$field, writer)?;", "String"),
    "position": ("position::read(reader)?", "position::write(&self.$field, writer)?;", "(i32, i32, i32)"),
    "bitset": ("bitset::read(reader)?", "bitset::write(&self.$field, writer)?;", "Vec<i64>"),
    "nbt": ("nbt::read(reader)?", "nbt::write(self.$field.as_ref(), writer)?;", "Option<crate::codec::nbt::NbtTag>"),
    "slot": ("slot::read(reader)?", "slot::write(self.$field.as_ref(), writer)?;", "Option<crate::codec::slot::SlotData>"),
}

# struct.unpack format codes mapped to rust types + read/write expressions.
_STRUCT_FORMATS: dict[str, tuple[str, int]] = {
    "b": ("i8", 1),
    "B": ("u8", 1),
    "h": ("i16", 2),
    "H": ("u16", 2),
    "i": ("i32", 4),
    "I": ("u32", 4),
    "q": ("i64", 8),
    "Q": ("u64", 8),
    "f": ("f32", 4),
    "d": ("f64", 8),
}


# --- AST parsing ----------------------------------------------------------


@dataclass
class PacketSpec:
    name: str             # module name (snake_case, the file's stem)
    class_name: str       # Python class name (CamelCase)
    packet_id: int
    decode_body: list[ast.stmt]
    encode_body: list[ast.stmt]
    source_path: Path


def _parse_packet(path: Path) -> Optional[PacketSpec]:
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None

    packet_id: Optional[int] = None
    class_name: Optional[str] = None
    decode_body: list[ast.stmt] = []
    encode_body: list[ast.stmt] = []

    for node in tree.body:
        # PACKET_ID = 0xNN
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id == "PACKET_ID" and isinstance(node.value, ast.Constant):
                packet_id = int(node.value.value)
        # Class
        if isinstance(node, ast.ClassDef) and not class_name:
            class_name = node.name
        # Functions
        if isinstance(node, ast.FunctionDef):
            if node.name == "decode":
                decode_body = node.body
            elif node.name == "encode":
                encode_body = node.body

    if packet_id is None or class_name is None or not decode_body:
        return None

    return PacketSpec(
        name=path.stem,
        class_name=class_name,
        packet_id=packet_id,
        decode_body=decode_body,
        encode_body=encode_body,
        source_path=path,
    )


# --- Body emitter ---------------------------------------------------------


@dataclass
class EmitState:
    fields: list[tuple[str, str]] = field(default_factory=list)   # (name, rust_type)
    decode_lines: list[str] = field(default_factory=list)
    encode_lines: list[str] = field(default_factory=list)
    has_todo: bool = False
    needs_uuid_import: bool = False
    needs_chat_import: bool = False
    needs_position_import: bool = False
    needs_nbt_import: bool = False
    needs_slot_import: bool = False
    needs_bitset_import: bool = False
    needs_identifier_import: bool = False


def _add_field(state: EmitState, name: str, rust_type: str) -> None:
    state.fields.append((name, rust_type))


def _track_imports(state: EmitState, codec: str) -> None:
    if codec == "uuid":
        state.needs_uuid_import = True
    elif codec == "chat_component":
        state.needs_chat_import = True
    elif codec == "position":
        state.needs_position_import = True
    elif codec == "nbt":
        state.needs_nbt_import = True
    elif codec == "slot":
        state.needs_slot_import = True
    elif codec == "bitset":
        state.needs_bitset_import = True
    elif codec == "identifier":
        state.needs_identifier_import = True


def _emit_simple_codec_assign(state: EmitState, field_name: str, codec: str) -> None:
    read_tpl, write_tpl, rust_type = _CODECS[codec]
    _add_field(state, field_name, rust_type)
    state.decode_lines.append(f"let {field_name} = {read_tpl};")
    state.encode_lines.append(write_tpl.replace("$field", field_name))
    _track_imports(state, codec)


def _emit_struct_unpack(
    state: EmitState, target_names: list[str], format_str: str
) -> bool:
    """Handle `struct.unpack(">XYZ", reader.read(N))` assignment."""
    fmt = format_str.lstrip(">").lstrip("<").lstrip("!").lstrip("=")
    if len(fmt) != len(target_names):
        return False
    total = 0
    for code in fmt:
        if code not in _STRUCT_FORMATS:
            return False
        total += _STRUCT_FORMATS[code][1]
    # Emit a single read_exact + per-field slice.
    state.decode_lines.append(
        f"let __buf = reader.read_exact({total})?;"
    )
    offset = 0
    encode_chunks: list[str] = []
    for name, code in zip(target_names, fmt):
        rust_ty, sz = _STRUCT_FORMATS[code]
        _add_field(state, name, rust_ty)
        # Decode
        if sz == 1:
            if code == "b":
                state.decode_lines.append(f"let {name} = __buf[{offset}] as i8;")
            else:
                state.decode_lines.append(f"let {name} = __buf[{offset}];")
        else:
            arr_lit = ",".join(f"__buf[{offset + i}]" for i in range(sz))
            state.decode_lines.append(f"let {name} = {rust_ty}::from_be_bytes([{arr_lit}]);")
        # Encode
        encode_chunks.append(f"self.{name}.to_be_bytes()")
        offset += sz
    # Emit encode as multiple write_all calls (cheapest, no temp Vec).
    for name, code in zip(target_names, fmt):
        rust_ty, sz = _STRUCT_FORMATS[code]
        if sz == 1 and code == "b":
            state.encode_lines.append(f"writer.write_all(&[self.{name} as u8])?;")
        elif sz == 1:
            state.encode_lines.append(f"writer.write_all(&[self.{name}])?;")
        else:
            state.encode_lines.append(f"writer.write_all(&self.{name}.to_be_bytes())?;")
    return True


def _emit_reader_read_n(state: EmitState, field_name: str, n_node: ast.expr) -> bool:
    """Handle `reader.read(N)` for raw byte buffers."""
    if isinstance(n_node, ast.Constant) and isinstance(n_node.value, int):
        n = n_node.value
        _add_field(state, field_name, f"[u8; {n}]")
        state.decode_lines.append(
            f"let __buf = reader.read_exact({n})?;"
        )
        state.decode_lines.append(f"let mut {field_name} = [0u8; {n}];")
        state.decode_lines.append(f"{field_name}.copy_from_slice(__buf);")
        state.encode_lines.append(f"writer.write_all(&self.{field_name})?;")
        return True
    if isinstance(n_node, ast.Attribute) and n_node.attr == "remaining":
        # reader.read(reader.remaining()) — slurp rest into Vec<u8>
        _add_field(state, field_name, "Vec<u8>")
        state.decode_lines.append(f"let {field_name} = reader.read_exact(reader.remaining())?.to_vec();")
        state.encode_lines.append(f"writer.write_all(&self.{field_name})?;")
        return True
    return False


def _process_assign(state: EmitState, stmt: ast.Assign) -> bool:
    """Process one assignment statement. Returns False if it can't be mapped."""
    if len(stmt.targets) != 1:
        return False
    target = stmt.targets[0]

    # Case: `field = codec.read(reader)`
    if isinstance(target, ast.Name) and isinstance(stmt.value, ast.Call):
        call = stmt.value
        # codec.read(reader)
        if (isinstance(call.func, ast.Attribute) and call.func.attr == "read"
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id in _CODECS):
            _emit_simple_codec_assign(state, target.id, call.func.value.id)
            return True
        # reader.read(N) — raw bytes
        if (isinstance(call.func, ast.Attribute) and call.func.attr == "read"
                and isinstance(call.func.value, ast.Name) and call.func.value.id == "reader"
                and len(call.args) == 1):
            return _emit_reader_read_n(state, target.id, call.args[0])

    # Case: `a, b, c = struct.unpack(">XYZ", reader.read(N))`
    if (isinstance(target, ast.Tuple)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Attribute)
            and stmt.value.func.attr == "unpack"
            and isinstance(stmt.value.func.value, ast.Name)
            and stmt.value.func.value.id == "struct"):
        # extract format
        if not (len(stmt.value.args) >= 1 and isinstance(stmt.value.args[0], ast.Constant)):
            return False
        fmt = stmt.value.args[0].value
        names = [n.id for n in target.elts if isinstance(n, ast.Name)]
        return _emit_struct_unpack(state, names, fmt)

    # Case: `field, = struct.unpack(">X", reader.read(N))`
    if (isinstance(target, ast.Tuple) and len(target.elts) == 1
            and isinstance(target.elts[0], ast.Name)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Attribute)
            and stmt.value.func.attr == "unpack"):
        if len(stmt.value.args) >= 1 and isinstance(stmt.value.args[0], ast.Constant):
            fmt = stmt.value.args[0].value
            return _emit_struct_unpack(state, [target.elts[0].id], fmt)

    return False


def _process_return_kwargs(state: EmitState, ret: ast.Return) -> bool:
    """Handle `return Pkt(field=expr, ...)` where each value is a codec
    call we recognise."""
    if not isinstance(ret.value, ast.Call):
        return False
    for kw in ret.value.keywords:
        if kw.arg is None:
            return False
        name = kw.arg
        v = kw.value
        # codec.read(reader)
        if (isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute)
                and v.func.attr == "read"
                and isinstance(v.func.value, ast.Name)
                and v.func.value.id in _CODECS):
            _emit_simple_codec_assign(state, name, v.func.value.id)
            continue
        # struct.unpack(">X", reader.read(N))[0] — single-element tuple subscript
        if (isinstance(v, ast.Subscript)
                and isinstance(v.value, ast.Call)
                and isinstance(v.value.func, ast.Attribute)
                and v.value.func.attr == "unpack"
                and len(v.value.args) >= 1
                and isinstance(v.value.args[0], ast.Constant)):
            fmt = v.value.args[0].value
            if _emit_struct_unpack(state, [name], fmt):
                continue
            return False
        # reader.read(1)[0]  — single byte (u8)
        if (isinstance(v, ast.Subscript)
                and isinstance(v.value, ast.Call)
                and isinstance(v.value.func, ast.Attribute)
                and v.value.func.attr == "read"
                and isinstance(v.value.func.value, ast.Name)
                and v.value.func.value.id == "reader"
                and len(v.value.args) == 1
                and isinstance(v.value.args[0], ast.Constant)
                and v.value.args[0].value == 1):
            _add_field(state, name, "u8")
            state.decode_lines.append(f"let {name} = reader.read_exact(1)?[0];")
            state.encode_lines.append(f"writer.write_all(&[self.{name}])?;")
            continue
        # reader.read(N) directly
        if (isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute)
                and v.func.attr == "read"
                and isinstance(v.func.value, ast.Name) and v.func.value.id == "reader"):
            if not _emit_reader_read_n(state, name, v.args[0] if v.args else ast.Constant(0)):
                return False
            continue
        # Unhandled value shape.
        return False
    return True


def _process_body(state: EmitState, body: list[ast.stmt]) -> bool:
    """Returns True if every statement was successfully translated."""
    if len(body) == 1 and isinstance(body[0], ast.Return):
        # Single-line return — try kwargs pattern.
        return _process_return_kwargs(state, body[0])
    for stmt in body:
        if isinstance(stmt, ast.Return):
            continue
        if isinstance(stmt, ast.Assign):
            if _process_assign(state, stmt):
                continue
        # Not handled — mark TODO and bail.
        state.has_todo = True
        return False
    return True


# --- Rust file emit ------------------------------------------------------


def _emit_rust_file(spec: PacketSpec, state: EmitState, state_dir: str, dir_str: str) -> str:
    """Render the final .rs file from accumulated state."""
    state_enum = {"handshaking": "Handshaking", "status": "Status",
                  "login": "Login", "play": "Play"}[state_dir]
    if dir_str == "clientbound":
        packet_trait = "ClientboundPacket"
        dir_label = "Clientbound"
    else:
        packet_trait = "ServerboundPacket"
        dir_label = "Serverbound"

    imports = [
        "use crate::codec::{varint, varlong, string_codec as string, BytesReader, BytesWriter, Reader, Writer};",
        "use crate::errors::ProtocolError;",
        f"use crate::protocol::v763::states::ConnectionState;",
        f"use crate::protocol::v763::{packet_trait};",
    ]
    if state.needs_uuid_import:
        imports.insert(1, "use crate::codec::uuid_codec::{self as uuid_c, Uuid};")
    if state.needs_chat_import:
        imports.insert(1, "use crate::codec::chat_component;")
    if state.needs_position_import:
        imports.insert(1, "use crate::codec::position;")
    if state.needs_nbt_import:
        imports.insert(1, "use crate::codec::nbt;")
    if state.needs_slot_import:
        imports.insert(1, "use crate::codec::slot;")
    if state.needs_bitset_import:
        imports.insert(1, "use crate::codec::bitset;")
    if state.needs_identifier_import:
        imports.insert(1, "use crate::codec::identifier;")

    field_decls = "\n".join(f"    /// Auto-generated field.\n    pub {n}: {t}," for n, t in state.fields)
    field_init = ", ".join(n for n, _ in state.fields)

    decode_block = "\n        ".join(state.decode_lines)
    encode_block = "\n        ".join(state.encode_lines) if state.encode_lines else "Ok::<(), ProtocolError>(())?;"

    _NON_EQ = ("f32", "f64", "NbtTag", "SlotData")
    derive_eq = "Eq, PartialEq, " if not any(
        any(tok in ty for tok in _NON_EQ) for _, ty in state.fields
    ) else "PartialEq, "

    return (
        f"//! Packet `{spec.name}` ({state_dir}/{dir_str}, id 0x{spec.packet_id:02X}).\n"
        f"//!\n"
        f"//! Auto-generated by tools/generate_rust_packets.py from\n"
        f"//! {spec.source_path.relative_to(REPO)}.\n"
        f"\n"
        + "\n".join(imports) + "\n\n"
        f"/// Numeric packet id within `({state_enum}, {dir_label})`.\n"
        f"pub const PACKET_ID: i32 = 0x{spec.packet_id:02X};\n"
        f"\n"
        f"/// {spec.class_name} packet body (auto-generated).\n"
        f"#[derive(Debug, Clone, {derive_eq}Default)]\n"
        f"pub struct {spec.class_name} {{\n"
        f"{field_decls}\n"
        f"}}\n"
        f"\n"
        f"impl {spec.class_name} {{\n"
        f"    /// Decode from `reader`.\n"
        f"    pub fn decode(reader: &mut BytesReader<'_>) -> Result<Self, ProtocolError> {{\n"
        f"        {decode_block}\n"
        f"        Ok(Self {{ {field_init} }})\n"
        f"    }}\n"
        f"}}\n"
        f"\n"
        f"impl {packet_trait} for {spec.class_name} {{\n"
        f"    fn state(&self) -> ConnectionState {{ ConnectionState::{state_enum} }}\n"
        f"    fn packet_id(&self) -> i32 {{ PACKET_ID }}\n"
        f"    fn encode(&self, writer: &mut BytesWriter) -> Result<(), ProtocolError> {{\n"
        f"        {encode_block}\n"
        f"        Ok(())\n"
        f"    }}\n"
        f"}}\n"
    )


# --- Driver --------------------------------------------------------------


def _convert(path: Path) -> Optional[tuple[str, bool]]:
    """Return (rust_source, fully_translated) for the packet, or None."""
    spec = _parse_packet(path)
    if spec is None:
        return None
    parts = path.relative_to(PY_BASE).parts
    state_dir, dir_str, _ = parts[0], parts[1], parts[2]
    state = EmitState()
    if not _process_body(state, spec.decode_body):
        # Bail with a TODO stub. Include the auto-generated header so
        # next run identifies it as our stub (not a hand-written file).
        stub = (
            f"//! Packet `{spec.name}` ({state_dir}/{dir_str}, id 0x{spec.packet_id:02X}).\n"
            f"//!\n"
            f"//! Auto-generated by tools/generate_rust_packets.py from\n"
            f"//! {path.relative_to(REPO)} — STUB (decode pattern not yet supported).\n"
            f"\n"
            f"pub const PACKET_ID: i32 = 0x{spec.packet_id:02X};\n"
        )
        return stub, False
    return _emit_rust_file(spec, state, state_dir, dir_str), True


_AUTO_HEADER = "//! Auto-generated by tools/generate_rust_packets.py"


def _is_hand_written(path: Path) -> bool:
    """If a Rust packet file already exists and lacks the auto-generated
    header, treat it as hand-written and leave it alone."""
    if not path.exists():
        return False
    try:
        head = path.read_text(encoding="utf-8").splitlines()[:6]
    except Exception:
        return False
    return not any(_AUTO_HEADER in line for line in head)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state", choices=["handshaking", "status", "login", "play"])
    p.add_argument("--dir", choices=["clientbound", "serverbound"])
    p.add_argument("--packet", help="restrict to single packet name (stem)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true",
                   help="overwrite hand-written files too")
    args = p.parse_args(argv)

    targets: list[Path] = []
    for state_dir in PY_BASE.iterdir():
        if not state_dir.is_dir():
            continue
        if args.state and state_dir.name != args.state:
            continue
        for dir_dir in state_dir.iterdir():
            if not dir_dir.is_dir() or dir_dir.name not in ("clientbound", "serverbound"):
                continue
            if args.dir and dir_dir.name != args.dir:
                continue
            for pkt in dir_dir.glob("*.py"):
                if pkt.name.startswith("_"):
                    continue
                if args.packet and pkt.stem != args.packet:
                    continue
                targets.append(pkt)
    targets.sort()

    full = 0
    stubs = 0
    skipped_hand = 0
    mods: dict[Path, list[str]] = {}
    for py_path in targets:
        rel = py_path.relative_to(PY_BASE)
        rust_path = RS_BASE / rel.parent / (rel.stem + ".rs")
        # Hand-written files: list in mod.rs but don't regenerate.
        if not args.force and _is_hand_written(rust_path):
            mods.setdefault(rust_path.parent, []).append(rel.stem)
            skipped_hand += 1
            continue
        result = _convert(py_path)
        if result is None:
            continue
        rust_src, ok = result
        rust_path.parent.mkdir(parents=True, exist_ok=True)
        if not args.dry_run:
            rust_path.write_text(rust_src, encoding="utf-8")
        mods.setdefault(rust_path.parent, []).append(rel.stem)
        if ok:
            full += 1
        else:
            stubs += 1

    # Rebuild each mod.rs to include the generated files.
    for mod_dir, names in sorted(mods.items()):
        names.sort()
        lines = ["//! Auto-generated by tools/generate_rust_packets.py.\n"]
        for n in names:
            lines.append(f"pub mod {n};")
        if not args.dry_run:
            (mod_dir / "mod.rs").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"generated {full} fully + {stubs} stubs (TODO) + {skipped_hand} hand-written preserved out of {len(targets)} sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
