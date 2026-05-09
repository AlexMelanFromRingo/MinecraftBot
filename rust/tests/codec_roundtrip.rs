//! Round-trip + golden-byte tests for every primitive codec.
//!
//! Validates byte parity with Python's `protocol-data/v763/golden_bytes/primitives.json`.

use std::collections::BTreeSet;
use std::fs;
use std::path::Path;

use minecraft_bot::codec::{
    bitset, chat_component, identifier, nbt, position, slot, string_codec, uuid_codec,
    varint, varlong, BytesReader, BytesWriter, Reader, Writer,
};

fn fixture_path() -> std::path::PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("protocol-data/v763/golden_bytes/primitives.json")
}

fn load_fixtures() -> serde_json_lite::Value {
    let raw = fs::read_to_string(fixture_path()).expect("primitives.json missing");
    serde_json_lite::from_str(&raw).expect("primitives.json parse")
}

// We can't depend on serde_json (Constitution VI keeps the dep tree shallow),
// so use a tiny in-tree JSON parser instead. For this test file only.
mod serde_json_lite {
    use std::collections::BTreeMap;
    use std::iter::Peekable;
    use std::str::Chars;

    #[derive(Debug, Clone)]
    pub enum Value {
        Null,
        Bool(bool),
        Number(f64),
        String(String),
        Array(Vec<Value>),
        Object(BTreeMap<String, Value>),
    }

    impl Value {
        pub fn as_str(&self) -> Option<&str> {
            if let Value::String(s) = self {
                Some(s)
            } else {
                None
            }
        }
        pub fn as_array(&self) -> Option<&Vec<Value>> {
            if let Value::Array(a) = self {
                Some(a)
            } else {
                None
            }
        }
        pub fn as_object(&self) -> Option<&BTreeMap<String, Value>> {
            if let Value::Object(o) = self {
                Some(o)
            } else {
                None
            }
        }
        pub fn as_i64(&self) -> Option<i64> {
            if let Value::Number(n) = self {
                Some(*n as i64)
            } else {
                None
            }
        }
        pub fn as_f64(&self) -> Option<f64> {
            if let Value::Number(n) = self {
                Some(*n)
            } else {
                None
            }
        }
    }

    pub fn from_str(s: &str) -> Result<Value, String> {
        let mut chars = s.chars().peekable();
        skip_ws(&mut chars);
        let v = parse_value(&mut chars)?;
        Ok(v)
    }

    fn skip_ws(chars: &mut Peekable<Chars>) {
        while let Some(&c) = chars.peek() {
            if c.is_whitespace() {
                chars.next();
            } else {
                break;
            }
        }
    }

    fn parse_value(chars: &mut Peekable<Chars>) -> Result<Value, String> {
        skip_ws(chars);
        match chars.peek() {
            Some('{') => parse_object(chars),
            Some('[') => parse_array(chars),
            Some('"') => parse_string(chars).map(Value::String),
            Some('t') | Some('f') => parse_bool(chars),
            Some('n') => parse_null(chars),
            Some(c) if *c == '-' || c.is_ascii_digit() => parse_number(chars),
            Some(c) => Err(format!("unexpected {:?}", c)),
            None => Err("unexpected EOF".into()),
        }
    }

    fn parse_object(chars: &mut Peekable<Chars>) -> Result<Value, String> {
        chars.next(); // consume '{'
        let mut map = BTreeMap::new();
        skip_ws(chars);
        if chars.peek() == Some(&'}') {
            chars.next();
            return Ok(Value::Object(map));
        }
        loop {
            skip_ws(chars);
            let key = parse_string(chars)?;
            skip_ws(chars);
            if chars.next() != Some(':') {
                return Err("expected ':'".into());
            }
            let v = parse_value(chars)?;
            map.insert(key, v);
            skip_ws(chars);
            match chars.next() {
                Some(',') => continue,
                Some('}') => break,
                other => return Err(format!("expected ',' or '}}', got {:?}", other)),
            }
        }
        Ok(Value::Object(map))
    }

    fn parse_array(chars: &mut Peekable<Chars>) -> Result<Value, String> {
        chars.next(); // '['
        let mut out = Vec::new();
        skip_ws(chars);
        if chars.peek() == Some(&']') {
            chars.next();
            return Ok(Value::Array(out));
        }
        loop {
            let v = parse_value(chars)?;
            out.push(v);
            skip_ws(chars);
            match chars.next() {
                Some(',') => continue,
                Some(']') => break,
                other => return Err(format!("expected ',' or ']', got {:?}", other)),
            }
        }
        Ok(Value::Array(out))
    }

