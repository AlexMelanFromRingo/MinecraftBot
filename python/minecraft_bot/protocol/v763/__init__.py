"""Protocol 763 — Minecraft Java Edition 1.20.1 wire definitions.

Submodules:

- :mod:`.states`   — :class:`ConnectionState`, :class:`Direction`
- :mod:`.registry` — :class:`CodecRegistry` walking ``packets/``

Packets live one-per-file under ``packets/{state}/{direction}/`` (Constitution II).
"""

from __future__ import annotations

from minecraft_bot.protocol.v763.states import ConnectionState, Direction

__all__ = ["ConnectionState", "Direction"]
