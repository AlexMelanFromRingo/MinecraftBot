#!/usr/bin/env python3
"""Hazard arena with a forced corridor:

The east half of the flat platform is enclosed by 2-block-tall stone
walls at z=9998 and z=10002, from x=10008 to x=10030. Inside the
3-wide channel (z=9999..10001) the bot MUST traverse each hazard;
there's no detour route within 2 jumps.

Zones (relative to centre 10000, 200, 10000):

    +5  E  3-tall wall          (z=9998..10002, blocks straight)
    +8 .. +30 E  channel walls  (z=9998, z=10002 — block detours)
    +10 E  oak_slab[type=bottom]  (top y=200.5; STEP_HEIGHT just fits)
    +13..+17 E  water pool 5×3   (swim through; exit needs jump)
    +20 E  full-block ledge      (needs jump)
    +25 E  3-deep drop pit       (fall through)

Plus a wide snow/ice purge (200-block radius) because surrounding
biomes are snowy.
"""

from __future__ import annotations

import asyncio
import os

from minecraft_bot.bot import Bot

HOST = os.environ.get("MINECRAFT_BOT_TEST_HOST", "172.26.160.1")
PORT = int(os.environ.get("MINECRAFT_BOT_TEST_PORT", "25565"))
CX, CY, CZ = 10000, 200, 10000


async def cmd(bot: Bot, c: str) -> None:
    await bot.command(c)
    await asyncio.sleep(0.15)


async def main() -> None:
    async with Bot.offline(HOST, PORT, "PyBot") as bot:
        await asyncio.sleep(1.5)
        await cmd(bot, f"tp PyBot {CX} {CY + 5} {CZ}")
        await asyncio.sleep(1.0)

        # Wide biome override + permanent clear weather.
        await cmd(bot, f"fillbiome 9900 -64 9900 10100 320 10100 minecraft:plains")
        await cmd(bot, "weather clear 1000000")
        await cmd(bot, "time set day")
        await cmd(bot, "gamerule doWeatherCycle false")
        await cmd(bot, "gamerule randomTickSpeed 0")

        # Snow / ice purge over a 200-block window (fills cap per /fill is
        # 32768 blocks, but we do many small calls).
        for snow_block in ("snow", "snow_block", "ice", "packed_ice", "blue_ice"):
            # /fill max volume is 32768. 201×40×201 = 1.6M — split into Y bands.
            for y0 in range(199, 240, 16):
                y1 = min(y0 + 15, 240)
                await cmd(
                    bot,
                    f"fill 9900 {y0} 9900 10100 {y1} 10100 air "
                    f"replace minecraft:{snow_block}",
                )

        # Rebuild flat platform.
        await cmd(bot, f"fill 9970 199 9970 10030 199 10030 stone")
        await cmd(bot, f"fill 9970 200 9970 10030 220 10030 air")

        # Zone L: 3-tall wall blocking straight east path.
        await cmd(bot, f"fill 10005 200 9998 10005 202 10002 stone")

        # Corridor walls (z=9998 and z=10002) from x=10008 to x=10030,
        # 3 blocks tall so bot can't jump-glitch over them.
        await cmd(bot, f"fill 10008 200 9998 10030 202 9998 stone")
        await cmd(bot, f"fill 10008 200 10002 10030 202 10002 stone")

        # +10 E: bottom slab row.
        await cmd(bot, f"fill 10010 200 9999 10010 200 10001 oak_slab[type=bottom]")

        # +13..+17 E: water pool 5×3, 1-deep.
        await cmd(bot, f"fill 10013 199 9999 10017 199 10001 air")
        await cmd(bot, f"fill 10013 198 9999 10017 198 10001 stone")
        await cmd(bot, f"fill 10013 199 9999 10017 199 10001 water")

        # +20 E: full-block ledge (single stone cube).
        await cmd(bot, f"fill 10020 200 9999 10020 200 10001 stone")

        # +25 E: 3-deep pit 1×3 with explicit stone floor at y=196.
        await cmd(bot, f"fill 10025 196 9999 10025 196 10001 stone")
        await cmd(bot, f"fill 10025 197 9999 10025 199 10001 air")

        # Force-load arena chunks.
        await cmd(bot, f"forceload add 9968 9968 10032 10032")

        await cmd(bot, f"tp PyBot {CX} {CY + 1} {CZ}")
        print(
            "Corridor hazard arena ready:\n"
            "  walls at z=9998/9 z=10002 from x=10008..10030 (3-tall)\n"
            "  +5 E   wall (z=±2)\n"
            "  +10 E  bottom-slab\n"
            "  +13..+17 E  water pool\n"
            "  +20 E  1-block ledge\n"
            "  +25 E  3-deep pit\n"
            "Biome=plains, snow/ice purged in 200-block window."
        )


if __name__ == "__main__":
    asyncio.run(main())
