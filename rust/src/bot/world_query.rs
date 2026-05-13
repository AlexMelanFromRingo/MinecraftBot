//! World-query methods for [`Bot`]: find_blocks_nearby, raycast,
//! scan_volume, voxel_grid, chunks_around, world_map_3d,
//! nearby_entities, nearby_players, distance_to.
//!
//! Mirrors `python/minecraft_bot/bot.py:719-797`. All methods are
//! read-only against the World cache + entity tracker — they
//! acquire shared (read) locks only.
//!
//! 004 Group D (T036..T039).

use super::Bot;
use crate::entities::Entity;

/// Eye height above feet for raycast origin (matches Python ref
/// `bot.py:762`).
const EYE_HEIGHT: f64 = 1.62;

impl Bot {
    /// Find up to `limit` blocks named `name` within Chebyshev
    /// `radius` of the bot, sorted ascending by distance.
    pub async fn find_blocks_nearby(
        &self,
        name: &str,
        radius: i32,
        limit: usize,
    ) -> Vec<(i32, i32, i32)> {
        let pos = self.position().await;
        self.world.find_blocks_nearby(name, pos, radius, limit)
    }

    /// All tracked entities within Euclidean `radius`, sorted by
    /// distance.
    pub async fn nearby_entities(&self, radius: f64) -> Vec<Entity> {
        let pos = self.position().await;
        self.entities_tracker.nearby_entities(pos, radius)
    }

    /// All tracked player entities within `radius`.
    pub async fn nearby_players(&self, radius: f64) -> Vec<Entity> {
        let pos = self.position().await;
        self.entities_tracker.nearby_players(pos, radius)
    }

    /// Euclidean distance to the entity `eid`, or `None` if not tracked.
    pub async fn distance_to(&self, eid: i32) -> Option<f64> {
        let pos = self.position().await;
        self.entities_tracker.distance_to(eid, pos)
    }

    /// DDA raycast from the bot's eye along its look vector. Returns
    /// `Some((x, y, z, state_id, face))` for the first solid block,
    /// or `None` if nothing was hit within `max_distance`.
    pub async fn raycast(&self, max_distance: f64) -> Option<(i32, i32, i32, i32, u8)> {
        let (eye_x, eye_y, eye_z, yaw, pitch) = {
            let s = self.state.lock().await;
            (s.x, s.y + EYE_HEIGHT, s.z, s.yaw as f64, s.pitch as f64)
        };
        let (dx, dy, dz) = look_direction(yaw, pitch);
        dda_raycast(&self.world, eye_x, eye_y, eye_z, dx, dy, dz, max_distance)
    }

    /// Every block within Chebyshev `radius` of the bot. When
    /// `include_air` is false, air blocks are omitted. Returns
    /// `[(x, y, z, state_id), ...]` sorted by Chebyshev distance.
    pub async fn scan_volume(
        &self,
        radius: i32,
        include_air: bool,
    ) -> Vec<(i32, i32, i32, i32)> {
        let (bx, by, bz) = self.position().await;
        let cx0 = bx.floor() as i32;
        let cy0 = by.floor() as i32;
        let cz0 = bz.floor() as i32;
        let guard = self.world.query_guard();
        let mut out: Vec<(i32, (i32, i32, i32, i32))> = Vec::new();
        for dx in -radius..=radius {
            for dy in -radius..=radius {
                for dz in -radius..=radius {
                    let x = cx0 + dx;
                    let y = cy0 + dy;
                    let z = cz0 + dz;
                    let state_id = guard.get_block_id(x, y, z);
                    if !include_air && state_id == 0 {
                        continue;
                    }
                    let cheb = dx.abs().max(dy.abs()).max(dz.abs());
                    out.push((cheb, (x, y, z, state_id)));
                }
            }
        }
        out.sort_by_key(|(k, _)| *k);
        out.into_iter().map(|(_, v)| v).collect()
    }

    /// A 3-D cube of block-state ids around the bot. Returns
    /// `(flat_grid, side)` where `side = 2*radius + 1` and the
    /// grid is row-major `[y][z][x]` flattened.
    pub async fn voxel_grid(&self, radius: i32) -> (Vec<i32>, usize) {
        let side = (2 * radius + 1) as usize;
        let (bx, by, bz) = self.position().await;
        let cx0 = bx.floor() as i32;
        let cy0 = by.floor() as i32;
        let cz0 = bz.floor() as i32;
        let mut grid = Vec::with_capacity(side * side * side);
        let guard = self.world.query_guard();
        for dy in -radius..=radius {
            for dz in -radius..=radius {
                for dx in -radius..=radius {
                    grid.push(guard.get_block_id(cx0 + dx, cy0 + dy, cz0 + dz));
                }
            }
        }
        (grid, side)
    }

