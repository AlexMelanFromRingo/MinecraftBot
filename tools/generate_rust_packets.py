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
    if isinstance(n_node, ast.Name):
        # reader.read(some_var) — variable-length Vec<u8>
        _add_field(state, field_name, "Vec<u8>")
        state.decode_lines.append(
            f"let {field_name} = reader.read_exact({n_node.id} as usize)?.to_vec();"
        )
        # Encode: emit prefix-then-bytes (the matching Python encode usually
        # does `varint.write(len(packet.x), writer); writer.write(packet.x)`).
        # We only emit the bytes write here; the length prefix comes from the
        # preceding assignment's encode line (handled separately).
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


def _expr_to_decode(state: EmitState, v: ast.expr) -> Optional[tuple[str, str]]:
    """Try to render a Python expression as (rust_expr, rust_type).
    Returns None if unsupported. Side-effect: updates state.imports."""
    # codec.read(reader)
    if (isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute)
            and v.func.attr == "read"
            and isinstance(v.func.value, ast.Name)
            and v.func.value.id in _CODECS):
        codec = v.func.value.id
        _track_imports(state, codec)
        read_tpl, _, rust_ty = _CODECS[codec]
        return (read_tpl, rust_ty)
    # struct.unpack(">X", reader.read(N))[0]
    if (isinstance(v, ast.Subscript)
            and isinstance(v.value, ast.Call)
            and isinstance(v.value.func, ast.Attribute)
            and v.value.func.attr == "unpack"
            and len(v.value.args) >= 1
            and isinstance(v.value.args[0], ast.Constant)):
        fmt = v.value.args[0].value
        f = fmt.lstrip(">").lstrip("<").lstrip("!").lstrip("=")
        if len(f) == 1 and f in _STRUCT_FORMATS:
            rust_ty, sz = _STRUCT_FORMATS[f]
            if sz == 1 and f == "b":
                return (f"(reader.read_exact(1)?[0] as i8)", "i8")
            if sz == 1:
                return (f"reader.read_exact(1)?[0]", "u8")
            return (
                f"{rust_ty}::from_be_bytes({{ let _b = reader.read_exact({sz})?; "
                + "[" + ",".join(f"_b[{i}]" for i in range(sz)) + "] }})",
                rust_ty,
            )
    # reader.read(1)[0]
    if (isinstance(v, ast.Subscript)
            and isinstance(v.value, ast.Call)
            and isinstance(v.value.func, ast.Attribute)
            and v.value.func.attr == "read"
            and isinstance(v.value.func.value, ast.Name)
            and v.value.func.value.id == "reader"
            and len(v.value.args) == 1
            and isinstance(v.value.args[0], ast.Constant)
            and v.value.args[0].value == 1):
        return ("reader.read_exact(1)?[0]", "u8")
    return None


