//! PyO3 exception classes mirroring ``python/minecraft_bot/errors.py``.
//!
//! Every exception class the Python reference exposes also exists here
//! with the same name and the same parent class. ``isinstance`` checks
//! between the two packages are independent (Q4 — separate types), but
//! catching by class name (``except ProtocolError:``) works the same way
//! when the appropriate package's class is used.

use pyo3::create_exception;
use pyo3::exceptions::PyException;
use pyo3::prelude::*;

// -- Root --------------------------------------------------------------
create_exception!(
    minecraft_bot_accel.errors,
    ProtocolError,
    PyException,
    "Base class for every error the native framework surfaces."
);

// -- Connection lifecycle ---------------------------------------------
create_exception!(
    minecraft_bot_accel.errors,
    HandshakeFailed,
    ProtocolError,
    "Server rejected the handshake or peer aborted before login."
);
create_exception!(
    minecraft_bot_accel.errors,
    LoginFailed,
    ProtocolError,
    "Server rejected the login."
);
create_exception!(
    minecraft_bot_accel.errors,
    Disconnected,
    ProtocolError,
    "Server-initiated disconnect during play."
);
create_exception!(
    minecraft_bot_accel.errors,
    KickedByServer,
    Disconnected,
    "The server sent a clientbound disconnect packet with a reason."
);
create_exception!(
    minecraft_bot_accel.errors,
    ConnectionDropped,
    ProtocolError,
    "TCP-level loss outside a clean disconnect."
);
create_exception!(
    minecraft_bot_accel.errors,
    KeepAliveTimeout,
    ConnectionDropped,
    "The framework did not answer a keep-alive within the protocol window."
);
create_exception!(
    minecraft_bot_accel.errors,
    PeerReset,
    ConnectionDropped,
    "The OS reported the socket was reset by the peer."
);
create_exception!(
    minecraft_bot_accel.errors,
    ConnectionClosed,
    ProtocolError,
    "Operation attempted on a Connection that is no longer open."
);

// -- Decoding ----------------------------------------------------------
create_exception!(
    minecraft_bot_accel.errors,
    DecodeError,
    ProtocolError,
    "The framework received bytes it could not parse."
);
create_exception!(
    minecraft_bot_accel.errors,
    UnknownPacketId,
    DecodeError,
    "A packet ID that has no schema registered."
);
create_exception!(
    minecraft_bot_accel.errors,
    OversizedVarInt,
    DecodeError,
    "A VarInt or VarLong consumed more bytes than allowed."
);
create_exception!(
    minecraft_bot_accel.errors,
    IncompleteRead,
    DecodeError,
    "A codec asked for more bytes than remained."
);
create_exception!(
    minecraft_bot_accel.errors,
    MalformedNbt,
    DecodeError,
    "An NBT tag was structurally invalid."
);

// -- Encoding ----------------------------------------------------------
create_exception!(
    minecraft_bot_accel.errors,
    EncodeError,
    ProtocolError,
    "A value provided by the developer cannot be serialised."
);
create_exception!(
    minecraft_bot_accel.errors,
    ValueOutOfRange,
    EncodeError,
    "A numeric or length-bounded field is out of its protocol-defined range."
);

// -- Bot API (002) -----------------------------------------------------
create_exception!(
    minecraft_bot_accel.errors,
    NoPathFound,
    ProtocolError,
    "A* pathfinder exhausted its budget without reaching the target."
);
create_exception!(
    minecraft_bot_accel.errors,
    WalkTimeout,
    ProtocolError,
    "A long-running movement method exceeded its timeout."
);
create_exception!(
    minecraft_bot_accel.errors,
    DigFailed,
    ProtocolError,
    "bot.dig(...) could not finish."
);
create_exception!(
    minecraft_bot_accel.errors,
    TargetLost,
    ProtocolError,
    "A follow/attack target vanished from the EntityTracker."
);
create_exception!(
    minecraft_bot_accel.errors,
    ContainerClosed,
    ProtocolError,
    "An operation was attempted on a container the server has closed."
);
create_exception!(
    minecraft_bot_accel.errors,
    InventoryStateMismatch,
    ProtocolError,
    "A click_slot was rejected because state_id diverged."
);
create_exception!(
    minecraft_bot_accel.errors,
    InVehicle,
    ProtocolError,
    "A movement method was called while the bot is riding a vehicle."
);

/// Register the ``errors`` submodule on the parent module.
///
/// Called from `lib.rs` at module-init time.
pub fn register(py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new_bound(py, "errors")?;

    macro_rules! add {
        ($cls:ident) => {
            m.add(stringify!($cls), py.get_type_bound::<$cls>())?;
        };
    }

    add!(ProtocolError);
    add!(HandshakeFailed);
    add!(LoginFailed);
    add!(Disconnected);
    add!(KickedByServer);
    add!(ConnectionDropped);
    add!(KeepAliveTimeout);
    add!(PeerReset);
    add!(ConnectionClosed);
    add!(DecodeError);
    add!(UnknownPacketId);
    add!(OversizedVarInt);
    add!(IncompleteRead);
    add!(MalformedNbt);
    add!(EncodeError);
    add!(ValueOutOfRange);
    add!(NoPathFound);
    add!(WalkTimeout);
    add!(DigFailed);
    add!(TargetLost);
    add!(ContainerClosed);
    add!(InventoryStateMismatch);
    add!(InVehicle);

    parent.add_submodule(&m)?;
    Ok(())
}
