//! Walkability predicates the A* pathfinder relies on.

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