    fn parse_string(chars: &mut Peekable<Chars>) -> Result<String, String> {
        if chars.next() != Some('"') {
            return Err("expected string".into());
        }
        let mut s = String::new();
        loop {
            match chars.next() {
                Some('"') => return Ok(s),
                Some('\\') => match chars.next() {
                    Some('n') => s.push('\n'),
                    Some('t') => s.push('\t'),
                    Some('r') => s.push('\r'),
                    Some('"') => s.push('"'),
                    Some('\\') => s.push('\\'),
                    Some('/') => s.push('/'),
                    Some('b') => s.push('\u{08}'),
                    Some('f') => s.push('\u{0C}'),
                    Some('u') => {
                        let mut hex = String::new();
                        for _ in 0..4 {
                            hex.push(chars.next().ok_or("bad escape")?);
                        }
                        let cp = u32::from_str_radix(&hex, 16).map_err(|e| e.to_string())?;
                        if let Some(c) = char::from_u32(cp) {
                            s.push(c);
                        } else {
                            return Err(format!("bad unicode escape: {}", hex));
                        }
                    }
                    other => return Err(format!("bad escape: {:?}", other)),
                },
                Some(c) => s.push(c),
                None => return Err("unterminated string".into()),
            }
        }
    }

    fn parse_number(chars: &mut Peekable<Chars>) -> Result<Value, String> {
        let mut s = String::new();
        while let Some(&c) = chars.peek() {
            if c.is_ascii_digit() || c == '-' || c == '+' || c == '.' || c == 'e' || c == 'E' {
                s.push(c);
                chars.next();
            } else {
                break;
            }
        }
        s.parse::<f64>().map(Value::Number).map_err(|e| e.to_string())
    }

    fn parse_bool(chars: &mut Peekable<Chars>) -> Result<Value, String> {
        let s: String = chars.take(4).collect();
        if s == "true" {
            Ok(Value::Bool(true))
        } else if s == "fals" && chars.next() == Some('e') {
            Ok(Value::Bool(false))
        } else {
            Err(format!("bad bool: {}", s))
        }
    }

    fn parse_null(chars: &mut Peekable<Chars>) -> Result<Value, String> {
        let s: String = chars.take(4).collect();
        if s == "null" {
            Ok(Value::Null)
        } else {
            Err(format!("bad null: {}", s))
        }
    }
}

fn hex_to_bytes(s: &str) -> Vec<u8> {
    (0..s.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
        .collect()
}

fn bytes_to_hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{:02x}", x)).collect()
}

#[test]
fn varint_golden() {
    let fixtures = load_fixtures();
    for fx in fixtures.as_object().unwrap()["varint"].as_array().unwrap() {
        let obj = fx.as_object().unwrap();
        let value = obj["value"].as_i64().unwrap() as i32;
        let expected = obj["hex"].as_str().unwrap();
        let mut w = BytesWriter::new();
        varint::write(value, &mut w).unwrap();
        assert_eq!(bytes_to_hex(w.as_slice()), expected, "varint {}", value);
        let raw = hex_to_bytes(expected);
        let mut r = BytesReader::new(&raw);
        let decoded = varint::read(&mut r).unwrap();
        assert_eq!(decoded, value);
        assert_eq!(r.remaining(), 0);
    }
}

#[test]
fn varlong_golden() {
    let fixtures = load_fixtures();
    for fx in fixtures.as_object().unwrap()["varlong"].as_array().unwrap() {
        let obj = fx.as_object().unwrap();
        let value = obj["value"].as_i64().unwrap();
        let expected = obj["hex"].as_str().unwrap();
        let mut w = BytesWriter::new();
        varlong::write(value, &mut w).unwrap();
        assert_eq!(bytes_to_hex(w.as_slice()), expected, "varlong {}", value);
    }
}

#[test]
fn string_golden() {
    let fixtures = load_fixtures();
    for fx in fixtures.as_object().unwrap()["string"].as_array().unwrap() {
        let obj = fx.as_object().unwrap();
        let value = obj["value"].as_str().unwrap();
        let expected = obj["hex"].as_str().unwrap();
        let mut w = BytesWriter::new();
        string_codec::write(value, &mut w).unwrap();
        assert_eq!(bytes_to_hex(w.as_slice()), expected, "string {:?}", value);
    }
}

