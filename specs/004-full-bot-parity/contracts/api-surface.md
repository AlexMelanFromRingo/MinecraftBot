# Contract: Bot API Surface Across Three Backends

**Phase**: 1 — Design & Contracts
**Feature**: [../spec.md](../spec.md)

This contract is the **authoritative method-by-method specification** for the `Bot` surface that must exist on all three backends after 004. Every row maps a Python reference symbol to its Rust crate equivalent and its accel `#[pymethods]` exposure. Parity tests (FR-046..FR-048) machine-check this table against the actual code.

## Reading the table

- **Python signature** is canonical. The Rust `async fn` returns the same value (modulo Python `int` -> Rust `i32/i64` mapping per item).
- **Accel form** is what Python users see when they `import minecraft_bot_accel`. "sync property" means `bot.x` (no parens, no await); "async method" means `await bot.x()`.
- **Mutation**: `INV` rows acquire the inventory mutex (R-2).
- **Live**: rows marked `LIVE` need a corresponding `cargo test --features live-smoke` test.

## State accessors (sync properties on accel)

| # | Python | Rust | Accel | Mutation | Live |
|---|---|---|---|---|---|
| 1 | `bot.x: float` | `async fn x(&self) -> f64` | `#[getter] x: f64` | - | - |
| 2 | `bot.y: float` | `async fn y(&self) -> f64` | `#[getter] y: f64` | - | - |
| 3 | `bot.z: float` | `async fn z(&self) -> f64` | `#[getter] z: f64` | - | - |
| 4 | `bot.yaw: float` | `async fn yaw(&self) -> f32` | `#[getter] yaw: f32` | - | - |
| 5 | `bot.pitch: float` | `async fn pitch(&self) -> f32` | `#[getter] pitch: f32` | - | - |
| 6 | `bot.on_ground: bool` | `async fn on_ground(&self) -> bool` | `#[getter] on_ground: bool` | - | - |
| 7 | `bot.health: float` | `async fn health(&self) -> f32` | `#[getter] health: f32` | - | - |
| 8 | `bot.food: int` | `async fn food(&self) -> i32` | `#[getter] food: i32` | - | - |
| 9 | `bot.saturation: float` | `async fn saturation(&self) -> f32` | `#[getter] saturation: f32` | - | - |
| 10 | `bot.is_dead: bool` | `async fn is_dead(&self) -> bool` | `#[getter] is_dead: bool` | - | - |
| 11 | `bot.xp_level: int` | `async fn xp_level(&self) -> i32` | `#[getter] xp_level: i32` | - | - |
| 12 | `bot.xp_total: int` | `async fn xp_total(&self) -> i32` | `#[getter] xp_total: i32` | - | - |
| 13 | `bot.game_mode: int \| None` | `async fn game_mode(&self) -> Option<u8>` | `#[getter] game_mode: Option<u8>` | - | - |
| 14 | `bot.held_slot: int` | `async fn held_slot(&self) -> u8` | `#[getter] held_slot: u8` | - | - |
| 15 | `bot.entity_id: int \| None` | `async fn entity_id(&self) -> Option<i32>` | `#[getter] entity_id: Option<i32>` | - | - |
| 16 | `bot.world_name: str \| None` | `async fn world_name(&self) -> Option<String>` | `#[getter] world_name: Option<String>` | - | - |
| 17 | `bot.dimension: str \| None` | `async fn dimension(&self) -> Option<String>` | `#[getter] dimension: Option<String>` | - | - |
| 18 | `bot.position: tuple[float, float, float]` | `async fn position(&self) -> (f64, f64, f64)` | `#[getter] position: (f64, f64, f64)` | - | - |

## Movement and orientation

| # | Python | Rust | Accel | Mutation | Live |
|---|---|---|---|---|---|
| 19 | `async bot.look_at(x, y, z)` | `async fn look_at(&self, x: f64, y: f64, z: f64) -> Result<()>` | `async fn look_at(x, y, z)` | - | LIVE |
| 20 | `async bot.jump()` | `async fn jump(&self) -> Result<()>` | `async fn jump()` | - | LIVE |
| 21 | `bot.sneak(enabled: bool)` | `async fn sneak(&self, enabled: bool) -> Result<()>` | `async fn sneak(enabled)` | - | LIVE |
| 22 | `bot.sprint(enabled: bool)` | `async fn sprint(&self, enabled: bool) -> Result<()>` | `async fn sprint(enabled)` | - | LIVE |
| 23 | `async bot.swing_arm(hand: int = 0)` | `async fn swing_arm(&self, hand: u8) -> Result<()>` | `async fn swing_arm(hand=0)` | - | LIVE |
| 24 | `async bot.walk_to(x, y, z, timeout=30.0)` | (exists in 003) | (exists in 003) | - | - |

