//! Tiny CLI used by `tools/cross_check.py` to produce Rust-encoded
//! bytes for every primitive codec fixture.
//!
//! Reads a JSON request from argv[1] of shape::
//!
//!     {"codec": "varint", "value": 25565}
//!     {"codec": "string", "value": "hello"}
//!     {"codec": "uuid", "value": "12345678-..."}
//!     {"codec": "position", "value": [100, 64, -200]}
//!     {"codec": "bitset", "value": [0, 5, 63]}
//!     {"codec": "identifier", "value": "minecraft:stone"}
//!     {"codec": "chat_component", "value": "{\"text\":\"...\"}"}
//!     {"codec": "nbt", "hex": "0a..."}     # for nbt/slot the input is the hex form
//!     {"codec": "slot", "hex": "01..."}
//!
//! Writes the resulting byte hex string to stdout.

use std::collections::BTreeSet;
use std::env;
use std::process::ExitCode;

use minecraft_bot::codec::{
    bitset, chat_component, identifier, nbt, position, slot, string_codec, uuid_codec, varint,
    varlong, BytesReader, BytesWriter, Reader, Writer,
};

mod json {
    // Minimal JSON parser, just enough for our request shape.
    use std::collections::BTreeMap;
    use std::iter::Peekable;
    use std::str::Chars;

    #[derive(Debug, Clone)]
    pub enum Value {
        Bool(bool),
        Number(f64),
        String(String),
        Array(Vec<Value>),
        Object(BTreeMap<String, Value>),
        Null,
    }

    impl Value {
        pub fn as_str(&self) -> Option<&str> {
            if let Value::String(s) = self { Some(s) } else { None }
        }
        pub fn as_i64(&self) -> Option<i64> {
            if let Value::Number(n) = self { Some(*n as i64) } else { None }
        }
        pub fn as_array(&self) -> Option<&Vec<Value>> {
            if let Value::Array(a) = self { Some(a) } else { None }
        }
        pub fn as_object(&self) -> Option<&BTreeMap<String, Value>> {
            if let Value::Object(o) = self { Some(o) } else { None }
        }
    }

    pub fn from_str(s: &str) -> Result<Value, String> {
        let mut chars = s.chars().peekable();
        skip_ws(&mut chars);
        parse_value(&mut chars)
    }

    fn skip_ws(chars: &mut Peekable<Chars>) {
        while let Some(&c) = chars.peek() {
            if c.is_whitespace() { chars.next(); } else { break; }
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
            other => Err(format!("unexpected {:?}", other)),
        }
    }

    fn parse_object(chars: &mut Peekable<Chars>) -> Result<Value, String> {
        chars.next();
        let mut map = BTreeMap::new();
        skip_ws(chars);
        if chars.peek() == Some(&'}') { chars.next(); return Ok(Value::Object(map)); }
        loop {
            skip_ws(chars);
            let key = parse_string(chars)?;
            skip_ws(chars);
            if chars.next() != Some(':') { return Err("expected ':'".into()); }
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
        chars.next();
        let mut out = Vec::new();
        skip_ws(chars);
        if chars.peek() == Some(&']') { chars.next(); return Ok(Value::Array(out)); }
        loop {
            out.push(parse_value(chars)?);
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
        if chars.next() != Some('"') { return Err("expected string".into()); }
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
                    Some('u') => {
                        let mut hex = String::new();
                        for _ in 0..4 { hex.push(chars.next().ok_or("bad escape")?); }
                        let cp = u32::from_str_radix(&hex, 16).map_err(|e| e.to_string())?;
                        // Surrogate pair handling for supplementary-plane code points.
                        if (0xD800..=0xDBFF).contains(&cp) {
                            // High surrogate; expect \uXXXX low surrogate next.
                            if chars.next() != Some('\\') || chars.next() != Some('u') {
                                return Err("orphan high surrogate".into());
                            }
                            let mut lo_hex = String::new();
                            for _ in 0..4 { lo_hex.push(chars.next().ok_or("bad escape")?); }
                            let lo = u32::from_str_radix(&lo_hex, 16).map_err(|e| e.to_string())?;
                            if !(0xDC00..=0xDFFF).contains(&lo) {
                                return Err(format!("bad low surrogate: {}", lo_hex));
                            }
                            let combined = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
                            if let Some(c) = char::from_u32(combined) { s.push(c); }
                            else { return Err(format!("bad surrogate pair: {} {}", hex, lo_hex)); }
                        } else if let Some(c) = char::from_u32(cp) {
                            s.push(c);
                        } else {
                            return Err(format!("bad unicode {}", hex));
                        }
                    }
                    other => return Err(format!("bad escape {:?}", other)),
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
                s.push(c); chars.next();
            } else { break; }
        }
        s.parse::<f64>().map(Value::Number).map_err(|e| e.to_string())
    }

