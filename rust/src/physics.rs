//! Per-tick physics — Rust port of `python/minecraft_bot/physics.py`.
//!
//! Pure: ``tick`` never mutates its inputs; it returns a new state.

/// Gravity (blocks/tick²).
pub const GRAVITY: f64 = -0.08;
/// Vertical drag per tick (air).
pub const AIR_DRAG: f64 = 0.98;
/// Horizontal friction on solid ground.
pub const GROUND_FRICTION: f64 = 0.6;
/// Vertical drag per tick (water/lava).
pub const WATER_DRAG: f64 = 0.8;
/// Initial jump velocity (blocks/tick).
pub const JUMP_VELOCITY: f64 = 0.42;
/// Walk speed cap (blocks/tick).
pub const WALK_CAP: f64 = 0.21;
/// Sprint speed cap.
pub const SPRINT_CAP: f64 = 0.28;
/// Sneak speed cap.
pub const SNEAK_CAP: f64 = 0.06;

/// Bot AABB width on x and z.
pub const BBOX_W: f64 = 0.6;
/// Bot AABB height.
pub const BBOX_H: f64 = 1.8;
/// Auto-step over slabs.
pub const STEP_HEIGHT: f64 = 0.6;
/// Terminal vertical velocity (blocks/tick).
pub const TERMINAL_VELOCITY: f64 = -3.92;

/// World predicate the physics tick needs.
pub trait CollisionWorld {
    /// True iff the full block at integer `(bx, by, bz)` is solid.
    fn is_solid(&self, bx: i32, by: i32, bz: i32) -> bool;
}

/// Bot kinematic state (feet position).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PhysicsState {
    /// X position.
    pub x: f64,
    /// Y position (feet).
    pub y: f64,
    /// Z position.
    pub z: f64,
    /// X velocity.
    pub vx: f64,
    /// Y velocity.
    pub vy: f64,
    /// Z velocity.
    pub vz: f64,
    /// Whether the bot is standing on a solid surface.
    pub on_ground: bool,
}

impl Default for PhysicsState {
    fn default() -> Self {
        Self {
            x: 0.0,
            y: 0.0,
            z: 0.0,
            vx: 0.0,
            vy: 0.0,
            vz: 0.0,
            on_ground: false,
        }
    }
}

/// Per-tick movement intent.
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct PhysicsIntent {
    /// Local strafe (-1..1).
    pub dx: f64,
    /// Local forward (-1..1).
    pub dz: f64,
    /// Whether to jump.
    pub jump: bool,
    /// Whether to sprint.
    pub sprint: bool,
    /// Whether to sneak.
    pub sneak: bool,
}

fn bbox_min_max(x: f64, y: f64, z: f64) -> (f64, f64, f64, f64, f64, f64) {
    let h = BBOX_W / 2.0;
    (x - h, y, z - h, x + h, y + BBOX_H, z + h)
}

fn intersects_solid<W: CollisionWorld + ?Sized>(world: &W, x: f64, y: f64, z: f64) -> bool {
    let (x0, y0, z0, x1, y1, z1) = bbox_min_max(x, y, z);
    let bx0 = x0.floor() as i32;
    let bx1 = (x1 - 1e-7).floor() as i32;
    let by0 = y0.floor() as i32;
    let by1 = (y1 - 1e-7).floor() as i32;
    let bz0 = z0.floor() as i32;
    let bz1 = (z1 - 1e-7).floor() as i32;
    for by in by0..=by1 {
        for bz in bz0..=bz1 {
            for bx in bx0..=bx1 {
                if world.is_solid(bx, by, bz) {
                    return true;
                }
            }
        }
    }
    false
}

/// Returns `(new_pos_on_axis, collided)`.
fn resolve_axis<W: CollisionWorld + ?Sized>(
    world: &W,
    x: f64,
    y: f64,
    z: f64,
    dx: f64,
    dy: f64,
    dz: f64,
) -> (f64, bool) {
    let target_x = x + dx;
    let target_y = y + dy;
    let target_z = z + dz;
    if !intersects_solid(world, target_x, target_y, target_z) {
        if dx != 0.0 {
            return (target_x, false);
        }
        if dy != 0.0 {
            return (target_y, false);
        }
        return (target_z, false);
    }

    let mut lo: f64 = 0.0;
    let mut hi: f64 = 1.0;
    let mut safe: f64 = 0.0;
    for _ in 0..8 {
        let mid = (lo + hi) / 2.0;
        let tx = x + dx * mid;
        let ty = y + dy * mid;
        let tz = z + dz * mid;
        if intersects_solid(world, tx, ty, tz) {
            hi = mid;
        } else {
            safe = mid;
            lo = mid;
        }
    }
    if dx != 0.0 {
        return (x + dx * safe, true);
    }
    if dy != 0.0 {
        return (y + dy * safe, true);
    }
    (z + dz * safe, true)
}

fn speed_cap(intent: &PhysicsIntent, in_fluid: bool) -> f64 {
    if in_fluid {
        WALK_CAP * 0.5
    } else if intent.sneak {
        SNEAK_CAP
    } else if intent.sprint {
        SPRINT_CAP
    } else {
        WALK_CAP
    }
}

