//! A* core for 3-D voxel navigation.

use std::cmp::Ordering;
use std::collections::{BinaryHeap, HashMap, HashSet};

use crate::pathfinding::walkable::{stand_floor, NavWorld};

/// Voxel position: feet of the bot at `(x, y, z)`.
pub type Pos = (i32, i32, i32);

/// A* result.
#[derive(Debug, Clone, PartialEq)]
pub struct Path {
    /// Ordered sequence from `start` to `goal` (inclusive).
    pub nodes: Vec<Pos>,
    /// Total g-score along `nodes`.
    pub cost: f64,
}

/// Pathfinder failure — emitted to callers as the matching Python
/// `NoPathFound` exception type via the PyO3 error map.
#[derive(Debug, thiserror::Error)]
#[error("no path to {goal:?} ({expansions} nodes explored)")]
pub struct NoPathFoundError {
    /// Goal that the search failed to reach.
    pub goal: Pos,
    /// Number of node expansions consumed.
    pub expansions: usize,
}

const DIAG: f64 = std::f64::consts::SQRT_2;

const HORIZ: &[(i32, i32, bool)] = &[
    (1, 0, false), (-1, 0, false), (0, 1, false), (0, -1, false),
    (1, 1, true), (1, -1, true), (-1, 1, true), (-1, -1, true),
];

#[derive(Copy, Clone, Debug)]
struct OpenEntry {
    /// f = g + h.
    f: f64,
    /// Tie-breaker for deterministic ordering.
    seq: u64,
    pos: Pos,
}

