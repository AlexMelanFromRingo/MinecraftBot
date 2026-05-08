"""NBT codec — Named Binary Tag, Java Edition.

For protocol 763 (Minecraft 1.20.1), NBT is "traditional": the root tag
carries a name. For protocol 764+ ("network NBT"), the root name is
stripped — :func:`read` and :func:`write` accept a ``nameless_root``
flag to handle that case once a 764+ milestone arrives.

Tag type table (matches the wire byte values exactly)::

    TAG_End        = 0
    TAG_Byte       = 1   # i8
    TAG_Short      = 2   # i16 big-endian
    TAG_Int        = 3   # i32 big-endian
    TAG_Long       = 4   # i64 big-endian
    TAG_Float      = 5   # f32 big-endian
    TAG_Double     = 6   # f64 big-endian
    TAG_Byte_Array = 7   # i32 length + signed bytes
    TAG_String     = 8   # u16 length + UTF-8 (Java-modified UTF-8 strictly,
                         # but unmodified UTF-8 round-trips for all common content)
    TAG_List       = 9   # 1-byte item type + i32 count + items (no per-item tag bytes)
    TAG_Compound   = 10  # sequence of named tags until TAG_End
    TAG_Int_Array  = 11  # i32 length + count*i32
    TAG_Long_Array = 12  # i32 length + count*i64

To preserve type identity across encode/decode (FR-013 round-trip
correctness), every numeric value is wrapped in a tagged dataclass.
:class:`Compound` is a thin ``dict[str, NbtTag]`` wrapper;
:class:`NbtList` enforces homogeneous element type.

A full NBT document is read with :func:`read` and written with
:func:`write`. Decoding an empty/absent NBT returns ``None`` (this is
how the Slot codec spells "no NBT").
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Optional, Union

from minecraft_bot.codec import Reader, Writer
from minecraft_bot.errors import MalformedNbt, ValueOutOfRange

# --- tag type codes --------------------------------------------------------

TAG_END = 0
TAG_BYTE = 1
TAG_SHORT = 2
TAG_INT = 3
TAG_LONG = 4
TAG_FLOAT = 5
TAG_DOUBLE = 6
TAG_BYTE_ARRAY = 7
TAG_STRING = 8
TAG_LIST = 9
TAG_COMPOUND = 10
TAG_INT_ARRAY = 11
TAG_LONG_ARRAY = 12


# --- tagged value classes --------------------------------------------------


@dataclass(frozen=True, slots=True)
class NbtByte:
    value: int  # i8

    def __post_init__(self) -> None:
        if not -128 <= self.value <= 127:
            raise ValueOutOfRange("nbt.byte", self.value)


@dataclass(frozen=True, slots=True)
class NbtShort:
    value: int  # i16

    def __post_init__(self) -> None:
        if not -(1 << 15) <= self.value <= (1 << 15) - 1:
            raise ValueOutOfRange("nbt.short", self.value)


@dataclass(frozen=True, slots=True)
class NbtInt:
    value: int  # i32

    def __post_init__(self) -> None:
        if not -(1 << 31) <= self.value <= (1 << 31) - 1:
            raise ValueOutOfRange("nbt.int", self.value)


@dataclass(frozen=True, slots=True)
class NbtLong:
    value: int  # i64

    def __post_init__(self) -> None:
        if not -(1 << 63) <= self.value <= (1 << 63) - 1:
            raise ValueOutOfRange("nbt.long", self.value)


@dataclass(frozen=True, slots=True)
class NbtFloat:
    value: float


@dataclass(frozen=True, slots=True)
class NbtDouble:
    value: float


@dataclass(frozen=True, slots=True)
class NbtByteArray:
    values: bytes  # signed bytes; we store as Python bytes


@dataclass(frozen=True, slots=True)
class NbtString:
    value: str


@dataclass(frozen=True, slots=True)
class NbtList:
    """A homogeneous list of tags. ``element_type`` is the wire type byte
    (TAG_BYTE, TAG_INT, TAG_COMPOUND, ...) of every element. An empty
    list with ``element_type=TAG_END`` is the canonical empty-list
    representation."""

    element_type: int
    items: tuple["NbtTag", ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class NbtCompound:
    """A mapping from name to tag. Order is preserved on round-trip."""

    items: tuple[tuple[str, "NbtTag"], ...] = field(default_factory=tuple)

    def get(self, name: str) -> Optional["NbtTag"]:
        for n, v in self.items:
            if n == name:
                return v
        return None

    def to_dict(self) -> dict[str, "NbtTag"]:
        return dict(self.items)


@dataclass(frozen=True, slots=True)
class NbtIntArray:
    values: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class NbtLongArray:
    values: tuple[int, ...]


NbtTag = Union[
    NbtByte,
    NbtShort,
    NbtInt,
    NbtLong,
    NbtFloat,
    NbtDouble,
    NbtByteArray,
    NbtString,
    NbtList,
    NbtCompound,
    NbtIntArray,
    NbtLongArray,
]


# --- helpers ---------------------------------------------------------------


def _read_string(reader: Reader) -> str:
    """NBT-style string: 2-byte big-endian length + UTF-8 payload."""
    (n,) = struct.unpack(">H", reader.read(2))
    raw = reader.read(n)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MalformedNbt(f"non-utf-8 string: {exc}") from exc


def _write_string(value: str, writer: Writer) -> None:
    raw = value.encode("utf-8")
    if len(raw) > 0xFFFF:
        raise ValueOutOfRange("nbt.string.length", len(raw))
    writer.write(struct.pack(">H", len(raw)))
    writer.write(raw)


def _tag_type_for(tag: NbtTag) -> int:
    cls = type(tag)
    return _CLASS_TO_TAG[cls]


_CLASS_TO_TAG: dict[type, int] = {
    NbtByte: TAG_BYTE,
    NbtShort: TAG_SHORT,
    NbtInt: TAG_INT,
    NbtLong: TAG_LONG,
    NbtFloat: TAG_FLOAT,
    NbtDouble: TAG_DOUBLE,
    NbtByteArray: TAG_BYTE_ARRAY,
    NbtString: TAG_STRING,
    NbtList: TAG_LIST,
    NbtCompound: TAG_COMPOUND,
    NbtIntArray: TAG_INT_ARRAY,
    NbtLongArray: TAG_LONG_ARRAY,
}


# --- payload-only readers/writers (no type byte, no name) ------------------


def _read_payload(tag_type: int, reader: Reader) -> NbtTag:  # noqa: PLR0911, PLR0912
    if tag_type == TAG_BYTE:
        return NbtByte(struct.unpack(">b", reader.read(1))[0])
    if tag_type == TAG_SHORT:
        return NbtShort(struct.unpack(">h", reader.read(2))[0])
    if tag_type == TAG_INT:
        return NbtInt(struct.unpack(">i", reader.read(4))[0])
    if tag_type == TAG_LONG:
        return NbtLong(struct.unpack(">q", reader.read(8))[0])
    if tag_type == TAG_FLOAT:
        return NbtFloat(struct.unpack(">f", reader.read(4))[0])
    if tag_type == TAG_DOUBLE:
        return NbtDouble(struct.unpack(">d", reader.read(8))[0])
    if tag_type == TAG_BYTE_ARRAY:
        (n,) = struct.unpack(">i", reader.read(4))
        if n < 0:
            raise MalformedNbt(f"negative byte array length: {n}")
        return NbtByteArray(reader.read(n))
    if tag_type == TAG_STRING:
        return NbtString(_read_string(reader))
    if tag_type == TAG_LIST:
        elem_type = reader.read(1)[0]
        (count,) = struct.unpack(">i", reader.read(4))
        if count < 0:
            raise MalformedNbt(f"negative list count: {count}")
        if count == 0 and elem_type == TAG_END:
            return NbtList(element_type=TAG_END, items=())
        if elem_type == TAG_END:
            raise MalformedNbt("non-empty list with TAG_End element type")
        items = tuple(_read_payload(elem_type, reader) for _ in range(count))
        return NbtList(element_type=elem_type, items=items)
    if tag_type == TAG_COMPOUND:
        items: list[tuple[str, NbtTag]] = []
        while True:
            child_type = reader.read(1)[0]
            if child_type == TAG_END:
                return NbtCompound(items=tuple(items))
            child_name = _read_string(reader)
            child_value = _read_payload(child_type, reader)
            items.append((child_name, child_value))
    if tag_type == TAG_INT_ARRAY:
        (n,) = struct.unpack(">i", reader.read(4))
        if n < 0:
            raise MalformedNbt(f"negative int array length: {n}")
        return NbtIntArray(tuple(struct.unpack(f">{n}i", reader.read(4 * n))))
    if tag_type == TAG_LONG_ARRAY:
        (n,) = struct.unpack(">i", reader.read(4))
        if n < 0:
            raise MalformedNbt(f"negative long array length: {n}")
        return NbtLongArray(tuple(struct.unpack(f">{n}q", reader.read(8 * n))))
    raise MalformedNbt(f"unknown tag type: {tag_type}")


def _write_payload(tag: NbtTag, writer: Writer) -> None:  # noqa: PLR0912
    if isinstance(tag, NbtByte):
        writer.write(struct.pack(">b", tag.value))
    elif isinstance(tag, NbtShort):
        writer.write(struct.pack(">h", tag.value))
    elif isinstance(tag, NbtInt):
        writer.write(struct.pack(">i", tag.value))
    elif isinstance(tag, NbtLong):
        writer.write(struct.pack(">q", tag.value))
    elif isinstance(tag, NbtFloat):
        writer.write(struct.pack(">f", tag.value))
    elif isinstance(tag, NbtDouble):
        writer.write(struct.pack(">d", tag.value))
    elif isinstance(tag, NbtByteArray):
        writer.write(struct.pack(">i", len(tag.values)))
        writer.write(tag.values)
    elif isinstance(tag, NbtString):
        _write_string(tag.value, writer)
    elif isinstance(tag, NbtList):
        elem_type = tag.element_type if tag.items else TAG_END
        writer.write(bytes([elem_type]))
        writer.write(struct.pack(">i", len(tag.items)))
        for it in tag.items:
            if _tag_type_for(it) != elem_type:
                raise ValueOutOfRange("nbt.list.heterogeneous", type(it).__name__)
            _write_payload(it, writer)
    elif isinstance(tag, NbtCompound):
        for name, value in tag.items:
            writer.write(bytes([_tag_type_for(value)]))
            _write_string(name, writer)
            _write_payload(value, writer)
        writer.write(bytes([TAG_END]))
    elif isinstance(tag, NbtIntArray):
        writer.write(struct.pack(">i", len(tag.values)))
        if tag.values:
            writer.write(struct.pack(f">{len(tag.values)}i", *tag.values))
    elif isinstance(tag, NbtLongArray):
        writer.write(struct.pack(">i", len(tag.values)))
        if tag.values:
            writer.write(struct.pack(f">{len(tag.values)}q", *tag.values))
    else:
        raise ValueOutOfRange("nbt.tag", type(tag).__name__)


# --- public API ------------------------------------------------------------


def read(reader: Reader, *, nameless_root: bool = False) -> Optional[NbtTag]:
    """Decode a complete NBT document from ``reader``.

    Returns ``None`` if the first byte is :data:`TAG_END` (canonical
    "no NBT" marker used in Slot data).

    With ``nameless_root=True`` (network-NBT, protocol 764+), the root
    tag's name is omitted; pass this when implementing the future v764.
    """
    tag_type = reader.read(1)[0]
    if tag_type == TAG_END:
        return None
    if tag_type < TAG_BYTE or tag_type > TAG_LONG_ARRAY:
        # Fail fast on unknown root tag id, before trying to read a name.
        raise MalformedNbt(f"unknown tag type at root: {tag_type}")
    if not nameless_root:
        # Discard the root name; we don't surface it in the value tree.
        _read_string(reader)
    return _read_payload(tag_type, reader)


def write(value: Optional[NbtTag], writer: Writer, *, nameless_root: bool = False,
          root_name: str = "") -> None:
    """Encode a complete NBT document into ``writer``.

    ``value=None`` writes a single :data:`TAG_END` byte (canonical
    "no NBT").
    """
    if value is None:
        writer.write(bytes([TAG_END]))
        return
    writer.write(bytes([_tag_type_for(value)]))
    if not nameless_root:
        _write_string(root_name, writer)
    _write_payload(value, writer)


__all__ = [
    "TAG_END", "TAG_BYTE", "TAG_SHORT", "TAG_INT", "TAG_LONG", "TAG_FLOAT",
    "TAG_DOUBLE", "TAG_BYTE_ARRAY", "TAG_STRING", "TAG_LIST", "TAG_COMPOUND",
    "TAG_INT_ARRAY", "TAG_LONG_ARRAY",
    "NbtByte", "NbtShort", "NbtInt", "NbtLong", "NbtFloat", "NbtDouble",
    "NbtByteArray", "NbtString", "NbtList", "NbtCompound",
    "NbtIntArray", "NbtLongArray", "NbtTag",
    "read", "write",
]
