//! A* pathfinder — Rust port of `python/minecraft_bot/pathfinding.py`.
//!
//! Pure / world-agnostic: the algorithm needs only the `NavWorld`
//! trait (three predicates) and works against any navigable graph.

pub mod astar;
pub mod walkable;

pub use astar::{find_path, NoPathFoundError, Path, Pos};
pub use walkable::NavWorld;
