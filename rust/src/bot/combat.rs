//! Combat and interaction methods for [`Bot`]: attack, interact_entity,
//! use_item. Mirrors `python/minecraft_bot/bot.py:691-715`.
//!
//! 004 Group C (T032).

use super::Bot;
use crate::errors::ProtocolError;
use crate::protocol::v763::packets::play::serverbound::arm_animation::ArmAnimation;
use crate::protocol::v763::packets::play::serverbound::use_entity::UseEntity;
use crate::protocol::v763::packets::play::serverbound::use_item::UseItem;

/// UseEntity action codes (Mojang protocol).
const USE_ENTITY_INTERACT: i32 = 0;
const USE_ENTITY_ATTACK: i32 = 1;

impl Bot {
    /// Attack the entity `eid`. Sends `UseEntity(action=attack)`
    /// followed by an arm swing on the main hand. Mirrors Python's
    /// `attack` (acquires the action slot, sends both packets in
    /// order, captures the bot's current sneak state).
    pub async fn attack(&self, eid: i32) -> Result<(), ProtocolError> {
        let sneaking = self.state.lock().await.is_sneaking;
        self.connection
            .send(&UseEntity {
                target: eid,
                mouse: USE_ENTITY_ATTACK,
                x: None,
                y: None,
                z: None,
                hand: None,
                sneaking,
            })
            .await?;
        self.connection.send(&ArmAnimation { hand: 0 }).await
    }

    /// Right-click / interact with entity `eid`. `hand` is `0` for
    /// main, `1` for off. Mirrors Python's `interact_entity`.
    pub async fn interact_entity(&self, eid: i32, hand: i32) -> Result<(), ProtocolError> {
        let sneaking = self.state.lock().await.is_sneaking;
        self.connection
            .send(&UseEntity {
                target: eid,
                mouse: USE_ENTITY_INTERACT,
                x: None,
                y: None,
                z: None,
                hand: Some(hand),
                sneaking,
            })
            .await
    }

    /// Right-click with the currently-held item (e.g. eat, drink, place
    /// torch). `hand` is `0` for main, `1` for off. Mirrors Python's
    /// `use_item`.
    pub async fn use_item(&self, hand: i32) -> Result<(), ProtocolError> {
        self.connection
            .send(&UseItem { hand, sequence: 0 })
            .await
    }
}
