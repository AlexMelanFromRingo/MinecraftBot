//! Container methods for [`Bot`]: open_block_container, open_chest,
//! open_furnace, open_crafting_table, close_container, craft.
//! Mirrors `python/minecraft_bot/bot.py:1026-1230`.
//!
//! 004 Group G (T058..T064). MVP scope: open_* + close_container send
//! the right packets, craft places ingredients via click_slot sequences.
//! Full container handshake (await OpenScreen + WindowItems) is
//! simplified to a fixed delay — the dispatcher updates InventoryState
//! when the packets arrive, so subsequent reads see the right state.

use std::time::Duration;

use super::Bot;
use crate::errors::ProtocolError;
use crate::protocol::v763::packets::play::serverbound::close_window::CloseWindow;

impl Bot {
    /// Right-click the block at `(x, y, z)` to open its container UI.
    /// Returns the new window_id (or 0 if no window opened yet).
    pub async fn open_block_container(
        &self,
        x: i32,
        y: i32,
        z: i32,
        timeout: Duration,
    ) -> Result<u8, ProtocolError> {
        // Aim at the block, then use_item (which delegates to a
        // right-click). The server replies with OpenScreen + WindowItems
        // which the dispatcher picks up to populate InventoryState.
        self.look_at(x as f64 + 0.5, y as f64 + 0.5, z as f64 + 0.5)
            .await?;
        self.use_item(0).await?;
        // Wait up to `timeout` for the dispatcher to set window_id.
        let deadline = std::time::Instant::now() + timeout;
        while std::time::Instant::now() < deadline {
            let wid = self.inventory.lock().await.window_id;
            if wid != 0 {
                return Ok(wid);
            }
            tokio::time::sleep(Duration::from_millis(50)).await;
        }
        Ok(0)
    }

    /// Open a chest at `(x, y, z)`.
    pub async fn open_chest(
        &self,
        x: i32,
        y: i32,
        z: i32,
        timeout: Duration,
    ) -> Result<u8, ProtocolError> {
        self.open_block_container(x, y, z, timeout).await
    }

    /// Open a furnace at `(x, y, z)`.
    pub async fn open_furnace(
        &self,
        x: i32,
        y: i32,
        z: i32,
        timeout: Duration,
    ) -> Result<u8, ProtocolError> {
        self.open_block_container(x, y, z, timeout).await
    }

    /// Open a crafting table at `(x, y, z)`.
    pub async fn open_crafting_table(
        &self,
        x: i32,
        y: i32,
        z: i32,
        timeout: Duration,
    ) -> Result<u8, ProtocolError> {
        self.open_block_container(x, y, z, timeout).await
    }

    /// Close the currently-open container. No-op if no window is open.
    pub async fn close_container(&self) -> Result<(), ProtocolError> {
        let wid = {
            let inv = self.inventory.lock().await;
            inv.window_id
        };
        if wid == 0 {
            return Ok(());
        }
        self.connection
            .send(&CloseWindow { window_id: wid })
            .await?;
        // Mirror state locally; server doesn't echo a close.
        let mut inv = self.inventory.lock().await;
        inv.apply_close_window();
        Ok(())
    }

    /// Craft using a 3x3 crafting table at `(x, y, z)`.
    ///
    /// `recipe` is a 9-element row-major grid of `Option<String>`
    /// Minecraft item-ids (e.g. `Some("minecraft:oak_planks")` or
    /// `None`). Plays the click sequence per Python's algorithm:
    /// open table, place each ingredient via pick-up + put-down,
    /// shift-click the result slot `repeat` times.
    pub async fn craft(
        &self,
        recipe: [Option<String>; 9],
        x: i32,
        y: i32,
        z: i32,
        repeat: u32,
        timeout: Duration,
    ) -> Result<i32, ProtocolError> {
        let wid = self.open_crafting_table(x, y, z, timeout).await?;
        if wid == 0 {
            return Err(ProtocolError::DecodeError(
                "craft: crafting table did not open".into(),
            ));
        }

        let mut total: i32 = 0;
        for _ in 0..repeat {
            // For each non-None grid cell, find the ingredient in
            // player_slots, pick it up, place into the crafting grid
            // slot (1..9 on the crafting table window).
            for (i, cell) in recipe.iter().enumerate() {
                let Some(name) = cell else {
                    continue;
                };
                let src = match self.find_item(name).await {
                    Some(idx) => idx as i16,
                    None => {
                        return Err(ProtocolError::DecodeError(format!(
                            "craft: ingredient {name} not in inventory"
                        )));
                    }
                };
                let dst = (i + 1) as i16; // grid slot
                self.click_slot(src, "left", 0, Some(wid)).await?;
                self.click_slot(dst, "left", 0, Some(wid)).await?;
            }
            // Snapshot result slot count *before* shift-click; the
            // difference after the click is the exact output count
            // for this iteration. SetSlot from the server updates the
            // slot to 0 (or remaining stack) within ~50ms.
            let before = self
                .inventory
                .lock()
                .await
                .container_slots
                .first()
                .and_then(|s| s.clone())
                .map(|s| s.count as i32)
                .unwrap_or(0);
            self.quick_move(0, Some(wid)).await?;
            tokio::time::sleep(Duration::from_millis(100)).await;
            let after = self
                .inventory
                .lock()
                .await
                .container_slots
                .first()
                .and_then(|s| s.clone())
                .map(|s| s.count as i32)
                .unwrap_or(0);
            // The shift-click takes the full stack and produces
            // `before` items (if the recipe makes 1 per craft) or
            // `before * (max_stack / ingredient_count)` etc. For
            // accuracy we report `(before - after).max(before)`
            // which lands at `before` for the common case.
            total += (before - after).max(before);
        }
        self.close_container().await?;
        Ok(total)
    }
}
