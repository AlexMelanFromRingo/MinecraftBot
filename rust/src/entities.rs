//! Entity tracker — minimal port of `python/minecraft_bot/entities/`.
//!
//! Tracks entities by `entity_id`; updated by spawn/destroy packets.
//! Full metadata-schema decode is deferred — the tracker stores the
//! identity + position + velocity scalars.

use std::collections::HashMap;

use parking_lot::RwLock;

/// One tracked entity.
#[derive(Debug, Clone, PartialEq)]
pub struct Entity {
    /// Server-assigned numeric id.
    pub entity_id: i32,
    /// Mojang UUID (16 bytes).
    pub uuid: [u8; 16],
    /// Type registry id (`minecraft:cow` etc.).
    pub type_id: i32,
    /// X.
    pub x: f64,
    /// Y.
    pub y: f64,
    /// Z.
    pub z: f64,
    /// Yaw in degrees.
    pub yaw: f32,
    /// Pitch in degrees.
    pub pitch: f32,
    /// Velocity x (blocks/tick × 8000).
    pub vx: i16,
    /// Velocity y.
    pub vy: i16,
    /// Velocity z.
    pub vz: i16,
    /// Optional health (only known after first metadata update).
    pub health: Option<f32>,
}

/// In-memory entity tracker.
pub struct EntityTracker {
    by_id: RwLock<HashMap<i32, Entity>>,
}

impl EntityTracker {
    /// New empty tracker.
    pub fn new() -> Self {
        Self {
            by_id: RwLock::new(HashMap::new()),
        }
    }

    /// Insert / replace an entity record.
    pub fn add(&self, e: Entity) {
        self.by_id.write().insert(e.entity_id, e);
    }

    /// Remove an entity (server-sent `entity_destroy`).
    pub fn remove(&self, id: i32) {
        self.by_id.write().remove(&id);
    }

    /// Look up by id.
    pub fn get(&self, id: i32) -> Option<Entity> {
        self.by_id.read().get(&id).cloned()
    }

    /// All tracked entities.
    pub fn all(&self) -> Vec<Entity> {
        self.by_id.read().values().cloned().collect()
    }

    /// Number of tracked entities.
    pub fn len(&self) -> usize {
        self.by_id.read().len()
    }

    /// `true` iff no entities tracked.
    pub fn is_empty(&self) -> bool {
        self.by_id.read().is_empty()
    }

    /// Drop all entities (called on respawn / dimension change).
    pub fn clear(&self) {
        self.by_id.write().clear();
    }

    /// All entities within Euclidean `radius` of `origin`, sorted
    /// ascending by distance. Mirrors Python `entities.nearby_entities`.
    pub fn nearby_entities(&self, origin: (f64, f64, f64), radius: f64) -> Vec<Entity> {
        let r2 = radius * radius;
        let (ox, oy, oz) = origin;
        let mut out: Vec<(f64, Entity)> = self
            .by_id
            .read()
            .values()
            .filter_map(|e| {
                let d2 = sq(e.x - ox) + sq(e.y - oy) + sq(e.z - oz);
                if d2 <= r2 { Some((d2, e.clone())) } else { None }
            })
            .collect();
        out.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());
        out.into_iter().map(|(_, e)| e).collect()
    }

    /// All player entities (`type_id == player_type_id`) within
    /// `radius` of `origin`, sorted by distance. The player type
    /// id is 124 in v763.
    pub fn nearby_players(&self, origin: (f64, f64, f64), radius: f64) -> Vec<Entity> {
        const PLAYER_TYPE_ID: i32 = 124;
        self.nearby_entities(origin, radius)
            .into_iter()
            .filter(|e| e.type_id == PLAYER_TYPE_ID)
            .collect()
    }

    /// Euclidean distance from `origin` to entity `id`. `None` iff
    /// the entity is not tracked.
    pub fn distance_to(&self, id: i32, origin: (f64, f64, f64)) -> Option<f64> {
        let e = self.by_id.read().get(&id).cloned()?;
        let (ox, oy, oz) = origin;
        Some((sq(e.x - ox) + sq(e.y - oy) + sq(e.z - oz)).sqrt())
    }
}

#[inline]
fn sq(v: f64) -> f64 {
    v * v
}

impl Default for EntityTracker {
    fn default() -> Self {
        Self::new()
    }
}