#[test]
fn uuid_golden() {
    let fixtures = load_fixtures();
    for fx in fixtures.as_object().unwrap()["uuid"].as_array().unwrap() {
        let obj = fx.as_object().unwrap();
        let value_str = obj["value"].as_str().unwrap();
        let expected = obj["hex"].as_str().unwrap();
        let u = uuid_codec::parse_str(value_str).unwrap();
        let mut w = BytesWriter::new();
        uuid_codec::write(&u, &mut w).unwrap();
        assert_eq!(bytes_to_hex(w.as_slice()), expected, "uuid {}", value_str);
    }
}

#[test]
fn position_golden() {
    let fixtures = load_fixtures();
    for fx in fixtures.as_object().unwrap()["position"].as_array().unwrap() {
        let obj = fx.as_object().unwrap();
        let arr = obj["value"].as_array().unwrap();
        let pos = (
            arr[0].as_i64().unwrap() as i32,
            arr[1].as_i64().unwrap() as i32,
            arr[2].as_i64().unwrap() as i32,
        );
        let expected = obj["hex"].as_str().unwrap();
        let mut w = BytesWriter::new();
        position::write(&pos, &mut w).unwrap();
        assert_eq!(bytes_to_hex(w.as_slice()), expected, "position {:?}", pos);
    }
}

#[test]
fn identifier_golden() {
    let fixtures = load_fixtures();
    for fx in fixtures.as_object().unwrap()["identifier"]
        .as_array()
        .unwrap()
    {
        let obj = fx.as_object().unwrap();
        let value = obj["value"].as_str().unwrap();
        let expected = obj["hex"].as_str().unwrap();
        let mut w = BytesWriter::new();
        identifier::write(value, &mut w).unwrap();
        assert_eq!(bytes_to_hex(w.as_slice()), expected, "identifier {:?}", value);
    }
}

#[test]
fn bitset_golden() {
    let fixtures = load_fixtures();
    for fx in fixtures.as_object().unwrap()["bitset"].as_array().unwrap() {
        let obj = fx.as_object().unwrap();
        let mut bs = BTreeSet::new();
        for v in obj["value"].as_array().unwrap() {
            bs.insert(v.as_i64().unwrap() as u32);
        }
        let expected = obj["hex"].as_str().unwrap();
        let mut w = BytesWriter::new();
        bitset::write(&bs, &mut w).unwrap();
        assert_eq!(bytes_to_hex(w.as_slice()), expected, "bitset");
    }
}

#[test]
fn chat_component_golden() {
    let fixtures = load_fixtures();
    for fx in fixtures.as_object().unwrap()["chat_component"]
        .as_array()
        .unwrap()
    {
        let obj = fx.as_object().unwrap();
        let value = obj["value"].as_str().unwrap();
        let expected = obj["hex"].as_str().unwrap();
        let mut w = BytesWriter::new();
        chat_component::write(value, &mut w).unwrap();
        assert_eq!(bytes_to_hex(w.as_slice()), expected, "chat_component");
    }
}

#[test]
fn nbt_golden_round_trip() {
    let fixtures = load_fixtures();
    for fx in fixtures.as_object().unwrap()["nbt"].as_array().unwrap() {
        let obj = fx.as_object().unwrap();
        let expected_hex = obj["hex"].as_str().unwrap();
        let raw = hex_to_bytes(expected_hex);
        let mut r = BytesReader::new(&raw);
        let decoded = nbt::read(&mut r).unwrap();
        let mut w = BytesWriter::new();
        nbt::write(decoded.as_ref(), &mut w).unwrap();
        assert_eq!(bytes_to_hex(w.as_slice()), expected_hex, "nbt round-trip");
    }
}

#[test]
fn slot_golden_round_trip() {
    let fixtures = load_fixtures();
    for fx in fixtures.as_object().unwrap()["slot"].as_array().unwrap() {
        let obj = fx.as_object().unwrap();
        let expected_hex = obj["hex"].as_str().unwrap();
        let raw = hex_to_bytes(expected_hex);
        let mut r = BytesReader::new(&raw);
        let decoded = slot::read(&mut r).unwrap();
        let mut w = BytesWriter::new();
        slot::write(decoded.as_ref(), &mut w).unwrap();
        assert_eq!(bytes_to_hex(w.as_slice()), expected_hex, "slot round-trip");
    }
}