def _process_for_array(state: EmitState, stmt: ast.For) -> bool:
    """Handle::

        for _ in range(n):
            items.append(<expr>)

    where ``items`` was just initialised to ``[]``. Emit a Rust
    Vec<T> built up the same way."""
    # iter must be range(...)
    if not (isinstance(stmt.iter, ast.Call)
            and isinstance(stmt.iter.func, ast.Name) and stmt.iter.func.id == "range"):
        return False
    if not (len(stmt.iter.args) == 1 and isinstance(stmt.iter.args[0], ast.Name)):
        return False
    n_var = stmt.iter.args[0].id
    # body must be exactly one .append(...)
    if not (len(stmt.body) == 1 and isinstance(stmt.body[0], ast.Expr)
            and isinstance(stmt.body[0].value, ast.Call)
            and isinstance(stmt.body[0].value.func, ast.Attribute)
            and stmt.body[0].value.func.attr == "append"
            and len(stmt.body[0].value.args) == 1):
        return False
    target_name = stmt.body[0].value.func.value.id   # e.g. "items"
    expr_decoded = _expr_to_decode(state, stmt.body[0].value.args[0])
    if expr_decoded is None:
        return False
    elem_expr, elem_ty = expr_decoded
    # Promote the array field type. The list variable was already
    # declared as `let mut target_name: Vec<T> = Vec::new();` — find it
    # and bump its type. Simpler: re-add as Vec<T> on first sight.
    state.fields = [(n, t) for n, t in state.fields if n != target_name]
    _add_field(state, target_name, f"Vec<{elem_ty}>")
    # Decode: replace the empty-init line with a proper Vec::with_capacity.
    # The empty list `target_name = []` line should already have been
    # processed by _process_assign as a generic placeholder. Insert
    # the loop.
    state.decode_lines.append(
        f"let mut {target_name}: Vec<{elem_ty}> = Vec::with_capacity({n_var} as usize);"
    )
    state.decode_lines.append(f"for _ in 0..{n_var} {{")
    state.decode_lines.append(f"    {target_name}.push({elem_expr});")
    state.decode_lines.append("}")
    # Encode: emit a length prefix + element loop. The Python encode
    # likely does `varint.write(len(packet.x), writer)` plus a per-elem
    # write. We can't always tell which codec writes the element, so
    # emit a simple loop using the same codec.
    # NOTE: caller is responsible for the length-prefix encode (it
    # appears as a varint.write(len(packet.field), writer) line in the
    # Python encode body, NOT here).
    # Try to guess element write template from the read template.
    elem_write = _guess_write_for(elem_expr, elem_ty)
    if elem_write:
        state.encode_lines.append(f"for __e in &self.{target_name} {{")
        state.encode_lines.append(f"    {elem_write}")
        state.encode_lines.append("}")
    else:
        state.encode_lines.append(f"// TODO encode {target_name}")
    return True


def _guess_write_for(read_expr: str, rust_ty: str) -> Optional[str]:
    """Pair a recognised read expr with its encode line."""
    for codec, (read_tpl, write_tpl, ty) in _CODECS.items():
        if read_tpl == read_expr:
            return write_tpl.replace("self.$field", "*__e") if ty in ("i32", "i64") else write_tpl.replace("&self.$field", "__e").replace("self.$field", "*__e")
    if rust_ty in ("u8",):
        return "writer.write_all(&[*__e])?;"
    if rust_ty in ("i8",):
        return "writer.write_all(&[*__e as u8])?;"
    if rust_ty in ("u16", "i16", "u32", "i32", "u64", "i64", "f32", "f64"):
        return "writer.write_all(&__e.to_be_bytes())?;"
    return None


def _process_if_optional(state: EmitState, stmt: ast.If) -> Optional[str]:
    """Match the ``if present == 1: x = codec.read(reader); elif present == 0: x = None; else: raise`` pattern.
    Returns the optional field name on match, or None on failure."""
    # `if present == 1`
    if not (isinstance(stmt.test, ast.Compare)
            and len(stmt.test.ops) == 1 and isinstance(stmt.test.ops[0], ast.Eq)
            and isinstance(stmt.test.left, ast.Name)
            and isinstance(stmt.test.comparators[0], ast.Constant)
            and stmt.test.comparators[0].value == 1):
        return None
    present_var = stmt.test.left.id
    # `if` body: single Assign(name, codec.read(reader))
    if not (len(stmt.body) == 1 and isinstance(stmt.body[0], ast.Assign)
            and len(stmt.body[0].targets) == 1
            and isinstance(stmt.body[0].targets[0], ast.Name)):
        return None
    field = stmt.body[0].targets[0].id
    inner = _expr_to_decode(state, stmt.body[0].value)
    if inner is None:
        return None
    rust_expr, rust_ty = inner
    # `elif present == 0: x = None`
    if not stmt.orelse or not isinstance(stmt.orelse[0], ast.If):
        return None
    elif_stmt = stmt.orelse[0]
    # Could be just plain elif without the raise — we tolerate both shapes.
    state.decode_lines.append(f"let {field} = match {present_var} {{")
    state.decode_lines.append(f"    0 => None,")
    state.decode_lines.append(f"    1 => Some({rust_expr}),")
    state.decode_lines.append(
        f"    other => return Err(ProtocolError::DecodeError("
        f"format!(\"{field}.present: {{}}\", other))),"
    )
    state.decode_lines.append("};")
    state.fields = [(n, t) for n, t in state.fields if n != field]
    _add_field(state, field, f"Option<{rust_ty}>")
    # Encode is harder — we'll emit a stub for caller to potentially fix.
    state.encode_lines.append(f"match &self.{field} {{")
    state.encode_lines.append(f"    None => writer.write_all(&[0])?,")
    state.encode_lines.append(f"    Some(v) => {{")
    state.encode_lines.append(f"        writer.write_all(&[1])?;")
    # Inline the same codec write idiom.
    _encode_inline = _inline_encode_for(rust_expr)
    if _encode_inline:
        state.encode_lines.append(f"        {_encode_inline}")
    state.encode_lines.append(f"    }}")
    state.encode_lines.append(f"}}")
    return field


