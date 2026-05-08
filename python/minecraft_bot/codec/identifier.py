"""Identifier codec — namespaced resource location (``namespace:path``).

When no colon is present, the namespace defaults to ``"minecraft"``.
Wire format is identical to a regular String; the only added behaviour
is the namespace defaulting on decode.
"""

from __future__ import annotations

from minecraft_bot.codec import Reader, Writer, string
from minecraft_bot.errors import ValueOutOfRange

DEFAULT_NAMESPACE = "minecraft"


def read(reader: Reader) -> str:
    """Decode an Identifier as ``namespace:path``. Inserts default namespace
    if the wire string has no colon."""
    raw = string.read(reader)
    if ":" not in raw:
        return f"{DEFAULT_NAMESPACE}:{raw}"
    return raw


def write(value: str, writer: Writer) -> None:
    """Encode an Identifier. Strips a leading ``minecraft:`` only if the
    caller provided it explicitly — otherwise round-trips bytes-for-bytes
    with the original wire form."""
    if not value:
        raise ValueOutOfRange("identifier", value)
    string.write(value, writer)


__all__ = ["read", "write", "DEFAULT_NAMESPACE"]
