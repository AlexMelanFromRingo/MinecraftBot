//! Vec3 + RayHit + Observation snapshot — minimal port of
//! `python/minecraft_bot/observation.py` for AI/ML consumers.

/// 3D vector with f64 components.
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct Vec3 {
    /// X.
    pub x: f64,
    /// Y.
    pub y: f64,
    /// Z.
    pub z: f64,
}

impl Vec3 {
    /// Construct a Vec3.
    pub fn new(x: f64, y: f64, z: f64) -> Self {
        Self { x, y, z }
    }
}

/// First-solid-block raycast hit.
#[derive(Debug, Clone, PartialEq)]
pub struct RayHit {
    /// X.
    pub x: i32,
    /// Y.
    pub y: i32,
    /// Z.
    pub z: i32,
    /// Block-state id.
    pub state_id: i32,
    /// Block name.
    pub name: String,
    /// Face hit (0=bottom..5=east).
    pub face: u8,
    /// Distance from eye in blocks.
    pub distance: f64,
}

/// One AI-agent observation snapshot (subset of the Python reference).
#[derive(Debug, Clone, PartialEq, Default)]
pub struct Observation {
    /// Position x.
    pub x: f64,
    /// Position y.
    pub y: f64,
    /// Position z.
    pub z: f64,
    /// Yaw.
    pub yaw: f32,
    /// Pitch.
    pub pitch: f32,
    /// On-ground flag.
    pub on_ground: bool,
    /// Health.
    pub health: f32,
    /// Food.
    pub food: i32,
    /// Saturation.
    pub saturation: f32,
}
