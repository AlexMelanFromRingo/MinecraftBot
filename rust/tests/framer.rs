//! Integration-level framer tests (T127).
//!
//! The framer's unit tests live alongside the source in
//! `src/framer.rs`. This file exercises additional scenarios that
//! benefit from being external to the crate:
//!
//! - Streaming feed (one byte at a time)
//! - Multi-packet buffering
//! - Compression toggle mid-stream

use minecraft_bot::framer::{Framer, MAX_PACKET_SIZE};

#[test]
fn extracts_two_packets_back_to_back() {
    let f = Framer::new();
    let p1 = b"\x01\x02\x03";
    let p2 = b"\x10\x20\x30\x40";
    let mut buf = f.encode(p1).unwrap();
    buf.extend_from_slice(&f.encode(p2).unwrap());

    let mut g = Framer::new();
    g.feed(&buf);
    let a = g.try_extract().unwrap().expect("first packet");
    let b = g.try_extract().unwrap().expect("second packet");
    assert!(g.try_extract().unwrap().is_none());
    assert_eq!(&a, p1);
    assert_eq!(&b, p2);
}

#[test]
fn extract_packet_when_fed_one_byte_at_a_time() {
    let body = b"hello, framer";
    let framed = Framer::new().encode(body).unwrap();
    let mut g = Framer::new();
    let mut got: Option<Vec<u8>> = None;
    for byte in framed.iter() {
        g.feed(&[*byte]);
        if let Some(b) = g.try_extract().unwrap() {
            got = Some(b);
            break;
        }
    }
    assert_eq!(got.as_deref(), Some(&body[..]));
}

#[test]
fn compression_toggle_mid_stream() {
    // Phase 1: produce a frame with NO compression.
    let f1 = Framer::new();
    let raw_frame = f1.encode(b"prefix").unwrap();

    // Phase 2: switch to compression for the next frame.
    let f2 = Framer::with_compression(4);
    let zip_frame = f2
        .encode(b"this is a longer payload, well above the threshold")
        .unwrap();

    // Receiver: starts uncompressed, then enables compression on the
    // second frame (Set Compression in Login).
    let mut g = Framer::new();
    g.feed(&raw_frame);
    let a = g.try_extract().unwrap().unwrap();
    assert_eq!(&a, b"prefix");

    g.compression_threshold = 4;
    g.feed(&zip_frame);
    let b = g.try_extract().unwrap().unwrap();
    assert_eq!(&b, b"this is a longer payload, well above the threshold");
}

#[test]
fn max_packet_size_constant_matches_spec() {
    // 2 MiB per spec R-02.
    assert_eq!(MAX_PACKET_SIZE, 2 * 1024 * 1024);
}

#[test]
fn rejects_oversized_length_prefix() {
    let mut g = Framer::new();
    // Length varint of i32::MAX ≈ 2 GiB.
    g.feed(&[0xFF, 0xFF, 0xFF, 0xFF, 0x07]);
    let err = g.try_extract().expect_err("must reject oversized");
    let msg = format!("{}", err);
    assert!(
        msg.contains("MAX_PACKET_SIZE") || msg.contains("packet length"),
        "unexpected error: {}",
        msg
    );
}
