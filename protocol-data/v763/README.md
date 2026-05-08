# protocol-data/v763 — pinned snapshots and golden fixtures

This directory holds the read-only protocol numerics, schemas, and
golden-byte fixtures for **Minecraft Java Edition 1.20.1, protocol 763**.

## Files

| File | Purpose | Source |
|---|---|---|
| `packet_registry.json` | Pinned schema for all packets in protocol 763 | PrismarineJS minecraft-data — `data/pc/1.20/protocol.json` (1.20 and 1.20.1 share the same protocol per upstream `dataPaths.json`) |
| `golden_bytes/primitives.json` | Test vectors for the 10 primitive codecs (≥3 each, including boundary cases — SC-004) | Hand-curated, validated against live Paper |
| `golden_bytes/packets/clientbound/*.json` | Per-packet golden payloads, one file per packet | Live captures, recorded via `tools/capture_session.py` |
| `golden_bytes/packets/serverbound/*.json` | Per-packet golden payloads | Live captures |
| `live_captures/*.jsonl` | Full-session WireLog dumps (committed for reproducibility) | `tools/capture_session.py` |
| `overrides.json` (optional) | Live-server probe overrides on top of the upstream snapshot | Hand-edited when minecraft-data and the live server disagree |

## Packet counts (this snapshot)

| State | Clientbound | Serverbound |
|---|---|---|
| handshaking | 0 | 2 |
| status | 2 | 2 |
| login | 5 | 3 |
| play | 110 | 51 |

**Total**: 175 packet definitions to mirror across Python and Rust.

## Updating

This snapshot is **pinned**. To refresh against upstream:

```bash
curl -fsSL -o protocol-data/v763/packet_registry.json \
  https://raw.githubusercontent.com/PrismarineJS/minecraft-data/master/data/pc/1.20/protocol.json
python tools/cross_check.py  # verify nothing regressed
```

Per Constitution and FR-022: when the live-server probe disagrees with this
snapshot on a numeric ID or schema detail, the live-server probe is the
authoritative value. Record the override in `overrides.json` rather than
diverging from the upstream snapshot.
