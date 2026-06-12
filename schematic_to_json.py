#!/usr/bin/env python3
"""
Low-level NBT reader for Minecraft .schematic files.

For the full conversion pipeline use: python convert.py input.schematic --name "Map Name"
For in-memory parsing use: schematic_parser.parse_schematic_file(path)
"""

import argparse
import gzip
import json
import pathlib
import struct
import sys

TAG_End = 0
TAG_Byte = 1
TAG_Short = 2
TAG_Int = 3
TAG_Long = 4
TAG_Float = 5
TAG_Double = 6
TAG_Byte_Array = 7
TAG_String = 8
TAG_List = 9
TAG_Compound = 10
TAG_Int_Array = 11
TAG_Long_Array = 12


def _read_exact(f, n):
    data = f.read(n)
    if len(data) != n:
        raise EOFError("Unexpected end of NBT data")
    return data


def _read_byte(f):
    return _read_exact(f, 1)[0]


def _read_short(f):
    return struct.unpack(">h", _read_exact(f, 2))[0]


def _read_ushort(f):
    return struct.unpack(">H", _read_exact(f, 2))[0]


def _read_int(f):
    return struct.unpack(">i", _read_exact(f, 4))[0]


def _read_long(f):
    return struct.unpack(">q", _read_exact(f, 8))[0]


def _read_float(f):
    return struct.unpack(">f", _read_exact(f, 4))[0]


def _read_double(f):
    return struct.unpack(">d", _read_exact(f, 8))[0]


def _read_string(f):
    length = _read_ushort(f)
    if length == 0:
        return ""
    return _read_exact(f, length).decode("utf-8")


def _read_tag_payload(f, tag_type):
    if tag_type == TAG_End:
        return None
    if tag_type == TAG_Byte:
        return struct.unpack(">b", _read_exact(f, 1))[0]
    if tag_type == TAG_Short:
        return _read_short(f)
    if tag_type == TAG_Int:
        return _read_int(f)
    if tag_type == TAG_Long:
        return _read_long(f)
    if tag_type == TAG_Float:
        return _read_float(f)
    if tag_type == TAG_Double:
        return _read_double(f)
    if tag_type == TAG_Byte_Array:
        length = _read_int(f)
        return list(_read_exact(f, length))
    if tag_type == TAG_String:
        return _read_string(f)
    if tag_type == TAG_List:
        child_type = _read_byte(f)
        length = _read_int(f)
        return [_read_tag_payload(f, child_type) for _ in range(length)]
    if tag_type == TAG_Compound:
        obj = {}
        while True:
            t = _read_byte(f)
            if t == TAG_End:
                break
            name = _read_string(f)
            obj[name] = _read_tag_payload(f, t)
        return obj
    if tag_type == TAG_Int_Array:
        length = _read_int(f)
        return [_read_int(f) for _ in range(length)]
    if tag_type == TAG_Long_Array:
        length = _read_int(f)
        return [_read_long(f) for _ in range(length)]
    raise ValueError(f"Unknown NBT tag type: {tag_type}")


def _read_named_tag(f):
    tag_type = _read_byte(f)
    if tag_type == TAG_End:
        return None, None, TAG_End
    name = _read_string(f)
    payload = _read_tag_payload(f, tag_type)
    return name, payload, tag_type


def read_nbt_from_gzipped_file(path):
    with gzip.open(path, "rb") as f:
        name, payload, tag_type = _read_named_tag(f)
        if tag_type != TAG_Compound:
            raise ValueError(f"Root tag is not a Compound (got {tag_type})")
        return name, payload


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Convert .schematic to JSON (debug utility). Prefer: python convert.py"
    )
    parser.add_argument("input", help=".schematic file path")
    parser.add_argument("output", nargs="?", help="Output JSON path")
    args = parser.parse_args(argv)

    in_path = pathlib.Path(args.input)
    out_path = pathlib.Path(args.output) if args.output else in_path.with_suffix(".json")

    root_name, root_payload = read_nbt_from_gzipped_file(in_path)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({root_name: root_payload}, f, ensure_ascii=False, indent=2)
    print(f"Wrote JSON to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