/// Advance the bot one tick (50 ms) and return the new state.
pub fn tick<W: CollisionWorld + ?Sized>(
    state: &PhysicsState,
    intent: &PhysicsIntent,
    world: &W,
    in_water: bool,
    in_lava: bool,
) -> PhysicsState {
    let in_fluid = in_water || in_lava;
    let cap = speed_cap(intent, in_fluid);

    // Horizontal target velocity.
    let mut dx = intent.dx;
    let mut dz = intent.dz;
    let mag = (dx * dx + dz * dz).sqrt();
    if mag > 1.0 {
        dx /= mag;
        dz /= mag;
    }
    let target_vx = dx * cap;
    let target_vz = dz * cap;

    let accel: f64 = if state.on_ground {
        0.5
    } else if in_fluid {
        0.2
    } else {
        0.05
    };
    let mut vx = state.vx + (target_vx - state.vx) * accel;
    let mut vz = state.vz + (target_vz - state.vz) * accel;

    // Vertical: gravity, jump, buoyancy, terminal cap.
    let mut vy = state.vy;
    if intent.jump && (state.on_ground || in_fluid) {
        vy = if in_fluid { 0.16 } else { JUMP_VELOCITY };
    }
    vy += GRAVITY;
    if in_fluid {
        vy *= WATER_DRAG;
    } else {
        vy *= AIR_DRAG;
    }
    if vy < TERMINAL_VELOCITY {
        vy = TERMINAL_VELOCITY;
    }

    // Per-axis swept collision.
    let mut working_y = state.y;
    let (mut new_x, hit_x) = resolve_axis(world, state.x, working_y, state.z, vx, 0.0, 0.0);
    if hit_x {
        let (stepped_x, blocked_after) = resolve_axis(
            world,
            state.x,
            working_y + STEP_HEIGHT,
            state.z,
            vx,
            0.0,
            0.0,
        );
        if !blocked_after && stepped_x != state.x {
            new_x = stepped_x;
            working_y += STEP_HEIGHT;
        } else {
            vx = 0.0;
        }
    }
    let (mut new_z, hit_z) = resolve_axis(world, new_x, working_y, state.z, 0.0, 0.0, vz);
    if hit_z {
        let (stepped_z, blocked_after) =
            resolve_axis(world, new_x, working_y + STEP_HEIGHT, state.z, 0.0, 0.0, vz);
        if !blocked_after && stepped_z != state.z {
            new_z = stepped_z;
            working_y += STEP_HEIGHT;
        } else {
            vz = 0.0;
        }
    }
    let (new_y, hit_y) = resolve_axis(world, new_x, working_y, new_z, 0.0, vy, 0.0);
    let mut on_ground = false;
    let mut vy_final = vy;
    if hit_y {
        if vy < 0.0 {
            on_ground = true;
        }
        vy_final = 0.0;
    }

    if on_ground && !in_fluid {
        vx *= GROUND_FRICTION;
        vz *= GROUND_FRICTION;
    }

    PhysicsState {
        x: new_x,
        y: new_y,
        z: new_z,
        vx,
        vy: vy_final,
        vz,
        on_ground,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Solid floor at y=0; everything else is air.
    struct FloorWorld;
    impl CollisionWorld for FloorWorld {
        fn is_solid(&self, _x: i32, y: i32, _z: i32) -> bool {
            y == 0
        }
    }

    /// No floor at all.
    struct Empty;
    impl CollisionWorld for Empty {
        fn is_solid(&self, _x: i32, _y: i32, _z: i32) -> bool {
            false
        }
    }

    #[test]
    fn gravity_pulls_down_in_empty_world() {
        let s = PhysicsState {
            y: 10.0,
            ..Default::default()
        };
        let after = tick(&s, &PhysicsIntent::default(), &Empty, false, false);
        assert!(after.y < s.y, "expected fall, got y={}", after.y);
        assert!(after.vy < 0.0);
    }

    #[test]
    fn terminal_velocity_caps_fall_speed() {
        let mut s = PhysicsState {
            y: 10000.0,
            ..Default::default()
        };
        for _ in 0..200 {
            s = tick(&s, &PhysicsIntent::default(), &Empty, false, false);
        }
        assert!(s.vy >= TERMINAL_VELOCITY - 1e-6);
        assert!(s.vy < 0.0);
    }

    #[test]
    fn bot_lands_on_floor_and_stays() {
        let s = PhysicsState {
            y: 5.0,
            ..Default::default()
        };
        let mut cur = s;
        for _ in 0..50 {
            cur = tick(&cur, &PhysicsIntent::default(), &FloorWorld, false, false);
        }
        // After many ticks, bot should be on the floor (y == 1.0,
        // feet on top of y=0 cube).
        assert!(cur.on_ground, "expected on_ground after settling");
        assert!((cur.y - 1.0).abs() < 0.01, "expected y≈1, got {}", cur.y);
        assert_eq!(cur.vy, 0.0);
    }

    #[test]
    fn jump_lifts_off_ground() {
        let s = PhysicsState {
            y: 1.0,
            on_ground: true,
            ..Default::default()
        };
        let intent = PhysicsIntent {
            jump: true,
            ..Default::default()
        };
        let after = tick(&s, &intent, &FloorWorld, false, false);
        // After one tick the bot has lifted off.
        assert!(after.y > 1.0, "expected lift, got y={}", after.y);
        assert!(!after.on_ground);
    }

    #[test]
    fn horizontal_intent_moves_along_x() {
        let s = PhysicsState {
            y: 1.0,
            on_ground: true,
            ..Default::default()
        };
        let intent = PhysicsIntent {
            dx: 1.0,
            ..Default::default()
        };
        let after = tick(&s, &intent, &FloorWorld, false, false);
        assert!(after.x > 0.0);
        assert!(after.x < WALK_CAP);
    }
}
