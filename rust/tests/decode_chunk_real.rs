//! T025 parity: decode a real captured `map_chunk` payload and
//! verify the result against the Python reference's observed values.
//!
//! Fixture: `protocol-data/v763/golden_bytes/packets/clientbound/map_chunk.json`
//! captured by `tools/extract_golden_bytes.py` from a live Paper 1.20.1
//! session (US2 baseline).

use minecraft_bot::codec::BytesReader;
use minecraft_bot::protocol::v763::packets::play::clientbound::map_chunk::MapChunk;
use minecraft_bot::world::decode_chunk::decode as decode_chunk;
use std::path::PathBuf;

fn fixture_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("protocol-data/v763/golden_bytes/packets/clientbound/map_chunk.json")
}

fn load_hex_payloads() -> Vec<Vec<u8>> {
    let raw = std::fs::read_to_string(fixture_path()).expect("read map_chunk.json");
    let arr: Vec<String> = serde_json::from_str(&raw).expect("parse JSON array of hex strings");
    arr.into_iter().map(|h| hex_decode(&h)).collect()
}

fn hex_decode(s: &str) -> Vec<u8> {
    let bytes = s.as_bytes();
    let mut out = Vec::with_capacity(bytes.len() / 2);
    let mut i = 0;
    while i + 1 < bytes.len() {
        let hi = hex_nibble(bytes[i]);
        let lo = hex_nibble(bytes[i + 1]);
        out.push((hi << 4) | lo);
        i += 2;
    }
    out
}

fn hex_nibble(b: u8) -> u8 {
    match b {
        b'0'..=b'9' => b - b'0',
        b'a'..=b'f' => 10 + (b - b'a'),
        b'A'..=b'F' => 10 + (b - b'A'),
        _ => 0,
    }
}

#[test]
fn first_real_chunk_decodes_24_sections() {
    let payloads = load_hex_payloads();
    assert!(!payloads.is_empty(), "no map_chunk fixtures");
    let raw = &payloads[0];

    // The captured raw bytes include the full map_chunk packet
    // payload: chunk_x (i32) + chunk_z (i32) + inner payload. The
    // packet decoder peels off the header; the world decoder takes
    // the inner payload.
    let mut reader = BytesReader::new(raw);
    let pkt = MapChunk::decode(&mut reader).expect("packet decode");

    let chunk =
        decode_chunk(&pkt.payload, pkt.chunk_x, pkt.chunk_z, -64, 24).expect("world decode_chunk");

    assert_eq!(chunk.cx, pkt.chunk_x);
    assert_eq!(chunk.cz, pkt.chunk_z);
    assert_eq!(chunk.sections.len(), 24);

    // Python's parity observation (probed live):
    //   section 0, cell 0 -> state_id 79  (bedrock-ish)
    //   section 1, cell 0 -> state_id 22450 (deep stone)
    //   section 5, cell 0 -> state_id 1     (stone)
    assert_eq!(chunk.sections[0].block_states.get(0), 79);
    assert_eq!(chunk.sections[1].block_states.get(0), 22450);
    assert_eq!(chunk.sections[5].block_states.get(0), 1);
}

#[test]
fn all_real_chunk_payloads_decode_cleanly() {
    let payloads = load_hex_payloads();
    for (idx, raw) in payloads.iter().enumerate() {
        let mut reader = BytesReader::new(raw);
        let pkt = MapChunk::decode(&mut reader)
            .unwrap_or_else(|e| panic!("packet decode fixture {idx}: {e}"));
        let chunk = decode_chunk(&pkt.payload, pkt.chunk_x, pkt.chunk_z, -64, 24)
            .unwrap_or_else(|e| panic!("world decode fixture {idx}: {e}"));
        assert_eq!(chunk.sections.len(), 24, "fixture {idx} section count");
    }
}
