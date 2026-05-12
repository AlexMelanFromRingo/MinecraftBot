//! Walkability predicates the A* pathfinder relies on.

use crate::physics::CollisionWorld;
use crate::world::cache::WorldQueryGuard;
use crate::world::World;

/// Minimal world-side interface the pathfinder needs.
pub trait NavWorld {
    /// Block fully blocks movement.
    fn is_solid(&self, x: i32, y: i32, z: i32) -> bool;
    /// Block is water source or flowing water.
    fn is_water(&self, x: i32, y: i32, z: i32) -> bool;
    /// Door / fence-gate / trapdoor — passable at extra cost.
    fn is_navigable_obstacle(&self, x: i32, y: i32, z: i32) -> bool;
}

impl NavWorld for World {
    fn is_solid(&self, x: i32, y: i32, z: i32) -> bool {
        World::is_solid(self, x, y, z)
    }
    fn is_water(&self, x: i32, y: i32, z: i32) -> bool {
        World::is_water(self, x, y, z)
    }
    fn is_navigable_obstacle(&self, x: i32, y: i32, z: i32) -> bool {
        World::is_navigable_obstacle(self, x, y, z)
    }
}

/// Lock-held guard implements NavWorld too. Callers that do many
/// queries should prefer this over `&World` to skip per-call lock
/// acquisition.
impl<'a> NavWorld for WorldQueryGuard<'a> {
    #[inline]
    fn is_solid(&self, x: i32, y: i32, z: i32) -> bool {
        WorldQueryGuard::is_solid(self, x, y, z)
    }
    #[inline]
    fn is_water(&self, x: i32, y: i32, z: i32) -> bool {
        WorldQueryGuard::is_water(self, x, y, z)
    }
    #[inline]
    fn is_navigable_obstacle(&self, x: i32, y: i32, z: i32) -> bool {
        WorldQueryGuard::is_navigable_obstacle(self, x, y, z)
    }
}

/// World implements `CollisionWorld` (single is_solid predicate)
/// so the physics tick can collide against a live `World` cache.
impl CollisionWorld for World {
    fn is_solid(&self, x: i32, y: i32, z: i32) -> bool {
        World::is_solid(self, x, y, z)
    }
}

/// A bot can stand at `(x, y, z)` if `(y-1)` is solid (or water),
/// `(y)` is passable, and `(y+1)` is passable.
pub fn stand_floor<W: NavWorld + ?Sized>(world: &W, x: i32, y: i32, z: i32) -> bool {
    if !world.is_solid(x, y - 1, z) {
        if !world.is_water(x, y - 1, z) {
            return false;
        }
    }
    if world.is_solid(x, y, z) && !world.is_navigable_obstacle(x, y, z) {
        return false;
    }
    if world.is_solid(x, y + 1, z) && !world.is_navigable_obstacle(x, y + 1, z) {
        return false;
    }
    true
}