    /// Loaded chunk coordinates within `radius_chunks` of the bot's
    /// chunk. Sorted Chebyshev-ascending.
    pub async fn chunks_around(&self, radius_chunks: i32) -> Vec<(i32, i32)> {
        let (bx, _by, bz) = self.position().await;
        let cx0 = (bx as i32) >> 4;
        let cz0 = (bz as i32) >> 4;
        let mut out: Vec<(i32, (i32, i32))> = Vec::new();
        for dx in -radius_chunks..=radius_chunks {
            for dz in -radius_chunks..=radius_chunks {
                let cx = cx0 + dx;
                let cz = cz0 + dz;
                if self.world.get_chunk(cx, cz).is_some() {
                    let cheb = dx.abs().max(dz.abs());
                    out.push((cheb, (cx, cz)));
                }
            }
        }
        out.sort_by_key(|(k, _)| *k);
        out.into_iter().map(|(_, v)| v).collect()
    }

    /// Larger rectangular voxel map than `voxel_grid` — independent
    /// XZ and Y radii. Returns `(flat_grid, (size_x, size_y, size_z))`.
    pub async fn world_map_3d(
        &self,
        radius_xz: i32,
        radius_y: Option<i32>,
    ) -> (Vec<i32>, (usize, usize, usize)) {
        let ry = radius_y.unwrap_or(radius_xz);
        let sx = (2 * radius_xz + 1) as usize;
        let sy = (2 * ry + 1) as usize;
        let sz = sx;
        let (bx, by, bz) = self.position().await;
        let cx0 = bx.floor() as i32;
        let cy0 = by.floor() as i32;
        let cz0 = bz.floor() as i32;
        let mut grid = Vec::with_capacity(sx * sy * sz);
        let guard = self.world.query_guard();
        for dy in -ry..=ry {
            for dz in -radius_xz..=radius_xz {
                for dx in -radius_xz..=radius_xz {
                    grid.push(guard.get_block_id(cx0 + dx, cy0 + dy, cz0 + dz));
                }
            }
        }
        (grid, (sx, sy, sz))
    }
}

/// Convert yaw/pitch (degrees) to a unit look vector in world space.
/// Mirrors `python/minecraft_bot/observation.py::_eye_direction`.
fn look_direction(yaw: f64, pitch: f64) -> (f64, f64, f64) {
    let yaw_r = yaw.to_radians();
    let pitch_r = pitch.to_radians();
    let cos_p = pitch_r.cos();
    // Minecraft: yaw 0 faces south (+z), increases clockwise (looking down).
    let dx = -yaw_r.sin() * cos_p;
    let dy = -pitch_r.sin();
    let dz = yaw_r.cos() * cos_p;
    (dx, dy, dz)
}

/// DDA voxel raycast against the World cache. Returns first solid
/// block hit `(x, y, z, state_id, face)` or `None`. `face` is the
/// Mojang face index (0=bottom, 1=top, 2=north, 3=south, 4=west, 5=east).
fn dda_raycast(
    world: &crate::world::World,
    ox: f64,
    oy: f64,
    oz: f64,
    dx: f64,
    dy: f64,
    dz: f64,
    max_distance: f64,
) -> Option<(i32, i32, i32, i32, u8)> {
    let guard = world.query_guard();
    let mut x = ox.floor() as i32;
    let mut y = oy.floor() as i32;
    let mut z = oz.floor() as i32;

    let step_x = if dx > 0.0 { 1 } else { -1 };
    let step_y = if dy > 0.0 { 1 } else { -1 };
    let step_z = if dz > 0.0 { 1 } else { -1 };

    let next_boundary = |o: f64, s: i32, base: i32| -> f64 {
        if s > 0 {
            (base + 1) as f64 - o
        } else {
            o - base as f64
        }
    };

    let mut t_max_x = if dx.abs() > 1e-12 {
        next_boundary(ox, step_x, x) / dx.abs()
    } else {
        f64::INFINITY
    };
    let mut t_max_y = if dy.abs() > 1e-12 {
        next_boundary(oy, step_y, y) / dy.abs()
    } else {
        f64::INFINITY
    };
    let mut t_max_z = if dz.abs() > 1e-12 {
        next_boundary(oz, step_z, z) / dz.abs()
    } else {
        f64::INFINITY
    };

    let t_delta_x = if dx.abs() > 1e-12 { 1.0 / dx.abs() } else { f64::INFINITY };
    let t_delta_y = if dy.abs() > 1e-12 { 1.0 / dy.abs() } else { f64::INFINITY };
    let t_delta_z = if dz.abs() > 1e-12 { 1.0 / dz.abs() } else { f64::INFINITY };

    let mut face: u8 = 1; // default to "top" when origin starts inside a block
    let mut travelled = 0.0f64;

    while travelled <= max_distance {
        let state = guard.get_block_id(x, y, z);
        if state != 0 {
            return Some((x, y, z, state, face));
        }

        if t_max_x < t_max_y && t_max_x < t_max_z {
            x += step_x;
            travelled = t_max_x;
            t_max_x += t_delta_x;
            face = if step_x > 0 { 4 } else { 5 }; // hit west / east
        } else if t_max_y < t_max_z {
            y += step_y;
            travelled = t_max_y;
            t_max_y += t_delta_y;
            face = if step_y > 0 { 0 } else { 1 }; // hit bottom / top
        } else {
            z += step_z;
            travelled = t_max_z;
            t_max_z += t_delta_z;
            face = if step_z > 0 { 2 } else { 3 }; // hit north / south
        }
    }
    None
}
