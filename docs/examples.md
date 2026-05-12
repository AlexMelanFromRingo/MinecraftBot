# Examples

Practical recipes for common bot tasks. Each example shows the Python
reference version and the `minecraft_bot_accel` equivalent where
they differ.

## Connect and disconnect

```python
import asyncio
from minecraft_bot.bot import Bot

async def main():
    async with Bot.offline("172.26.160.1", 25565, "ExampleBot") as bot:
        print(f"connected as entity {bot.entity_id}")
        print(f"spawn position: ({bot.x:.1f}, {bot.y:.1f}, {bot.z:.1f})")

asyncio.run(main())
```

Accel equivalent:

```python
import asyncio
import minecraft_bot_accel as mb

async def main():
    bot = mb.Bot.offline("172.26.160.1", 25565, "ExampleBot")
    await bot.connect()
    try:
        eid = await bot.entity_id()
        pos = await bot.position()
        print(f"connected as entity {eid}")
        print(f"spawn position: {pos[:3]}")
    finally:
        await bot.disconnect()

asyncio.run(main())
```

## Find blocks of a given type

```python
async with Bot.offline("172.26.160.1", 25565, "Miner") as bot:
    await asyncio.sleep(2)  # let chunks stream in
    blocks = bot.world.find_blocks_nearby(
        "minecraft:diamond_ore",
        origin=(bot.x, bot.y, bot.z),
        radius=32,
        limit=8,
    )
    for x, y, z in blocks:
        print(f"diamond at ({x}, {y}, {z})")
```

Accel: identical API.

```python
bot = mb.Bot.offline("172.26.160.1", 25565, "Miner")
await bot.connect()
try:
    for _ in range(40):
        if bot.loaded_chunk_count() > 20:
            break
        await asyncio.sleep(0.25)
    pos = await bot.position()
    blocks = bot.world.find_blocks_nearby(
        "minecraft:diamond_ore",
        origin=pos[:3],
        radius=32,
        limit=8,
    )
    for x, y, z in blocks:
        print(f"diamond at ({x}, {y}, {z})")
finally:
    await bot.disconnect()
```

## Walk to a target

Python reference walks via 20 Hz physics tick with auto-jump and
auto-step for half-blocks and slabs:

```python
async with Bot.offline("172.26.160.1", 25565, "Walker") as bot:
    await bot.walk_to(bot.x + 10, bot.y, bot.z, timeout=30.0)
```

Accel uses pathfinder slides with a 2-block-per-tick anti-cheat cap.
The function signature is the same; the motion profile is different
but the bot ends up at the target.

```python
bot = mb.Bot.offline("172.26.160.1", 25565, "Walker")
await bot.connect()
try:
    pos = await bot.position()
    ok = await bot.walk_to(pos[0] + 10, pos[1], pos[2], timeout=30.0)
    print(f"arrived: {ok}")
finally:
    await bot.disconnect()
```

## Drop the held item

```python
# Python ref
await bot.drop_held_item()              # drop one
await bot.drop_held_item(full_stack=True)  # drop the whole stack
```

```python
# Accel
await bot.drop_held_item()
await bot.drop_held_item(full_stack=True)
```

## Hold both backends in one process

```python
import asyncio
import minecraft_bot
import minecraft_bot_accel as mb

async def main():
    bot_py = minecraft_bot.bot.Bot.offline("172.26.160.1", 25565, "PyBot")
    bot_ac = mb.Bot.offline("172.26.160.1", 25565, "AcBot")

    # Connect in sequence (Paper rate-limits same-IP reconnects).
    async with bot_py:
        eid_py = bot_py.entity_id

    await asyncio.sleep(5)  # respect server-side connection throttle

    await bot_ac.connect()
    try:
        eid_ac = await bot_ac.entity_id()
        print(f"py-bot eid={eid_py}, accel-bot eid={eid_ac}")
    finally:
        await bot_ac.disconnect()

asyncio.run(main())
```

## Sending raw packets from the accel side

The accel Bot does not duplicate the Python reference's 176 typed
packet dataclasses. To send a custom serverbound packet, encode it
with the Python encoder and forward the bytes:

