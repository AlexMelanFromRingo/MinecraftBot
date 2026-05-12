//! Status-effect tracker — Rust port of
//! `python/minecraft_bot/status_effects.py`.

use std::collections::HashMap;

use parking_lot::RwLock;

/// Vanilla `entity_effect` flag bits.
pub const FLAG_AMBIENT: u8 = 0x01;
/// Vanilla `entity_effect` flag bits.
pub const FLAG_SHOW_PARTICLES: u8 = 0x02;
/// Vanilla `entity_effect` flag bits.
pub const FLAG_SHOW_ICON: u8 = 0x04;

/// Subset of 1.20.1 effect registry IDs → canonical names.
pub fn effect_name(id: i32) -> Option<&'static str> {
    Some(match id {
        1 => "speed",
        2 => "slowness",
        3 => "haste",
        4 => "mining_fatigue",
        5 => "strength",
        6 => "instant_health",
        7 => "instant_damage",
        8 => "jump_boost",
        9 => "nausea",
        10 => "regeneration",
        11 => "resistance",
        12 => "fire_resistance",
        13 => "water_breathing",
        14 => "invisibility",
        15 => "blindness",
        16 => "night_vision",
        17 => "hunger",
        18 => "weakness",
        19 => "poison",
        20 => "wither",
        21 => "health_boost",
        22 => "absorption",
        23 => "saturation",
        24 => "glowing",
        25 => "levitation",
        26 => "luck",
        27 => "unluck",
        28 => "slow_falling",
        29 => "conduit_power",
        30 => "dolphins_grace",
        31 => "bad_omen",
        32 => "hero_of_the_village",
        33 => "darkness",
        _ => return None,
    })
}

/// Reverse map: canonical name → registry id.
pub fn effect_id(name: &str) -> Option<i32> {
    Some(match name {
        "speed" => 1,
        "slowness" => 2,
        "haste" => 3,
        "mining_fatigue" => 4,
        "strength" => 5,
        "instant_health" => 6,
        "instant_damage" => 7,
        "jump_boost" => 8,
        "nausea" => 9,
        "regeneration" => 10,
        "resistance" => 11,
        "fire_resistance" => 12,
        "water_breathing" => 13,
        "invisibility" => 14,
        "blindness" => 15,
        "night_vision" => 16,
        "hunger" => 17,
        "weakness" => 18,
        "poison" => 19,
        "wither" => 20,
        "health_boost" => 21,
        "absorption" => 22,
        "saturation" => 23,
        "glowing" => 24,
        "levitation" => 25,
        "luck" => 26,
        "unluck" => 27,
        "slow_falling" => 28,
        "conduit_power" => 29,
        "dolphins_grace" => 30,
        "bad_omen" => 31,
        "hero_of_the_village" => 32,
        "darkness" => 33,
        _ => return None,
    })
}

/// One active status effect on the bot.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct EffectEntry {
    /// Registry id.
    pub id: i32,
    /// `0 = level I`, `1 = level II`, …
    pub amplifier: i32,
    /// Remaining ticks; `-1 = infinite`.
    pub duration_ticks: i32,
    /// Ambient (beacon-applied) effect.
    pub is_ambient: bool,
    /// Show particle trail.
    pub show_particles: bool,
    /// Show icon in HUD.
    pub show_icon: bool,
}

impl EffectEntry {
    /// Canonical name (or `"effect_{id}"` for unknown registry ids).
    pub fn name(&self) -> String {
        match effect_name(self.id) {
            Some(n) => n.to_string(),
            None => format!("effect_{}", self.id),
        }
    }

    /// Display level (`amplifier + 1`).
    pub fn level(&self) -> i32 {
        self.amplifier + 1
    }
}

/// Mutable per-bot tracker of active effects.
pub struct StatusEffects {
    inner: RwLock<HashMap<i32, EffectEntry>>,
    bot_eid: RwLock<Option<i32>>,
}

impl StatusEffects {
    /// Construct an empty tracker.
    pub fn new() -> Self {
        Self {
            inner: RwLock::new(HashMap::new()),
            bot_eid: RwLock::new(None),
        }
    }

