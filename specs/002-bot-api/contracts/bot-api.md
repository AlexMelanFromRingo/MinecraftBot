# Contract: Bot API (Python)

**Date**: 2026-05-12
**Plan**: [../plan.md](../plan.md)

This is the **canonical, normative** Python public surface for the
Bot API. Every name in this file is part of the public API. Adding
fields/methods is a MINOR change; removing or renaming requires a
MAJOR version bump.

A future Rust mirror (milestone 003) tracks this contract; cross-
language drift is a bug.

---

## Top-level imports

```python
from minecraft_bot import (
    # existing from 001
    Connection,
    ProtocolError, ConnectionClosed, KickedByServer, ConnectionDropped,
    KeepAliveTimeout, PeerReset,
    V_1_20_1, ProtocolVersion,
    WireLog, WireLogEntry,

    # new in 002
    Bot,
    BotBusy,
    BotSnapshot,

    # event types
    ChatMessageEvent, EntityDamageEvent, EntityDeathEvent,
    ItemPickupEvent, InventoryChangeEvent, BlockBreakEvent,
    ContainerOpenEvent, ContainerCloseEvent,
    TeleportedEvent, InLavaEvent, DimensionChangedEvent,
    RespawnEvent,

    # food pickers
    BEST_SATURATION, WORST_FIRST, OLDEST_FIRST,
)
from minecraft_bot.entities import Entity
from minecraft_bot.entities.types import Sheep, Wolf, Horse, Villager, Creeper, Player, ItemEntity
from minecraft_bot.inventory import ItemSlot, Enchantment
from minecraft_bot.behaviour import (
    Selector, Sequence, Inverter, RepeatUntilFail, AlwaysSucceed,
    Condition, Action,
    WalkTo, AttackNearest, EatWhenHungry, FollowPlayer, DropItem, Say,
)
```

---

## `Bot` — construction and lifecycle

```python
class Bot:
    """High-level Minecraft bot built on top of a Connection."""

    def __init__(self, connection: Connection): ...

    @classmethod
    def offline(
        cls,
        host: str, port: int, username: str, *,
        version: ProtocolVersion = V_1_20_1,
        auto_reconnect: bool = False,
        wire_log: WireLog | None = None,
    ) -> "Bot":
        """Convenience factory: construct Connection.offline + Bot."""

    async def connect(self) -> None:
        """Open underlying Connection, wait for PLAY, start physics tick."""

    async def disconnect(self, reason: str | None = None) -> None:
        """Cancel physics tick; close underlying Connection."""

    async def __aenter__(self) -> "Bot": ...
    async def __aexit__(self, *exc) -> None: ...
```

### Properties (read-only)

```python
position: tuple[float, float, float]
yaw: float
pitch: float
health: float           # 0..20
food: int               # 0..20
saturation: float       # 0..5
game_mode: int          # 0=survival, 1=creative, 2=adventure, 3=spectator
is_dead: bool
xp_level: int
xp_total: int
held_slot: int          # 0..8 hotbar index
held_item: ItemSlot | None
entity_id: int | None
world_name: str | None
is_connected: bool
```

### Submodule accessors

```python
connection: Connection
world: World
entities: EntityTracker
inventory: InventoryTracker
status_effects: StatusEffects
```

---

## Movement APIs (movement slot)

```python
async def walk_to(
    self,
    x: int | float, y: int | float, z: int | float,
    *,
    timeout: float = 30.0,
    max_fall: int = 3,
    wait_for_slot: bool = False,
) -> None:
    """Navigate via A* to within 1 block of target. Holds movement
    slot. Raises NoPathFound / WalkTimeout / BotBusy."""

async def follow(
    self,
    entity_id: int, *,
    distance: float = 3.0,
    timeout: float = 60.0,
    wait_for_slot: bool = False,
) -> None: ...

async def swim_to(
    self,
    x: int | float, y: int | float, z: int | float, *,
    timeout: float = 30.0,
    wait_for_slot: bool = False,
) -> None: ...

async def fly_to(
    self,
    x: int | float, y: int | float, z: int | float, *,
    timeout: float = 30.0,
    wait_for_slot: bool = False,
) -> None:
    """Creative mode only. Straight-line flight."""

async def dig(
    self,
    x: int, y: int, z: int, *,
    tool: ItemSlot | None = None,
    wait_for_slot: bool = False,
) -> None:
    """Holds movement slot until block breaks (or 2× break-time
    timeout). Raises DigFailed / BotBusy."""
```

---

## Action APIs (action slot)

```python
async def look_at(self, x: float, y: float, z: float) -> None: ...
async def look_by_vector(self, dx: float, dy: float, dz: float) -> None: ...

async def attack(self, entity_id: int) -> None: ...
async def interact_entity(self, entity_id: int) -> None: ...

async def swing_arm(self, *, hand: int = 0) -> None: ...
async def use_item(self, *, hand: int = 0) -> None: ...

async def select_slot(self, slot: int) -> None:
    """Hotbar slot 0..8."""

def sneak(self, value: bool) -> None: ...
def sprint(self, value: bool) -> None: ...

async def jump(self) -> None: ...

async def say(self, message: str) -> None: ...
async def command(self, slash_command: str) -> None: ...
```

---

## Container APIs (container slot)