## Combat and interaction

| # | Python | Rust | Accel | Mutation | Live |
|---|---|---|---|---|---|
| 25 | `async bot.attack(eid: int)` | `async fn attack(&self, eid: i32) -> Result<()>` | `async fn attack(eid)` | - | LIVE |
| 26 | `async bot.interact_entity(eid: int, *, hand: int = 0)` | `async fn interact_entity(&self, eid: i32, hand: u8) -> Result<()>` | `async fn interact_entity(eid, *, hand=0)` | - | LIVE |
| 27 | `async bot.use_item(hand: int = 0)` | `async fn use_item(&self, hand: u8) -> Result<()>` | `async fn use_item(hand=0)` | - | LIVE |

## World query (sync methods on accel — read-only)

| # | Python | Rust | Accel | Mutation | Live |
|---|---|---|---|---|---|
| 28 | `bot.find_blocks_nearby(filter, radius=8, limit=64)` | `fn find_blocks_nearby(&self, filter: impl Fn(u32) -> bool, radius: i32, limit: usize) -> Vec<BlockPos>` | `fn find_blocks_nearby(filter, radius=8, limit=64) -> list[tuple]` | - | - |
| 29 | `bot.nearby_entities(*, radius=32.0)` | `fn nearby_entities(&self, radius: f64) -> Vec<EntityRef>` | `fn nearby_entities(*, radius=32.0) -> list[EntityRef]` | - | - |
| 30 | `bot.nearby_players(*, radius=32.0)` | `fn nearby_players(&self, radius: f64) -> Vec<EntityRef>` | `fn nearby_players(*, radius=32.0) -> list[EntityRef]` | - | - |
| 31 | `bot.distance_to(eid: int) -> float \| None` | `fn distance_to(&self, eid: i32) -> Option<f64>` | `fn distance_to(eid) -> Optional[float]` | - | - |
| 32 | `bot.raycast(*, max_distance=32.0)` | `fn raycast(&self, max_distance: f64) -> Option<(BlockPos, BlockFace)>` | `fn raycast(*, max_distance=32.0) -> Optional[tuple]` | - | - |
| 33 | `bot.scan_volume(*, radius=8, include_air=False)` | `fn scan_volume(&self, radius: i32, include_air: bool) -> Vec<(BlockPos, u32)>` | `fn scan_volume(*, radius=8, include_air=False) -> list[tuple]` | - | - |
| 34 | `bot.voxel_grid(*, radius=4)` | `fn voxel_grid(&self, radius: i32) -> (Vec<u16>, (usize, usize, usize))` | `fn voxel_grid(*, radius=4) -> list[list[list[int]]]` | - | - |
| 35 | `bot.chunks_around(*, radius_chunks=2)` | `fn chunks_around(&self, radius_chunks: i32) -> Vec<(i32, i32)>` | `fn chunks_around(*, radius_chunks=2) -> list[tuple]` | - | - |
| 36 | `bot.world_map_3d(*, radius_xz=16, radius_y=None)` | `fn world_map_3d(&self, radius_xz: i32, radius_y: Option<i32>) -> (Vec<u16>, (usize, usize, usize))` | `fn world_map_3d(*, radius_xz=16, radius_y=None) -> list[list[list[int]]]` | - | - |

## Observation

| # | Python | Rust | Accel | Mutation | Live |
|---|---|---|---|---|---|
| 37 | `bot.snapshot(*, nearby_radius=32.0)` | `fn snapshot(&self, nearby_radius: f64) -> BotSnapshot` | `fn snapshot(*, nearby_radius=32.0) -> BotSnapshot` | - | - |
| 38 | `bot.observation(...)` | `fn observation(&self) -> Observation` | `fn observation() -> Observation` | - | - |