    fn parse_bool(chars: &mut Peekable<Chars>) -> Result<Value, String> {
        let s: String = chars.take(4).collect();
        if s == "true" { Ok(Value::Bool(true)) }
        else if s == "fals" && chars.next() == Some('e') { Ok(Value::Bool(false)) }
        else { Err(format!("bad bool: {}", s)) }
    }

    fn parse_null(chars: &mut Peekable<Chars>) -> Result<Value, String> {
        let s: String = chars.take(4).collect();
        if s == "null" { Ok(Value::Null) } else { Err(format!("bad null: {}", s)) }
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

fn run() -> Result<String, String> {
    let arg = env::args().nth(1).ok_or("usage: encode_one <json>")?;
    let req = json::from_str(&arg)?;
    let obj = req.as_object().ok_or("expected JSON object")?;
    let codec = obj.get("codec").and_then(|v| v.as_str()).ok_or("missing 'codec'")?;
    let mut w = BytesWriter::new();

    match codec {
        "varint" => {
            let v = obj["value"].as_i64().ok_or("varint.value not int")? as i32;
            varint::write(v, &mut w).map_err(|e| e.to_string())?;
        }
        "varlong" => {
            let v = obj["value"].as_i64().ok_or("varlong.value not int")?;
            varlong::write(v, &mut w).map_err(|e| e.to_string())?;
        }
        "string" => {
            let s = obj["value"].as_str().ok_or("string.value not str")?;
            string_codec::write(s, &mut w).map_err(|e| e.to_string())?;
        }
        "uuid" => {
            let s = obj["value"].as_str().ok_or("uuid.value not str")?;
            let u = uuid_codec::parse_str(s).map_err(|e| e.to_string())?;
            uuid_codec::write(&u, &mut w).map_err(|e| e.to_string())?;
        }
        "position" => {
            let arr = obj["value"].as_array().ok_or("position.value not array")?;
            let pos = (
                arr[0].as_i64().unwrap() as i32,
                arr[1].as_i64().unwrap() as i32,
                arr[2].as_i64().unwrap() as i32,
            );
            position::write(&pos, &mut w).map_err(|e| e.to_string())?;
        }
        "identifier" => {
            let s = obj["value"].as_str().ok_or("identifier.value not str")?;
            identifier::write(s, &mut w).map_err(|e| e.to_string())?;
        }
        "bitset" => {
            let arr = obj["value"].as_array().ok_or("bitset.value not array")?;
            let mut bs = BTreeSet::new();
            for v in arr { bs.insert(v.as_i64().unwrap() as u32); }
            bitset::write(&bs, &mut w).map_err(|e| e.to_string())?;
        }
        "chat_component" => {
            let s = obj["value"].as_str().ok_or("chat_component.value not str")?;
            chat_component::write(s, &mut w).map_err(|e| e.to_string())?;
        }
        "nbt" => {
            // Roundtrip via the hex form (decode → re-encode).
            let h = obj["hex"].as_str().ok_or("nbt.hex missing")?;
            let raw = hex_to_bytes(h);
            let mut r = BytesReader::new(&raw);
            let decoded = nbt::read(&mut r).map_err(|e| e.to_string())?;
            nbt::write(decoded.as_ref(), &mut w).map_err(|e| e.to_string())?;
        }
        "slot" => {
            let h = obj["hex"].as_str().ok_or("slot.hex missing")?;
            let raw = hex_to_bytes(h);
            let mut r = BytesReader::new(&raw);
            let decoded = slot::read(&mut r).map_err(|e| e.to_string())?;
            slot::write(decoded.as_ref(), &mut w).map_err(|e| e.to_string())?;
        }
        other => return Err(format!("unknown codec: {}", other)),
    }
    Ok(bytes_to_hex(w.as_slice()))
}

fn main() -> ExitCode {
    match run() {
        Ok(hex) => { println!("{}", hex); ExitCode::SUCCESS }
        Err(e) => { eprintln!("encode_one error: {}", e); ExitCode::FAILURE }
    }
}