```python
async def open_chest(self, x: int, y: int, z: int) -> "Container": ...
async def open_furnace(self, x: int, y: int, z: int) -> "Container": ...
async def open_crafting_table(self, x: int, y: int, z: int) -> "Container": ...
async def close_container(self) -> None: ...

async def craft(
    self,
    recipe_or_grid: str | list[list[str | None]],
    *, x: int, y: int, z: int,
) -> ItemSlot: ...

async def smelt(
    self,
    input_item: str, fuel_item: str,
    *, x: int, y: int, z: int,
) -> ItemSlot: ...
```

---

## Inventory APIs

`bot.inventory` is an `InventoryTracker` instance with:

```python
def items(self) -> list[ItemSlot]: ...
def hotbar_items(self) -> list[ItemSlot | None]: ...
def container_items(self) -> list[ItemSlot | None]: ...
def find_item(self, name: str) -> int | None: ...
def count_item(self, name: str) -> int: ...

async def click_slot(self, slot: int, button: int, mode: int) -> None: ...
async def move_item(self, from_slot: int, to_slot: int) -> None: ...
async def drop_item(self, *, slot: int | None = None, full_stack: bool = False) -> None: ...
async def equip_armor(self, item_name: str) -> None: ...
async def unequip_armor(self, armor_slot_name: str) -> None: ...
async def swap_to_offhand(self, slot: int) -> None: ...
```

---

## Survival APIs

```python
def auto_eat(
    self, *,
    threshold: int = 15,
    eat_duration: float = 1.6,
    picker: Callable[[list[ItemSlot]], ItemSlot] | None = None,
) -> None: ...

def in_reach(self, x: float, y: float, z: float, *, max_dist: float = 4.5) -> bool: ...
```

`bot.status_effects`:

```python
def has_effect(self, name: str) -> bool: ...
def get_effect(self, name: str) -> EffectEntry | None: ...
```

---

## World queries

`bot.world` is a `World` instance:

```python
def get_block(self, x: int, y: int, z: int) -> int | None: ...
def get_block_name(self, x: int, y: int, z: int) -> str | None: ...
def is_solid(self, x: int, y: int, z: int) -> bool: ...
def is_navigable(self, x: int, y: int, z: int) -> bool: ...
def is_water(self, x: int, y: int, z: int) -> bool: ...
def find_blocks_nearby(self, name: str, radius: int, limit: int) -> list[tuple[int, int, int]]: ...
```

---

## Entity tracker

`bot.entities` is an `EntityTracker` instance:

```python
def nearby_entities(self, radius: float, type_filter: type | None = None) -> list[Entity]: ...
def nearby_players(self, radius: float) -> list[Player]: ...
def find_by_id(self, entity_id: int) -> Entity | None: ...
def distance_to(self, entity_id: int) -> float | None: ...
```

Individual Entity instances expose typed accessors per the per-type
subclass (e.g., `sheep.wool_color`, `wolf.collar_color`,
`horse.armor_item`, `villager.profession`, `creeper.is_charged`).

---

## Hooks & events

```python
@bot.on(EventType)
def handler(event: EventType): ...

# Or imperatively:
sub = bot.subscribe(EventType, handler)
bot.unsubscribe(sub)

events = bot.drain_events()    # all events since last drain
event = await bot.next_event(EventType, timeout=10.0)
```

Handlers may be sync or async. Async handlers run as `asyncio.create_task` from the decode loop; sync handlers run inline.

---

## Behaviour trees (optional submodule)

```python
from minecraft_bot.behaviour import Selector, Sequence, Condition, Action, WalkTo, EatWhenHungry, AttackNearest

tree = Selector([
    Sequence([Condition(lambda bot: bot.food < 10), EatWhenHungry()]),
    Sequence([Condition(lambda bot: bot.entities.nearby_entities(8, Hostile)), AttackNearest(Hostile)]),
    WalkTo(spawn.x, spawn.y, spawn.z),
])

await bot.behaviour.run(tree)   # loops until tree returns Success or Failure
```

---

## `BotSnapshot`

A frozen, picklable point-in-time view of the bot useful for
ML/RL observation pipelines.

```python
@dataclass(frozen=True, slots=True)
class BotSnapshot:
    position: tuple[float, float, float]
    yaw: float
    pitch: float
    health: float
    food: int
    saturation: float
    inventory: tuple[ItemSlot | None, ...]
    nearby_entities: tuple[Entity, ...]
    status_effects: tuple[EffectEntry, ...]

bot.snapshot() -> BotSnapshot
```

---

## Errors

```python
class BotBusy(ProtocolError): ...
class NoPathFound(ProtocolError): ...
class WalkTimeout(ProtocolError): ...
class DigFailed(ProtocolError): ...
class TargetLost(ProtocolError): ...
class ContainerClosed(ProtocolError): ...
class InventoryStateMismatch(ProtocolError): ...
class InVehicle(ProtocolError): ...
```

All extend the existing `ProtocolError` hierarchy from 001.

---

## Stability and evolution

- Adding new methods to Bot → MINOR.
- Adding new event types → MINOR (additive).
- Adding new entity subclasses → MINOR.
- Renaming any public method, removing any field on Bot or Entity →
  MAJOR.
- Changing the slot ownership of an existing method → MAJOR
  (subtle behaviour break for users who relied on composability).
