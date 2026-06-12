#!/usr/bin/env python3
"""Read or change the TITLE (and other string keys) in a PSP/PS3 PARAM.SFO file.

PARAM.SFO layout:
    header (20 bytes)
    index table   (16 bytes per entry)
    key table     (null-terminated key names)
    data table    (values, each padded to its reserved max length)

The script fully rebuilds the file

Usage:
    python sfo_title.py PARAM.SFO                       # show all keys
    python sfo_title.py PARAM.SFO "My New Title"        # set TITLE
    python sfo_title.py PARAM.SFO "My New Title" -o OUT.SFO
    python sfo_title.py PARAM.SFO -k TITLE_00 -v "Foo"  # set an arbitrary key
"""

import argparse
import struct
import sys

MAGIC = b"\x00PSF"

FMT_UTF8_SPECIAL = 0x0004  # not null-terminated
FMT_UTF8 = 0x0204          # null-terminated string
FMT_INT32 = 0x0404


def parse_sfo(data):
    magic, version, key_start, data_start, count = struct.unpack_from("<4sIIII", data, 0)
    if magic != MAGIC:
        raise ValueError(f"Not a PARAM.SFO (bad magic {magic!r})")

    entries = []
    for i in range(count):
        key_off, fmt, used, maxlen, data_off = struct.unpack_from("<HHIII", data, 20 + i * 16)

        # key name
        ks = key_start + key_off
        ke = data.index(b"\x00", ks)
        key = data[ks:ke].decode("utf-8")

        raw = data[data_start + data_off: data_start + data_off + used]
        if fmt == FMT_INT32:
            value = struct.unpack("<I", raw)[0]
        else:
            value = raw.rstrip(b"\x00").decode("utf-8", "replace")

        entries.append({"key": key, "fmt": fmt, "maxlen": maxlen, "value": value})
    return version, entries


def build_sfo(version, entries):
    key_table = bytearray()
    data_table = bytearray()
    index = bytearray()

    for e in entries:
        key_off = len(key_table)
        key_table += e["key"].encode("utf-8") + b"\x00"

        fmt = e["fmt"]
        if fmt == FMT_INT32:
            raw = struct.pack("<I", int(e["value"]))
            used = 4
            maxlen = 4
        else:
            b = e["value"].encode("utf-8")
            if fmt == FMT_UTF8:
                b += b"\x00"
            used = len(b)
            # keep original reservation if it still fits, else grow (16-byte aligned)
            maxlen = max(e["maxlen"], (used + 15) & ~15)
            raw = b + b"\x00" * (maxlen - used)

        data_off = len(data_table)
        data_table += raw
        index += struct.pack("<HHIII", key_off, fmt, used, maxlen, data_off)

    # pad key table to 4-byte alignment (PSP convention)
    while len(key_table) % 4:
        key_table += b"\x00"

    header_size = 20 + len(index)
    key_start = header_size
    data_start = key_start + len(key_table)

    header = struct.pack("<4sIIII", MAGIC, version, key_start, data_start, len(entries))
    return bytes(header + index + key_table + data_table)


def main():
    ap = argparse.ArgumentParser(description="Read/modify a PARAM.SFO TITLE.")
    ap.add_argument("sfo", help="path to PARAM.SFO")
    ap.add_argument("title", nargs="?", help="new TITLE value")
    ap.add_argument("-k", "--key", default="TITLE", help="key to modify (default TITLE)")
    ap.add_argument("-v", "--value", help="new value for --key")
    ap.add_argument("-o", "--output", help="output path (default: overwrite input)")
    args = ap.parse_args()

    with open(args.sfo, "rb") as f:
        data = f.read()

    version, entries = parse_sfo(data)

    key = args.key
    value = args.value if args.value is not None else args.title

    if value is None:
        width = max(len(e["key"]) for e in entries)
        for e in entries:
            print(f"  {e['key']:<{width}}  = {e['value']!r}  (max {e['maxlen']})")
        return

    for e in entries:
        if e["key"] == key:
            e["value"] = value
            break
    else:
        sys.exit(f"Key {key!r} not found. Keys: {[e['key'] for e in entries]}")

    out = args.output or args.sfo
    with open(out, "wb") as f:
        f.write(build_sfo(version, entries))
    print(f"Set {key} = {value!r} -> {out}")


if __name__ == "__main__":
    main()
