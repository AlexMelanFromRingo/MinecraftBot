//! Per-packet round-trip tests (T128).
//!
//! For every concrete packet type we expose: construct a Default
//! instance, encode it to bytes, decode the bytes back, assert the
//! result equals the original. This catches asymmetric encode/decode
//! pairs even without external golden fixtures.
//!
//! Coverage: a curated subset of packets exercising the various
//! field shapes (varint, string, NBT-optional, uuid, fixed-byte, etc.).
//! Adding a new test here is one line per packet.

use minecraft_bot::codec::{BytesReader, BytesWriter, varint};
use minecraft_bot::protocol::v763::packets::handshaking::serverbound::set_protocol::SetProtocol;
use minecraft_bot::protocol::v763::packets::login::clientbound::{
    compress::Compress, disconnect::Disconnect as LoginDisconnect, success::{Property, Success},
};
use minecraft_bot::protocol::v763::packets::login::serverbound::login_start::LoginStart;
use minecraft_bot::protocol::v763::packets::play::clientbound::{
    keep_alive::KeepAlive as CbKeepAlive,
    kick_disconnect::KickDisconnect,
    statistics::{StatisticEntry, Statistics},
    multi_block_change::MultiBlockChange,
    select_advancement_tab::SelectAdvancementTab,
    stop_sound::StopSound,
    chunk_biomes::{ChunkBiomeEntry, ChunkBiomes},
};
use minecraft_bot::protocol::v763::packets::play::serverbound::{
    keep_alive::KeepAlive as SbKeepAlive,
    teleport_confirm::TeleportConfirm,
};
use minecraft_bot::protocol::v763::{ClientboundPacket, ServerboundPacket};


fn round_trip_serverbound<P>(pkt: &P) -> Vec<u8>
where
    P: ServerboundPacket + std::fmt::Debug,
{
    let mut w = BytesWriter::new();
    pkt.encode(&mut w).expect("encode");
    w.into_bytes()
}

fn round_trip_clientbound<P>(pkt: &P) -> Vec<u8>
where
    P: ClientboundPacket + std::fmt::Debug,
{
    let mut w = BytesWriter::new();
    pkt.encode(&mut w).expect("encode");
    w.into_bytes()
}


#[test]
fn handshake_set_protocol() {
    let pkt = SetProtocol {
        protocol_version: 763,
        server_host: "localhost".into(),
        server_port: 25565,
        next_state: 2,
    };
    let bytes = round_trip_serverbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(SetProtocol::decode(&mut r).unwrap(), pkt);
}


#[test]
fn login_start_with_uuid() {
    let pkt = LoginStart {
        username: "Bot".into(),
        player_uuid: Some([0x10; 16]),
    };
    let bytes = round_trip_serverbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(LoginStart::decode(&mut r).unwrap(), pkt);
}


#[test]
fn login_start_without_uuid() {
    let pkt = LoginStart {
        username: "NoUuid".into(),
        player_uuid: None,
    };
    let bytes = round_trip_serverbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(LoginStart::decode(&mut r).unwrap(), pkt);
}


#[test]
fn login_disconnect() {
    let pkt = LoginDisconnect { reason: "{\"text\":\"banned\"}".into() };
    let bytes = round_trip_clientbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(LoginDisconnect::decode(&mut r).unwrap(), pkt);
}


#[test]
fn login_compress() {
    let pkt = Compress { threshold: 256 };
    let bytes = round_trip_clientbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(Compress::decode(&mut r).unwrap(), pkt);
}


#[test]
fn login_success_no_properties() {
    let pkt = Success {
        uuid: [0xAB; 16],
        username: "Bot".into(),
        properties: vec![],
    };
    let bytes = round_trip_clientbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(Success::decode(&mut r).unwrap(), pkt);
}


#[test]
fn login_success_with_signed_property() {
    let pkt = Success {
        uuid: [0xCD; 16],
        username: "Bot".into(),
        properties: vec![Property {
            name: "textures".into(),
            value: "base64".into(),
            signature: Some("sig".into()),
        }],
    };
    let bytes = round_trip_clientbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(Success::decode(&mut r).unwrap(), pkt);
}


#[test]
fn play_keep_alive_clientbound() {
    let pkt = CbKeepAlive { keep_alive_id: 0x1122_3344_5566_7788_u64 as i64 };
    let bytes = round_trip_clientbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(CbKeepAlive::decode(&mut r).unwrap(), pkt);
}


#[test]
fn play_keep_alive_serverbound() {
    let pkt = SbKeepAlive { keep_alive_id: 0x4242_4242_4242_4242_u64 as i64 };
    let bytes = round_trip_serverbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(SbKeepAlive::decode(&mut r).unwrap(), pkt);
}


#[test]
fn play_teleport_confirm() {
    let pkt = TeleportConfirm { teleport_id: 123 };
    let bytes = round_trip_serverbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(TeleportConfirm::decode(&mut r).unwrap(), pkt);
}


#[test]
fn play_kick_disconnect() {
    let pkt = KickDisconnect { reason: "{\"text\":\"kicked\"}".into() };
    let bytes = round_trip_clientbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(KickDisconnect::decode(&mut r).unwrap(), pkt);
}


#[test]
fn play_statistics_nested_entries() {
    let pkt = Statistics {
        entries: vec![
            StatisticEntry { category_id: 1, statistic_id: 2, value: 3 },
            StatisticEntry { category_id: 10, statistic_id: 20, value: 30 },
        ],
    };
    let bytes = round_trip_clientbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(Statistics::decode(&mut r).unwrap(), pkt);
}


#[test]
fn play_multi_block_change_packed_section() {
    let pkt = MultiBlockChange {
        chunk_section_x: 12,
        chunk_section_z: -34,
        chunk_section_y: -4,
        records: vec![0x123_456, 0xDEAD_BEEF],
    };
    let bytes = round_trip_clientbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(MultiBlockChange::decode(&mut r).unwrap(), pkt);
}


#[test]
fn play_select_advancement_tab_with_id() {
    let pkt = SelectAdvancementTab { id: Some("minecraft:story/root".into()) };
    let bytes = round_trip_clientbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(SelectAdvancementTab::decode(&mut r).unwrap(), pkt);
}


#[test]
fn play_select_advancement_tab_none() {
    let pkt = SelectAdvancementTab { id: None };
    let bytes = round_trip_clientbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(SelectAdvancementTab::decode(&mut r).unwrap(), pkt);
}


#[test]
fn play_stop_sound_bitmask_optionals() {
    let pkt = StopSound {
        flags: 0x03, // both bits set → both Optionals present
        source: Some(2),
        sound: Some("minecraft:music_disc".into()),
    };
    let bytes = round_trip_clientbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(StopSound::decode(&mut r).unwrap(), pkt);
}


#[test]
fn play_stop_sound_no_optionals() {
    let pkt = StopSound { flags: 0, source: None, sound: None };
    let bytes = round_trip_clientbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(StopSound::decode(&mut r).unwrap(), pkt);
}


#[test]
fn play_chunk_biomes_variable_length_payload() {
    let pkt = ChunkBiomes {
        entries: vec![
            ChunkBiomeEntry { chunk_x: 5, chunk_z: -7, data: vec![1, 2, 3, 4] },
            ChunkBiomeEntry { chunk_x: 6, chunk_z: -7, data: vec![0x10, 0x20] },
        ],
    };
    let bytes = round_trip_clientbound(&pkt);
    let mut r = BytesReader::new(&bytes);
    assert_eq!(ChunkBiomes::decode(&mut r).unwrap(), pkt);
}
