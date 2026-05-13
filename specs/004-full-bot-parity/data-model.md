# Data Model: Full Bot Parity

**Phase**: 1 — Design & Contracts
**Feature**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)
**Research**: [research.md](./research.md)

This document defines the entities, fields, relationships, and state transitions introduced by 004. Each entity has three forms in lockstep: a Python dataclass / class (the spec), a Rust struct (in the standalone crate), and an accel `#[pyclass]` wrapper. The three forms must serialise compatibly via the parity tests defined in FR-046..FR-048.

---

## BotState

**Owns**: All single-bot mutable state that lives across the network session. Mirrors the Python `Bot` instance attributes 1:1.

**Rust**:

```rust
pub struct BotState {
    pub entity_id: Option<i32>,
    pub position: Vec3,         // x, y, z (f64)
    pub yaw: f32,
    pub pitch: f32,
    pub on_ground: bool,
    pub velocity: Vec3,         // physics integration only; not sent on its own
    pub health: f32,            // 0..20
    pub food: i32,              // 0..20
    pub saturation: f32,
    pub xp_level: i32,
    pub xp_total: i32,
    pub game_mode: Option<u8>,
    pub held_slot: u8,          // 0..8 hotbar index
    pub world_name: Option<String>,
    pub dimension: Option<String>,
    pub is_sneaking: bool,
    pub is_sprinting: bool,
    pub is_dead: bool,          // derived from health <= 0
}
```

Held under `Arc<RwLock<BotState>>` on the `Bot` struct. Read via the accessor methods (FR-001); written by the packet dispatcher when state-altering packets arrive (login, set-health, set-experience, update-game-state, player-info).

**State transitions**:

- `entity_id`: None -> Some on `Login` packet receipt. Never resets.
- `position`: updated each physics tick from network corrections or local integration.
- `yaw/pitch`: updated by `look_at` and by `PlayerPositionAndLook` server packets.
- `is_sneaking/is_sprinting`: toggled by `sneak(true/false)` / `sprint(true/false)`; FR-004/FR-005 enforce idempotent no-op on same-value.
- `is_dead`: derived getter (`health <= 0.0`); not stored.

**Validation**: `health >= 0.0 && health <= 20.0`; `food >= 0 && food <= 20`. Out-of-range values are clamped, not rejected.

---

## InventoryState

**Owns**: Per-bot inventory tracking. From clarification Q5: dual-list model.

**Rust**:

```rust
pub struct InventoryState {
    pub player_slots: [Option<ItemSlot>; 46],
    pub container_slots: Vec<Option<ItemSlot>>,
    pub cursor: Option<ItemSlot>,
    pub window_id: u8,                  // 0 = player inventory window
    pub state_id: i32,                  // server's window state-id
    next_transaction_id: AtomicI32,
}
```

Player slot layout: 0 = crafting result, 1..4 = crafting grid, 5..8 = armor (helmet/chest/legs/boots), 9..35 = main inventory, 36..44 = hotbar, 45 = offhand. `container_slots` is populated only while a container window is open; cleared on `close_container`.

**State transitions**:

- `SetSlot(window_id=0, slot, item)` -> `player_slots[slot] = item`.
- `SetSlot(window_id=X, slot, item)` with X > 0 -> `container_slots[slot] = item` if slot is in container range, else `player_slots[slot - container_size]`.
- `WindowItems(window_id=0, items)` -> `player_slots = items`.
- `WindowItems(window_id=X, items)` -> `container_slots = items[0..container_size]`, `player_slots[9..45] = items[container_size..]` (the server resends the player inventory tail when a container is open).
- `OpenScreen(window_id=X, kind)` -> `window_id = X`, allocate `container_slots` to the right size for `kind`.
- `CloseWindow(window_id)` -> `window_id = 0`, `container_slots = vec![]`.

**Invariants** (from Q5):

- `held_item()`, `find_item()`, `count_item()` read **only** from `player_slots`.
- `iter_accessible_slots()` returns the derived merged view; never cached.
- `next_transaction_id` is monotonic per Bot; reused only after `WindowConfirmation` round-trip.

---

## ItemSlot

**Owns**: The item-in-a-slot value type.

**Rust**:

```rust
#[derive(Clone, PartialEq, Eq)]
pub struct ItemSlot {
    pub item_id: u32,           // numeric item id from items.json
    pub count: u8,
    pub nbt: Option<Vec<u8>>,   // raw NBT bytes; decoded on demand by helpers
}
```

Python equivalent: `python/minecraft_bot/inventory/item.py` `ItemSlot` dataclass.

**Helpers**:
- `ItemSlot::name(&self) -> &str` — resolves to Minecraft item name (`"minecraft:oak_planks"`).
- `ItemSlot::from_slot_data(s: &SlotData) -> Option<Self>` — converts from on-wire form.

---

## BotSnapshot

**Owns**: Frozen observation returned by `Bot::snapshot(nearby_radius)`. Same field set on all three backends. Mirrors `python/minecraft_bot/observation.py` `BotSnapshot` dataclass.

**Rust**:

```rust
#[derive(Clone)]
pub struct BotSnapshot {
    pub timestamp_ms: u64,
    pub position: Vec3,
    pub yaw: f32,
    pub pitch: f32,
    pub on_ground: bool,
    pub health: f32,
    pub food: i32,
    pub saturation: f32,
    pub held_item: Option<ItemSlot>,
    pub inventory_summary: Vec<(String, u32)>,  // item_name -> count
    pub nearby_entities: Vec<EntityRef>,
    pub nearby_blocks: Vec<(BlockPos, u32)>,    // pos -> state_id
}
```