## Inventory (writes acquire `inventory_lock`)

| # | Python | Rust | Accel | Mutation | Live |
|---|---|---|---|---|---|
| 39 | `bot.held_item -> ItemSlot \| None` | `fn held_item(&self) -> Option<ItemSlot>` | `#[getter] held_item: Optional[ItemSlot]` | - | - |
| 40 | `bot.find_item(name: str)` | `fn find_item(&self, name: &str) -> Option<usize>` | `fn find_item(name) -> Optional[int]` | - | - |
| 41 | `bot.count_item(name: str)` | `fn count_item(&self, name: &str) -> u32` | `fn count_item(name) -> int` | - | - |
| 42 | `bot.iter_accessible_slots()` (new in 004) | `fn iter_accessible_slots(&self) -> impl Iterator<Item=(usize, Option<ItemSlot>)>` | `fn iter_accessible_slots() -> list[tuple[int, Optional[ItemSlot]]]` | - | - |
| 43 | `async bot.select_slot(hotbar_index: int)` | `async fn select_slot(&self, hotbar_index: u8) -> Result<()>` | `async fn select_slot(hotbar_index)` | - | LIVE |
| 44 | `async bot.drop_item(*, drop_stack=False)` | `async fn drop_item(&self, drop_stack: bool) -> Result<()>` | `async fn drop_item(*, drop_stack=False)` | INV | LIVE |
| 45 | `async bot.click_slot(window_id, slot, button, mode, items_changed=None)` | `async fn click_slot(&self, window_id: u8, slot: i16, button: u8, mode: u8, items_changed: Option<Vec<(u16, Option<ItemSlot>)>>) -> Result<()>` | `async fn click_slot(window_id, slot, button, mode, items_changed=None)` | INV | LIVE |
| 46 | `async bot.move_item(from_slot, to_slot, count=None)` | `async fn move_item(&self, from_slot: u16, to_slot: u16, count: Option<u8>) -> Result<()>` | `async fn move_item(from_slot, to_slot, count=None)` | INV | LIVE |
| 47 | `async bot.quick_move(slot: int)` | `async fn quick_move(&self, slot: u16) -> Result<()>` | `async fn quick_move(slot)` | INV | LIVE |
| 48 | `async bot.equip_armor(armor_slot: str, src_slot: int)` | `async fn equip_armor(&self, armor_slot: ArmorSlot, src_slot: u16) -> Result<()>` | `async fn equip_armor(armor_slot, src_slot)` | INV | LIVE |
| 49 | `async bot.unequip_armor(armor_slot: str, dst_slot: int)` | `async fn unequip_armor(&self, armor_slot: ArmorSlot, dst_slot: u16) -> Result<()>` | `async fn unequip_armor(armor_slot, dst_slot)` | INV | LIVE |
| 50 | `async bot.swap_to_offhand(src_slot: int)` | `async fn swap_to_offhand(&self, src_slot: u16) -> Result<()>` | `async fn swap_to_offhand(src_slot)` | INV | LIVE |

## Containers

| # | Python | Rust | Accel | Mutation | Live |
|---|---|---|---|---|---|
| 51 | `async bot.open_block_container(x, y, z, kind=None, *, timeout=5.0)` | `async fn open_block_container(&self, x: i32, y: i32, z: i32, kind: Option<ContainerKind>, timeout: Duration) -> Result<u8>` | `async fn open_block_container(x, y, z, kind=None, *, timeout=5.0) -> int` | INV | LIVE |
| 52 | `async bot.open_chest(x, y, z, **kw) -> int` | `async fn open_chest(&self, x: i32, y: i32, z: i32, timeout: Duration) -> Result<u8>` | `async fn open_chest(x, y, z, *, timeout=5.0) -> int` | INV | LIVE |
| 53 | `async bot.open_furnace(x, y, z, **kw) -> int` | `async fn open_furnace(&self, x: i32, y: i32, z: i32, timeout: Duration) -> Result<u8>` | `async fn open_furnace(x, y, z, *, timeout=5.0) -> int` | INV | LIVE |
| 54 | `async bot.open_crafting_table(x, y, z, **kw) -> int` | `async fn open_crafting_table(&self, x: i32, y: i32, z: i32, timeout: Duration) -> Result<u8>` | `async fn open_crafting_table(x, y, z, *, timeout=5.0) -> int` | INV | LIVE |
| 55 | `async bot.close_container()` | `async fn close_container(&self) -> Result<()>` | `async fn close_container()` | INV | LIVE |
| 56 | `async bot.craft(recipe, x, y, z, *, repeat=1, timeout=8.0) -> int` | `async fn craft(&self, recipe: [Option<String>; 9], x: i32, y: i32, z: i32, repeat: u32, timeout: Duration) -> Result<i32>` | `async fn craft(recipe, x, y, z, *, repeat=1, timeout=8.0) -> int` | INV | LIVE |

