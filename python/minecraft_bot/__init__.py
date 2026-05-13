"""minecraft_bot — Minecraft Java Edition bot framework (canonical Python implementation).

This is the package's public surface. Subpackages:

- ``minecraft_bot.codec``           — primitive type codecs (VarInt, NBT, Slot, ...)
- ``minecraft_bot.protocol.v763``   — protocol-763 packet definitions and registry
- ``minecraft_bot.connection``      — :class:`Connection` lifecycle (offline factory)
- ``minecraft_bot.framer``          — length-prefix + compression-threshold framer
- ``minecraft_bot.errors``          — typed :class:`ProtocolError` hierarchy
- ``minecraft_bot.wire_log``        — :class:`WireLog` capture and offline replay

See ``specs/001-protocol-foundation/contracts/python-api.md`` for the
normative public API contract.
"""

from __future__ import annotations

import logging

# Canonical logger for the entire framework. Sub-loggers inherit from it.
# Constitution VII (Observability and Determinism).
logging.getLogger("minecraft_bot.protocol").addHandler(logging.NullHandler())

__version__ = "0.2.0"
# Backend identifier — distinct from `minecraft_bot_accel.implementation`
# (== "rust"). Used by parity tests to confirm which backend is active.
implementation = "python"
__all__ = ["__version__", "implementation"]

# Real public re-exports are added by later milestones once the corresponding
# modules land. Keeping the public surface explicit avoids accidental exports.