Frozen by convention (no methods mutate); accel exposes as `#[pyclass(frozen)]`.

---

## Observation

**Owns**: Lightweight per-tick observation for AI loops. Mirrors `python/minecraft_bot/observation.py` `Observation`.

**Rust**:

```rust
#[derive(Clone)]
pub struct Observation {
    pub timestamp_ms: u64,
    pub position: Vec3,
    pub yaw: f32,
    pub pitch: f32,
    pub health: f32,
    pub food: i32,
    pub nearby_entities: Vec<EntityRef>,
}
```

Subset of `BotSnapshot`. No `nearby_blocks`, no `inventory_summary`.

---

## EntityRef

**Owns**: Read-only entity view for world-query methods.

**Rust**:

```rust
#[derive(Clone)]
pub struct EntityRef {
    pub eid: i32,
    pub entity_type: String,    // e.g. "minecraft:cow"
    pub position: Vec3,
    pub yaw: f32,
    pub pitch: f32,
    pub distance_from_bot: f64,
    pub is_player: bool,
    pub username: Option<String>,  // present iff is_player
}
```

Used by `nearby_entities`, `nearby_players`, `distance_to`, `snapshot`, `observation`. Sorted by `distance_from_bot` ascending in the returned `Vec`.

---

## NodeStatus

**Owns**: Behaviour-tree tick result enum. Canonical BT names per Q3.

**Rust**:

```rust
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum NodeStatus {
    Running,    // "tick me again next time"
    Success,
    Failure,
}
```

Python equivalent: `python/minecraft_bot/behaviour/nodes.py` `NodeStatus` enum.

---

## BehaviourValue + BehaviourCtx

**Owns**: Behaviour-tree shared context. Closed value enum per Q3 (no pyo3 in pure-Rust core).

**Rust**:

```rust
#[derive(Clone)]
pub enum BehaviourValue {
    Int(i64),
    Float(f64),
    Bool(bool),
    String(String),
    Bytes(Vec<u8>),
    Json(serde_json::Value),    // recursive fallback for nested dict/list
}

pub type BehaviourCtx =
    std::sync::Arc<parking_lot::RwLock<
        std::collections::HashMap<String, BehaviourValue>
    >>;
```

Accel layer converts to/from `Py<PyDict>` on each `PyLeaf::tick` entry/exit.

---

## Leaf (trait)

**Owns**: Behaviour-tree leaf contract.

**Rust**:

```rust
#[async_trait]
pub trait Leaf: Send + Sync {
    async fn tick(&mut self, bot: &Bot, ctx: &BehaviourCtx) -> NodeStatus;
    fn reset(&mut self) {}
}
```

Standard implementations: `WalkTo`, `EatWhenHungry`, `FollowEntity`, `AttackTarget`. Each mirrors the corresponding Python leaf in `python/minecraft_bot/behaviour/leaves.py`.

---

## BehaviourRunner

**Owns**: Top-level driver for running a tree on a Bot. Mirrors `python/minecraft_bot/behaviour/runner.py`.

**Rust**:

```rust
pub struct BehaviourRunner {
    pub tick_dt: Duration,      // typically 500ms
    cancel: Arc<tokio::sync::Notify>,
}

impl BehaviourRunner {
    pub async fn run(
        &self,
        root: Box<dyn Leaf>,
        bot: &Bot,
        ctx: BehaviourCtx,
        max_ticks: Option<u32>,
    ) -> Result<NodeStatus, BehaviourError>;
    pub fn cancel(&self);
}
```

Tick semantics: call `root.tick(bot, &ctx)`; if `Running`, sleep `tick_dt` and tick again; if `Success/Failure`, return. `cancel()` triggers `Notify` and the next `tick_dt` sleep returns `BehaviourError::Cancelled`.

---

## RecipeIndex

**Owns**: Pre-indexed `protocol-data/v763/recipes.json` for `craft` lookups (R-9).

**Rust**:

```rust
pub struct RecipeIndex {
    by_grid_hash: HashMap<u64, RecipeEntry>,
}

pub struct RecipeEntry {
    pub recipe_id: String,
    pub output_item: String,
    pub output_count: u32,
    pub grid_signature: [Option<String>; 9],  // for verification
}
```

Built once at first `Bot` instantiation; static via `OnceLock<RecipeIndex>`.

---

## FoodTable

**Owns**: Food-id -> (hunger_restore, saturation_restore) mapping (FR-045).

**Rust**:

```rust
pub struct FoodTable {
    by_item_id: HashMap<u32, FoodEntry>,
}

pub struct FoodEntry {
    pub hunger: u8,
    pub saturation: f32,
}
```

Built once at startup from `protocol-data/v763/items.json` (foods section). Static via `OnceLock<FoodTable>`.

---

## Entity relationships

```text
Bot ---owns---> Arc<RwLock<BotState>>
Bot ---owns---> Arc<RwLock<InventoryState>>
Bot ---owns---> Arc<RwLock<HashMap<i32, EntityRef>>>  // entity tracker (already in 003)
Bot ---owns---> Arc<Connection>                       // network (already in 003)
Bot ---owns---> Arc<RwLock<World>>                    // world cache (already in 003)
Bot ---uses---> &'static RecipeIndex (OnceLock)
Bot ---uses---> &'static FoodTable (OnceLock)

BehaviourRunner ---uses---> &Bot, BehaviourCtx
Leaf impls ---use---> &Bot, &BehaviourCtx
Selector / Sequencer ---own---> Vec<Box<dyn Leaf>>
```

The Python parity tests compare returned values shape-by-shape using PyO3's conversion (Vec3 -> tuple(f64, f64, f64), Vec -> list, HashMap -> dict).