```python
import minecraft_bot_accel as mb
from minecraft_bot.codec import Writer, varint
from minecraft_bot.protocol.v763.packets.play.serverbound import (
    chat_command,
)

bot = mb.Bot.offline("172.26.160.1", 25565, "RawBot")
await bot.connect()
try:
    cmd = chat_command.ChatCommand(
        command="say hello",
        timestamp=int(time.time() * 1000),
        salt=0,
        argument_signatures=(),
        message_count=0,
        acknowledged=b"\x00" * 3,
    )
    w = Writer()
    varint.write(cmd.packet_id(), w)
    chat_command.encode(cmd, w)
    await bot.send_raw(w.bytes())
finally:
    await bot.disconnect()
```

## Inspect the World cache

```python
import minecraft_bot_accel as mb

bot = mb.Bot.offline("172.26.160.1", 25565, "Inspector")
await bot.connect()
try:
    await asyncio.sleep(2)
    w = bot.world
    print(f"loaded chunks: {w.loaded_chunk_count()}")
    pos = await bot.position()
    x, y, z = int(pos[0]), int(pos[1]), int(pos[2])
    for dy in [-1, 0, 1, 2]:
        name = w.get_block_name(x, y + dy, z)
        solid = w.is_solid(x, y + dy, z)
        print(f"  ({x},{y+dy},{z}): {name} solid={solid}")
finally:
    await bot.disconnect()
```

## Run the physics tick offline

Both backends expose a pure-function `physics.tick(state, intent,
world, *, in_water=False, in_lava=False)`. Use it to simulate
movement without a connection.

```python
from minecraft_bot.physics import PhysicsState, PhysicsIntent, tick

class FloorWorld:
    def is_solid(self, x, y, z):
        return y == 0

state = PhysicsState(x=0.5, y=5.0, z=0.5)
intent = PhysicsIntent(dx=1.0, sprint=True)
for _ in range(20):
    state = tick(state, intent, FloorWorld())
print(state)
```

Accel batched tick:

```python
from minecraft_bot_accel.physics import PhysicsState, PhysicsIntent, tick_n
from minecraft_bot_accel.world import World

state = PhysicsState(x=0.5, y=5.0, z=0.5)
intent = PhysicsIntent(dx=1.0, sprint=True)
world = World()
# (load chunks into `world` so the tick has a floor to land on)
state = tick_n(state, intent, world, 20)
print(state)
```

## Run the A* pathfinder offline

```python
from minecraft_bot.pathfinding import find_path

# Synthesise a flat-floor World, find a path from (0, 1, 0) to (10, 1, 0).
path = find_path(world, (0, 1, 0), (10, 1, 0), max_fall=3)
print(f"path of {len(path.nodes)} nodes, cost {path.cost:.2f}")
```

Accel takes the same World object and signature:

```python
from minecraft_bot_accel.pathfinding import find_path

path_nodes = find_path(bot.world, (0, 1, 0), (10, 1, 0), max_fall=3)
# Note: accel returns a list[tuple[int, int, int]] (no Path wrapper)
print(f"path of {len(path_nodes)} nodes")
```

## Hooks (Python reference)

```python
async with Bot.offline("172.26.160.1", 25565, "Listener") as bot:
    @bot.on_packet("chat_message")
    async def on_chat(pkt):
        print(f"saw chat: {pkt}")

    await asyncio.sleep(60)
```

## Hooks (accel)

`Bot.on_packet(packet_id, callback)` subscribes to any clientbound
packet by numeric id. The callback receives `(packet_id, body)`
where `body` is the raw payload bytes after the id varint. Decode
the body through the Python reference's typed decoders when you
need a structured view.

```python
import asyncio
import minecraft_bot_accel as mb
from minecraft_bot.codec import Reader
from minecraft_bot.protocol.v763.packets.play.clientbound.system_chat import (
    decode as decode_system_chat,
)

ID_SYSTEM_CHAT = 0x67  # play / clientbound

async def main():
    bot = mb.Bot.offline("172.26.160.1", 25565, "ChatListener")

    def on_chat(packet_id, body):
        pkt = decode_system_chat(Reader(body))
        print(f"chat: {pkt}")

    await bot.on_packet(ID_SYSTEM_CHAT, on_chat)
    await bot.connect()
    try:
        await asyncio.sleep(60)
    finally:
        await bot.disconnect()

asyncio.run(main())
```

Multiple callbacks per id are allowed and fire in registration order.
Callbacks run on the dispatcher task, so launch any long-running
work on a separate asyncio task (`asyncio.create_task(...)`) to
avoid blocking the loop. `Bot.clear_hooks()` drops every
registration.