    /// Set the bot's entity id for filtering packets.
    pub fn set_bot_eid(&self, eid: Option<i32>) {
        *self.bot_eid.write() = eid;
    }

    /// Number of active effects.
    pub fn len(&self) -> usize {
        self.inner.read().len()
    }

    /// `true` iff no active effects.
    pub fn is_empty(&self) -> bool {
        self.inner.read().is_empty()
    }

    /// Handle a clientbound `entity_effect` packet.
    pub fn on_entity_effect(
        &self,
        entity_id: i32,
        effect_id: i32,
        amplifier: i32,
        duration: i32,
        flags: u8,
    ) {
        let bot = *self.bot_eid.read();
        if let Some(b) = bot {
            if entity_id != b {
                return;
            }
        }
        self.inner.write().insert(
            effect_id,
            EffectEntry {
                id: effect_id,
                amplifier,
                duration_ticks: duration,
                is_ambient: (flags & FLAG_AMBIENT) != 0,
                show_particles: (flags & FLAG_SHOW_PARTICLES) != 0,
                show_icon: (flags & FLAG_SHOW_ICON) != 0,
            },
        );
    }

    /// Handle a clientbound `remove_entity_effect` packet.
    pub fn on_remove_entity_effect(&self, entity_id: i32, effect_id: i32) {
        let bot = *self.bot_eid.read();
        if let Some(b) = bot {
            if entity_id != b {
                return;
            }
        }
        self.inner.write().remove(&effect_id);
    }

    /// Predicate: bot is currently under the named effect.
    pub fn has_effect_by_name(&self, name: &str) -> bool {
        match effect_id(name) {
            Some(id) => self.inner.read().contains_key(&id),
            None => false,
        }
    }

    /// Predicate: bot is currently under effect `id`.
    pub fn has_effect_by_id(&self, id: i32) -> bool {
        self.inner.read().contains_key(&id)
    }

    /// Get the entry for `id` if active.
    pub fn get_by_id(&self, id: i32) -> Option<EffectEntry> {
        self.inner.read().get(&id).copied()
    }

    /// Get the entry for the named effect if active.
    pub fn get_by_name(&self, name: &str) -> Option<EffectEntry> {
        let id = effect_id(name)?;
        self.get_by_id(id)
    }

    /// All currently-active effects, in arbitrary order.
    pub fn active_effects(&self) -> Vec<EffectEntry> {
        self.inner.read().values().copied().collect()
    }
}

impl Default for StatusEffects {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn name_lookup_roundtrips() {
        assert_eq!(effect_name(1), Some("speed"));
        assert_eq!(effect_id("speed"), Some(1));
        assert_eq!(effect_name(99), None);
        assert_eq!(effect_id("not-a-real-effect"), None);
    }

    #[test]
    fn entry_name_fallback_for_unknown_id() {
        let e = EffectEntry {
            id: 999,
            amplifier: 0,
            duration_ticks: 100,
            is_ambient: false,
            show_particles: true,
            show_icon: true,
        };
        assert_eq!(e.name(), "effect_999");
        assert_eq!(e.level(), 1);
    }

    #[test]
    fn tracker_filters_by_bot_eid() {
        let s = StatusEffects::new();
        s.set_bot_eid(Some(42));
        // Other entity's effect ignored.
        s.on_entity_effect(7, 1, 0, 100, FLAG_SHOW_PARTICLES);
        assert!(s.is_empty());
        // Bot's own effect tracked.
        s.on_entity_effect(42, 1, 0, 100, FLAG_SHOW_PARTICLES);
        assert!(s.has_effect_by_name("speed"));
        assert_eq!(s.len(), 1);
        // Remove for other entity does nothing.
        s.on_remove_entity_effect(7, 1);
        assert!(s.has_effect_by_name("speed"));
        // Remove for bot itself drops the entry.
        s.on_remove_entity_effect(42, 1);
        assert!(s.is_empty());
    }
}