## High-level tasks

| # | Python | Rust | Accel | Mutation | Live |
|---|---|---|---|---|---|
| 57 | `async bot.dig(x, y, z, *, expected_block=None)` | `async fn dig(&self, x: i32, y: i32, z: i32, expected_block: Option<u32>) -> Result<()>` | `async fn dig(x, y, z, *, expected_block=None)` | - | LIVE |
| 58 | `async bot.eat(*, timeout=3.0)` | `async fn eat(&self, timeout: Duration) -> Result<()>` | `async fn eat(*, timeout=3.0)` | INV | LIVE |
| 59 | `async bot.follow(eid, *, distance=2.0, timeout=60.0)` | `async fn follow(&self, eid: i32, distance: f64, timeout: Duration) -> Result<()>` | `async fn follow(eid, *, distance=2.0, timeout=60.0)` | - | LIVE |
| 60 | `async bot.say(message: str)` | `async fn say(&self, message: &str) -> Result<()>` | `async fn say(message)` | - | LIVE |
| 61 | `async bot.chat(message)` (alias) | `async fn chat(&self, message: &str) -> Result<()>` | `async fn chat(message)` | - | LIVE |

## Behaviour trees

| # | Python | Rust | Accel |
|---|---|---|---|
| BT-1 | `class Selector(BehaviourNode)` | `pub struct Selector { children: Vec<Box<dyn Leaf>> }` impl Leaf | `#[pyclass] Selector` |
| BT-2 | `class Sequencer(BehaviourNode)` | `pub struct Sequencer { children: Vec<Box<dyn Leaf>> }` impl Leaf | `#[pyclass] Sequencer` |
| BT-3 | `class Inverter(BehaviourNode)` | `pub struct Inverter { child: Box<dyn Leaf> }` impl Leaf | `#[pyclass] Inverter` |
| BT-4 | `class Repeater(BehaviourNode)` | `pub struct Repeater { child: Box<dyn Leaf>, count: Option<u32> }` impl Leaf | `#[pyclass] Repeater` |
| BT-5 | `class WalkTo(BehaviourLeaf)` | `pub struct WalkTo { ... }` impl Leaf | `#[pyclass] WalkTo` |
| BT-6 | `class EatWhenHungry(BehaviourLeaf)` | `pub struct EatWhenHungry { threshold: u8 }` impl Leaf | `#[pyclass] EatWhenHungry` |
| BT-7 | `class FollowEntity(BehaviourLeaf)` | `pub struct FollowEntity { eid: i32, distance: f64 }` impl Leaf | `#[pyclass] FollowEntity` |
| BT-8 | `class AttackTarget(BehaviourLeaf)` | `pub struct AttackTarget { eid: i32 }` impl Leaf | `#[pyclass] AttackTarget` |
| BT-9 | `class BehaviourRunner` | `pub struct BehaviourRunner` | `#[pyclass] BehaviourRunner` |
| BT-10 | Python `tick(bot, ctx)` callable as leaf | `PyLeaf` adapter struct (not exposed to Rust users directly) | `Selector.new([custom_obj])` accepts any object with `async def tick(self, bot, ctx)` |

## Python-only allow-list

Names on `Bot` that intentionally exist **only** in Python (excluded from FR-046 introspection):

```python
PYTHON_ONLY_METHODS = {
    "_llm_chat_loop",        # llm_agent dependency, Python-only
    "_llm_observe",
    # add here with code-review when a method is intentionally Python-only
}
```

Anything else missing from accel's `Bot` fails the introspection test.
