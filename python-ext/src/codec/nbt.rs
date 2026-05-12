//! `minecraft_bot_accel.codec.nbt` — direct NBT decode/encode.
//!
//! Reads bytes-in / Python-value-out without crossing the FFI
//! boundary mid-parse. Returns a Python value tree:
//! - primitives: int / float / str
//! - byte_array / int_array / long_array: list[int]
//! - list: list[value]
//! - compound: dict[str, value]
//! Tag-type information is preserved on the **root** via a wrapper
//! dict ``{"_type": "compound", "_value": {...}}`` so callers can
//! re-encode without ambiguity. Inner tags carry no type metadata
//! (lossy round-trip; matches the parity gates we already have).

use minecraft_bot::codec::{nbt as rnbt, BytesReader, Reader as _};
use minecraft_bot::errors::ProtocolError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList};

use crate::codec::{PyReader, PyWriter};
use crate::error_map::IntoPyResult;

fn tag_to_py<'py>(py: Python<'py>, tag: &rnbt::NbtTag) -> PyResult<Bound<'py, PyAny>> {
    use rnbt::NbtTag::*;
    Ok(match tag {
        Byte(v) => (*v as i64).into_py(py).into_bound(py),
        Short(v) => (*v as i64).into_py(py).into_bound(py),
        Int(v) => (*v as i64).into_py(py).into_bound(py),
        Long(v) => (*v).into_py(py).into_bound(py),
        Float(v) => (*v as f64).into_py(py).into_bound(py),
        Double(v) => (*v).into_py(py).into_bound(py),
        String(s) => s.clone().into_py(py).into_bound(py),
        ByteArray(arr) => {
            let l = PyList::empty_bound(py);
            for b in arr {
                l.append(*b as i64)?;
            }
            l.into_any()
        }
        IntArray(arr) => {
            let l = PyList::empty_bound(py);
            for i in arr {
                l.append(*i as i64)?;
            }
            l.into_any()
        }
        LongArray(arr) => {
            let l = PyList::empty_bound(py);
            for i in arr {
                l.append(*i)?;
            }
            l.into_any()
        }
        List { items, .. } => {
            let l = PyList::empty_bound(py);
            for item in items {
                l.append(tag_to_py(py, item)?)?;
            }
            l.into_any()
        }
        Compound(entries) => {
            let d = PyDict::new_bound(py);
            for (k, v) in entries {
                d.set_item(k, tag_to_py(py, v)?)?;
            }
            d.into_any()
        }
    })
}

/// `read(reader) -> object | None` — decode one NBT root tag from a
/// Reader. Returns `None` if the root tag is TAG_End. The returned
/// Python value mirrors the tag structure (dict for compound, list
/// for list/array, scalar for primitives).
#[pyfunction]
fn read<'py>(py: Python<'py>, reader: &PyReader) -> PyResult<Option<Bound<'py, PyAny>>> {
    let tag_opt = reader.with_rust_reader(|r| rnbt::read(r))?;
    match tag_opt {
        None => Ok(None),
        Some(t) => Ok(Some(tag_to_py(py, &t)?)),
    }
}

/// `read_bytes(buf) -> (value | None, consumed_bytes)` — convenience
/// for callers who don't want to construct a Reader. Decodes one tag
/// from the start of `buf`.
#[pyfunction]
fn read_bytes<'py>(
    py: Python<'py>,
    buf: &Bound<'_, PyBytes>,
) -> PyResult<(Option<Bound<'py, PyAny>>, usize)> {
    let bytes = buf.as_bytes();
    // Run the decode under allow_threads where possible. The tag-to-
    // Python conversion needs the GIL, so we keep that on the calling
    // thread.
    let owned: Vec<u8> = bytes.to_vec();
    let (tag_opt, consumed): (Option<rnbt::NbtTag>, usize) = py
        .allow_threads(move || -> Result<_, ProtocolError> {
            let mut r = BytesReader::new(&owned);
            let t = rnbt::read(&mut r)?;
            let c = r.position();
            Ok((t, c))
        })
        .into_py()?;
    match tag_opt {
        None => Ok((None, consumed)),
        Some(t) => Ok((Some(tag_to_py(py, &t)?), consumed)),
    }
}

/// `write(tag, writer)` — encode a Python tag into the writer.
/// `tag=None` writes a single TAG_End byte (empty network NBT root).
/// Top-level non-None values MUST be a dict (compound); deeper
/// values follow standard list/dict/int/str/float conventions.
#[pyfunction]
fn write(tag: &Bound<'_, PyAny>, writer: &PyWriter) -> PyResult<()> {
    let parsed: Option<rnbt::NbtTag> = if tag.is_none() {
        None
    } else {
        Some(py_to_tag(tag)?)
    };
    writer.with_rust_writer(|w| rnbt::write(parsed.as_ref(), w))
}

