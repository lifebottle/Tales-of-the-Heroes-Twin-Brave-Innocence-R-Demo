#!/usr/bin/env python3
"""
Standalone ARC/EZBIND Repacker
Repacks modified files into ARC archives using the original archive as a template.
"""

import argparse
import gzip
from pathlib import Path

# ARC format constants
ARC_MAGIC = b"EZBIND\x00\x00"
GZIP_MAGIC = b"\x1f\x8b"
ZIP_MAGIC = b"PK"


# -----------------------------
# Repo root detection
# -----------------------------
def find_repo_root(start: Path) -> Path:
    """
    Walk upward until we find a known repo marker.
    Adjust "1_extracted" if your repo structure changes.
    """
    for parent in start.resolve().parents:
        if (parent / "1_extracted").exists():
            return parent
    raise RuntimeError("Could not locate repo root (missing '1_extracted' folder)")


ROOT_DIR = find_repo_root(Path(__file__))


def resolve_from_root(p: Path) -> Path:
    """
    Resolve CLI paths as if they are relative to repo root.
    """
    if p.is_absolute():
        return p
    return ROOT_DIR / p


# -----------------------------
# ARC utilities
# -----------------------------
def calculate_hash(name: str) -> int:
    calc_hash = 0
    for c in name:
        calc_hash *= 0x25
        calc_hash += ord(c)
        calc_hash &= 0xFFFFFFFF
    return calc_hash


def align_offset(offset: int, alignment: int) -> int:
    if alignment <= 1:
        return offset
    remainder = offset % alignment
    return offset if remainder == 0 else offset + (alignment - remainder)


class ArcFileInfo:
    def __init__(self, name: str, is_compressed: bool, original_order: int):
        self.name = name
        self.is_compressed = is_compressed
        self.original_order = original_order


def read_arc_structure(arc_path: Path) -> tuple[int, list[ArcFileInfo]]:
    with open(arc_path, 'rb') as f:
        magic = f.read(8)
        if magic != ARC_MAGIC:
            raise ValueError(f"Invalid EZBIND magic in {arc_path}!")

        count = int.from_bytes(f.read(4), 'little')
        alignment = int.from_bytes(f.read(4), 'little')

        table_data = []
        for _ in range(count):
            name_offset = int.from_bytes(f.read(4), 'little')
            size = int.from_bytes(f.read(4), 'little')
            data_offset = int.from_bytes(f.read(4), 'little')
            hash_val = int.from_bytes(f.read(4), 'little')
            table_data.append((name_offset, size, data_offset, hash_val))

        file_infos = []

        for idx, (name_offset, size, data_offset, hash_val) in enumerate(table_data):
            current_pos = f.tell()

            f.seek(name_offset)
            name_bytes = b""
            while True:
                b = f.read(1)
                if b == b'\x00':
                    break
                name_bytes += b
            name = name_bytes.decode('ascii')

            f.seek(current_pos)

            f.seek(data_offset)
            data_header = f.read(2)
            is_compressed = (data_header == GZIP_MAGIC)

            file_infos.append(ArcFileInfo(name, is_compressed, idx))

    return alignment, file_infos


# -----------------------------
# Repacker
# -----------------------------
def repack_arc(original_arc: Path, modified_files_dir: Path, output_arc: Path, verbose: bool = True):
    if verbose:
        print(f"Reading original ARC structure from: {original_arc}")

    alignment, file_infos = read_arc_structure(original_arc)

    if verbose:
        print(f"  Alignment: {alignment}")
        print(f"  File count: {len(file_infos)}")

    files_data = []

    for file_info in file_infos:
        file_path = modified_files_dir / file_info.name

        if not file_path.exists():
            raise FileNotFoundError(f"Modified file not found: {file_path}")

        data = file_path.read_bytes()

        if file_info.is_compressed:
            if verbose:
                print(f"  Compressing: {file_info.name}")
            data = gzip.compress(data)
        else:
            if verbose:
                print(f"  Keeping uncompressed: {file_info.name}")

        files_data.append((file_info.name, data))

    count = len(files_data)
    header_size = 16
    file_table_size = count * 16

    name_section_offset = header_size + file_table_size
    current_offset = name_section_offset

    name_offsets = []
    for name, _ in files_data:
        name_offsets.append(current_offset)
        current_offset += len(name) + 1

    data_section_start = align_offset(current_offset, alignment)

    current_offset = data_section_start
    file_entries = []

    for (name, data), name_offset in zip(files_data, name_offsets):
        size = len(data)
        data_offset = current_offset
        hash_val = calculate_hash(name)

        file_entries.append({
            'name_offset': name_offset,
            'size': size,
            'data_offset': data_offset,
            'hash': hash_val,
            'name': name,
            'data': data
        })

        current_offset = align_offset(current_offset + size, alignment)

    if verbose:
        print(f"\nWriting ARC to: {output_arc}")

    output_arc.parent.mkdir(parents=True, exist_ok=True)

    with open(output_arc, 'wb') as f:
        f.write(ARC_MAGIC)
        f.write(count.to_bytes(4, 'little'))
        f.write(alignment.to_bytes(4, 'little'))

        for entry in file_entries:
            f.write(entry['name_offset'].to_bytes(4, 'little'))
            f.write(entry['size'].to_bytes(4, 'little'))
            f.write(entry['data_offset'].to_bytes(4, 'little'))
            f.write(entry['hash'].to_bytes(4, 'little'))

        for entry in file_entries:
            f.write(entry['name'].encode('ascii') + b'\x00')

        while f.tell() < data_section_start:
            f.write(b'\x00')

        for entry in file_entries:
            if f.tell() != entry['data_offset']:
                raise ValueError(
                    f"Offset mismatch for {entry['name']}: "
                    f"expected {entry['data_offset']}, got {f.tell()}"
                )

            f.write(entry['data'])

            next_offset = align_offset(f.tell(), alignment)
            while f.tell() < next_offset:
                f.write(b'\x00')

    if verbose:
        print(f"Done! Wrote {len(file_entries)} files to {output_arc}")


# -----------------------------
# CLI
# -----------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Repack ARC/EZBIND files using original archive as template"
    )

    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quiet", action="store_true")

    args = parser.parse_args()

    # 🔥 KEY FIX: resolve ALL paths relative to repo root
    original = resolve_from_root(args.original)
    input_dir = resolve_from_root(args.input)
    output = resolve_from_root(args.output)

    try:
        repack_arc(
            original_arc=original,
            modified_files_dir=input_dir,
            output_arc=output,
            verbose=not args.quiet
        )
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())