def _inline_encode_for(read_expr: str) -> Optional[str]:
    """Mirror of _guess_write_for keyed by a v identifier."""
    for codec, (read_tpl, write_tpl, _ty) in _CODECS.items():
        if read_tpl == read_expr:
            return write_tpl.replace("self.$field", "*v") if codec in ("varint", "varlong") else write_tpl.replace("&self.$field", "v")
    return None


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
    """Walk the decode body. Returns True if everything was translated."""
    if len(body) == 1 and isinstance(body[0], ast.Return):
        # Single-line return — try kwargs pattern.
        return _process_return_kwargs(state, body[0])

    # Track local variable → rust expression source for return mapping.
    # The return statement may use kwargs like `Foo(field=local_var)`
    # — we record each local as a field with the right Rust type.
    final_return: Optional[ast.Return] = None

    for stmt in body:
        if isinstance(stmt, ast.Return):
            final_return = stmt
            continue
        if isinstance(stmt, ast.Assign):
            if _process_assign(state, stmt):
                continue
            # Try inline-expr → "let name = <rust_expr>"
            if (len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)):
                inner = _expr_to_decode(state, stmt.value)
                if inner is not None:
                    rust_expr, rust_ty = inner
                    nm = stmt.targets[0].id
                    state.decode_lines.append(f"let {nm} = {rust_expr};")
                    _add_field(state, nm, rust_ty)
                    continue
            # Could be `items: list[T] = []` — that's an AnnAssign actually.
            return False
        if isinstance(stmt, ast.AnnAssign):
            # `items: list[T] = []` — record as empty Vec; type fixed by for-loop.
            if (isinstance(stmt.target, ast.Name)
                    and isinstance(stmt.value, ast.List)
                    and not stmt.value.elts):
                # Leave the field unbound; the for-loop will redeclare with the real type.
                # We emit nothing here.
                continue
            return False
        if isinstance(stmt, ast.For):
            if _process_for_array(state, stmt):
                continue
            return False
        if isinstance(stmt, ast.If):
            if _process_if_optional(state, stmt) is not None:
                continue
            return False
        # Unknown statement type.
        return False

    # If the return uses kwargs mapping `field=local_var` and the local
    # name differs from the field name, rewrite the field list to use
    # the field names.
    if final_return is not None and isinstance(final_return.value, ast.Call):
        rename_map: dict[str, str] = {}
        for kw in final_return.value.keywords:
            if kw.arg and isinstance(kw.value, ast.Name) and kw.arg != kw.value.id:
                rename_map[kw.value.id] = kw.arg
        if rename_map:
            new_fields: list[tuple[str, str]] = []
            for n, t in state.fields:
                new_fields.append((rename_map.get(n, n), t))
            state.fields = new_fields
            # Patch decode_lines so references to local names are renamed in `let X = ...;`.
            patched: list[str] = []
            for line in state.decode_lines:
                for old, new in rename_map.items():
                    line = re.sub(rf"\blet {old}\b", f"let {new}", line)
                    line = re.sub(rf"\blet mut {old}\b", f"let mut {new}", line)
                patched.append(line)
            state.decode_lines = patched
            # Patch encode_lines for self.X references the same way.
            patched = []
            for line in state.encode_lines:
                for old, new in rename_map.items():
                    line = re.sub(rf"self\.{old}\b", f"self.{new}", line)
                patched.append(line)
            state.encode_lines = patched

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