impl PartialEq for OpenEntry {
    fn eq(&self, other: &Self) -> bool {
        self.f == other.f && self.seq == other.seq
    }
}
impl Eq for OpenEntry {}
impl Ord for OpenEntry {
    fn cmp(&self, other: &Self) -> Ordering {
        // BinaryHeap is max-heap → invert ordering for min-heap.
        other
            .f
            .partial_cmp(&self.f)
            .unwrap_or(Ordering::Equal)
            .then(other.seq.cmp(&self.seq))
    }
}
impl PartialOrd for OpenEntry {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

fn heuristic(a: Pos, b: Pos) -> f64 {
    let dx = (a.0 - b.0).abs();
    let dy = (a.1 - b.1).abs();
    let dz = (a.2 - b.2).abs();
    let diag = dx.min(dz);
    let straight = dx.max(dz) - diag;
    DIAG * (diag as f64) + (straight as f64) + 0.5 * (dy as f64)
}

fn vertical_resolve<W: NavWorld + ?Sized>(
    world: &W,
    x: i32,
    y_from: i32,
    z: i32,
    max_fall: i32,
) -> Option<(i32, f64)> {
    if stand_floor(world, x, y_from, z) {
        return Some((y_from, 0.0));
    }
    if stand_floor(world, x, y_from + 1, z) {
        return Some((y_from + 1, 0.5));
    }
    for drop in 1..=max_fall {
        let ny = y_from - drop;
        if stand_floor(world, x, ny, z) {
            return Some((ny, 0.1 * (drop as f64)));
        }
    }
    None
}

fn neighbors<W: NavWorld + ?Sized>(
    world: &W,
    cur: Pos,
    max_fall: i32,
) -> Vec<(Pos, f64)> {
    let (x, y, z) = cur;
    let in_water = world.is_water(x, y, z);
    let water_mult: f64 = if in_water { 1.6 } else { 1.0 };
    let mut out = Vec::with_capacity(HORIZ.len());

    for &(dx, dz, is_diag) in HORIZ {
        let nx = x + dx;
        let nz = z + dz;
        if is_diag {
            let side_a = stand_floor(world, x + dx, y, z);
            let side_b = stand_floor(world, x, y, z + dz);
            if !(side_a || side_b) {
                continue;
            }
        }
        let Some((ny, vcost)) = vertical_resolve(world, nx, y, nz, max_fall) else {
            continue;
        };
        let base: f64 = if is_diag { DIAG } else { 1.0 };
        let mut cost = base * water_mult + vcost;
        if world.is_navigable_obstacle(nx, ny, nz)
            || world.is_navigable_obstacle(nx, ny + 1, nz)
        {
            cost += 2.0;
        }
        out.push(((nx, ny, nz), cost));
    }
    out
}

/// Find a path from `start` to `goal` using A*.
///
/// Returns `Err(NoPathFoundError)` if the goal is unreachable or the
/// node budget is exhausted (`max_nodes` expansions).
pub fn find_path<W: NavWorld + ?Sized>(
    world: &W,
    start: Pos,
    goal: Pos,
    max_fall: i32,
    max_nodes: usize,
) -> Result<Path, NoPathFoundError> {
    if start == goal {
        return Ok(Path { nodes: vec![start], cost: 0.0 });
    }

    let mut open: BinaryHeap<OpenEntry> = BinaryHeap::new();
    let mut g_score: HashMap<Pos, f64> = HashMap::new();
    let mut came_from: HashMap<Pos, Pos> = HashMap::new();
    let mut closed: HashSet<Pos> = HashSet::new();

    let mut seq: u64 = 0;
    g_score.insert(start, 0.0);
    open.push(OpenEntry { f: heuristic(start, goal), seq, pos: start });

    let mut expansions: usize = 0;
    while let Some(OpenEntry { pos: cur, .. }) = open.pop() {
        if closed.contains(&cur) {
            continue;
        }
        if cur == goal {
            // Reconstruct.
            let mut nodes_rev: Vec<Pos> = vec![cur];
            let mut walker = cur;
            while let Some(&prev) = came_from.get(&walker) {
                nodes_rev.push(prev);
                walker = prev;
            }
            nodes_rev.reverse();
            let final_cost = g_score.get(&goal).copied().unwrap_or(0.0);
            return Ok(Path { nodes: nodes_rev, cost: final_cost });
        }
        closed.insert(cur);
        expansions += 1;
        if expansions > max_nodes {
            return Err(NoPathFoundError { goal, expansions });
        }

        let g_cur = *g_score.get(&cur).unwrap_or(&f64::INFINITY);
        for (nbr, step_cost) in neighbors(world, cur, max_fall) {
            if closed.contains(&nbr) {
                continue;
            }
            let tentative = g_cur + step_cost;
            let prev_g = *g_score.get(&nbr).unwrap_or(&f64::INFINITY);
            if tentative < prev_g {
                g_score.insert(nbr, tentative);
                came_from.insert(nbr, cur);
                seq += 1;
                open.push(OpenEntry {
                    f: tentative + heuristic(nbr, goal),
                    seq,
                    pos: nbr,
                });
            }
        }
    }
    Err(NoPathFoundError { goal, expansions })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Pure flat plane: all `y == 0` is solid floor; `y >= 1` is air.
    struct FlatWorld;
    impl NavWorld for FlatWorld {
        fn is_solid(&self, _x: i32, y: i32, _z: i32) -> bool {
            y == 0
        }
        fn is_water(&self, _x: i32, _y: i32, _z: i32) -> bool {
            false
        }
        fn is_navigable_obstacle(&self, _x: i32, _y: i32, _z: i32) -> bool {
            false
        }
    }

    /// Plane with a finite 2-block-tall wall at z=5, spanning x ∈ [-2, 2].
    /// Goal at (0, 1, 10) forces the bot to detour around either end.
    struct WallWorld;
    impl NavWorld for WallWorld {
        fn is_solid(&self, x: i32, y: i32, z: i32) -> bool {
            if y == 0 {
                return true;
            }
            // 5-block-long wall at z=5, x ∈ [-2..=2], heights 1-2.
            (y == 1 || y == 2) && z == 5 && (-2..=2).contains(&x)
        }
        fn is_water(&self, _x: i32, _y: i32, _z: i32) -> bool {
            false
        }
        fn is_navigable_obstacle(&self, _x: i32, _y: i32, _z: i32) -> bool {
            false
        }
    }

    #[test]
    fn same_start_and_goal_returns_single_node_zero_cost() {
        let p = find_path(&FlatWorld, (0, 1, 0), (0, 1, 0), 3, 100).unwrap();
        assert_eq!(p.nodes.len(), 1);
        assert_eq!(p.cost, 0.0);
    }

    #[test]
    fn straight_line_on_flat_world() {
        let p = find_path(&FlatWorld, (0, 1, 0), (5, 1, 0), 3, 1000).unwrap();
        assert_eq!(p.nodes.first(), Some(&(0, 1, 0)));
        assert_eq!(p.nodes.last(), Some(&(5, 1, 0)));
        // Pure horizontal cardinal moves; cost == 5.
        assert!((p.cost - 5.0).abs() < 1e-9);
    }

    #[test]
    fn diagonal_on_flat_world() {
        let p = find_path(&FlatWorld, (0, 1, 0), (3, 1, 3), 3, 1000).unwrap();
        assert_eq!(p.nodes.first(), Some(&(0, 1, 0)));
        assert_eq!(p.nodes.last(), Some(&(3, 1, 3)));
        // Three diagonal moves; cost == 3 * sqrt(2).
        assert!((p.cost - 3.0 * std::f64::consts::SQRT_2).abs() < 1e-9);
    }

    #[test]
    fn wall_forces_detour() {
        let p = find_path(&WallWorld, (0, 1, 0), (0, 1, 10), 3, 100_000).unwrap();
        // Path must end at the goal and pass around the wall (|x| > 2 at z==5).
        assert_eq!(p.nodes.last(), Some(&(0, 1, 10)));
        let crossed_wall_row = p.nodes.iter().any(|&(x, _, z)| z == 5 && x.abs() > 2);
        assert!(
            crossed_wall_row,
            "expected detour around wall, got path: {:?}",
            p.nodes
        );
    }

    #[test]
    fn node_budget_exhaustion_returns_error() {
        // Unreachable: goal is in solid rock (y=0 is the floor).
        let r = find_path(&FlatWorld, (0, 1, 0), (0, 0, 0), 3, 100);
        assert!(r.is_err());
    }
}