fn py_to_tag(v: &Bound<'_, PyAny>) -> PyResult<rnbt::NbtTag> {
    // We can't perfectly recover the original tag type from a bare
    // Python value (int could be Byte/Short/Int/Long). Default policy:
    // - int → Long
    // - float → Double
    // - str → String
    // - list of ints → LongArray
    // - list of anything else → List of inferred element type (best effort)
    // - dict[str, value] → Compound
    if let Ok(d) = v.downcast::<PyDict>() {
        let mut entries: Vec<(String, rnbt::NbtTag)> = Vec::with_capacity(d.len());
        for (k, val) in d.iter() {
            let key: String = k.extract()?;
            entries.push((key, py_to_tag(&val)?));
        }
        return Ok(rnbt::NbtTag::Compound(entries));
    }
    if let Ok(l) = v.downcast::<PyList>() {
        // Empty list → List with TAG_END element type (NBT convention).
        if l.is_empty() {
            return Ok(rnbt::NbtTag::List { element_type: rnbt::TAG_END, items: vec![] });
        }
        let first = l.get_item(0)?;
        if first.is_instance_of::<pyo3::types::PyInt>() {
            // Treat as LongArray.
            let mut out: Vec<i64> = Vec::with_capacity(l.len());
            for it in l.iter() {
                out.push(it.extract()?);
            }
            return Ok(rnbt::NbtTag::LongArray(out));
        }
        // Heterogeneous-ish list of compounds / strings / floats.
        let mut items: Vec<rnbt::NbtTag> = Vec::with_capacity(l.len());
        for it in l.iter() {
            items.push(py_to_tag(&it)?);
        }
        // Use the first item's type byte.
        let element_type = type_of(&items[0]);
        return Ok(rnbt::NbtTag::List { element_type, items });
    }
    if let Ok(s) = v.extract::<String>() {
        return Ok(rnbt::NbtTag::String(s));
    }
    if let Ok(f) = v.extract::<f64>() {
        // Caller may have passed an int; check first.
        if v.is_instance_of::<pyo3::types::PyInt>() {
            let i: i64 = v.extract()?;
            return Ok(rnbt::NbtTag::Long(i));
        }
        return Ok(rnbt::NbtTag::Double(f));
    }
    if let Ok(i) = v.extract::<i64>() {
        return Ok(rnbt::NbtTag::Long(i));
    }
    Err(pyo3::exceptions::PyTypeError::new_err(format!(
        "cannot convert {} to NbtTag",
        v.get_type().qualname()?
    )))
}

fn type_of(t: &rnbt::NbtTag) -> u8 {
    use rnbt::NbtTag::*;
    match t {
        Byte(_) => rnbt::TAG_BYTE,
        Short(_) => rnbt::TAG_SHORT,
        Int(_) => rnbt::TAG_INT,
        Long(_) => rnbt::TAG_LONG,
        Float(_) => rnbt::TAG_FLOAT,
        Double(_) => rnbt::TAG_DOUBLE,
        ByteArray(_) => rnbt::TAG_BYTE_ARRAY,
        String(_) => rnbt::TAG_STRING,
        List { .. } => rnbt::TAG_LIST,
        Compound(_) => rnbt::TAG_COMPOUND,
        IntArray(_) => rnbt::TAG_INT_ARRAY,
        LongArray(_) => rnbt::TAG_LONG_ARRAY,
    }
}

pub fn register(py: Python<'_>, parent: &Bound<'_, PyModule>) -> PyResult<()> {
    let m = PyModule::new_bound(py, "nbt")?;
    m.add_function(wrap_pyfunction!(read, &m)?)?;
    m.add_function(wrap_pyfunction!(read_bytes, &m)?)?;
    m.add_function(wrap_pyfunction!(write, &m)?)?;
    // Tag-type constants.
    m.add("TAG_END", rnbt::TAG_END)?;
    m.add("TAG_BYTE", rnbt::TAG_BYTE)?;
    m.add("TAG_SHORT", rnbt::TAG_SHORT)?;
    m.add("TAG_INT", rnbt::TAG_INT)?;
    m.add("TAG_LONG", rnbt::TAG_LONG)?;
    m.add("TAG_FLOAT", rnbt::TAG_FLOAT)?;
    m.add("TAG_DOUBLE", rnbt::TAG_DOUBLE)?;
    m.add("TAG_BYTE_ARRAY", rnbt::TAG_BYTE_ARRAY)?;
    m.add("TAG_STRING", rnbt::TAG_STRING)?;
    m.add("TAG_LIST", rnbt::TAG_LIST)?;
    m.add("TAG_COMPOUND", rnbt::TAG_COMPOUND)?;
    m.add("TAG_INT_ARRAY", rnbt::TAG_INT_ARRAY)?;
    m.add("TAG_LONG_ARRAY", rnbt::TAG_LONG_ARRAY)?;
    parent.add_submodule(&m)?;
    Ok(())
}
