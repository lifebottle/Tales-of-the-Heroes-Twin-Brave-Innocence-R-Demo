"""
Standalone BDI Repacker
Repacks BDI archives using original metadata and files from extracted/patched directories.

Usage:
    python bdi_repack.py

This script reads the original BDI to get metadata (file order, compression, timestamp)
and rebuilds it using files from 1_extracted/all (with replacements from 3_patched/all).
"""

import argparse
import gzip
import json
import mmap
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
import crunch64

GZIP_MAGIC = b"\x1f\x8b"
ARC_MAGIC = b"EZBIND\x00\x00"


@dataclass
class BdiFile:
    hash: int
    offset: int
    size: int
    is_file: bool  # Marks either NBI (False) or everything else (True)
    rel_path: Path
    is_compressed: bool = False
    gzip_ts: int = 0
    is_arc: bool = False


class BdiReader:
    """Lightweight BDI reader to extract metadata only"""
    
    def __init__(self, path: Path, names_path: Path | None = None, crc_bits: int = 15):
        self.path = path
        self.names_path = names_path
        self._fp: BinaryIO | None = None
        self._mm = None
        self._crc_bits = crc_bits
        self.files: list[BdiFile] = []
        self.name_map: dict[int, str] = {}
        self.timestamp: int = 0
        
        self._parse_hashes()
    
    def __enter__(self):
        self._fp = self.path.open("rb")
        self._mm = mmap.mmap(self._fp.fileno(), 0, access=mmap.ACCESS_READ)
        self._parse_header()
        return self
    
    def __exit__(self, exc_type, exc, tb):
        if self._mm is not None:
            self._mm.close()
        if self._fp is not None:
            self._fp.close()
        return False
    
    def _parse_hashes(self):
        if self.names_path is None:
            return
        
        def _Keys2int(x):
            if isinstance(x, dict):
                return {int(k, base=16): v for k, v in x.items()}
            return x
        
        with self.names_path.open("r") as f:
            data = json.load(f, object_hook=_Keys2int)
            self.name_map = data
    
    def _parse_header(self):
        fp = self._fp
        assert fp is not None
        
        # Skip index table
        fp.seek((1 << self._crc_bits) * 2)
        
        # Read file count and timestamp
        _, file_count, _, ts = struct.unpack("<IIII", fp.read(16))
        self.timestamp = ts
        
        file_count += 2
        pairs = struct.unpack(f"<{file_count * 2}I", fp.read(file_count * 8))
        
        for i in range(file_count - 1):
            file_hash = pairs[i * 2 + 0]
            file_off = pairs[i * 2 + 1] & 0x7FFFF800
            file_pad = pairs[i * 2 + 1] & 0x000007FF
            flag = (pairs[i * 2 + 1] & 0x80000000) != 0
            next_off = pairs[i * 2 + 3] & 0x7FFFF800
            file_size = next_off - file_off - file_pad
            
            file_path = Path(self.name_map.get(file_hash, f"_no_name/${file_hash:08X}"))
            file = BdiFile(file_hash, file_off, file_size, flag, file_path)
            file.is_compressed = self._is_gz_file(file)
            if file.is_compressed:
                file.gzip_ts = self._get_gz_timestamp(file)
            file.is_arc = self._is_arc_file(file)
            self.files.append(file)
    
    def _is_gz_file(self, p: BdiFile) -> bool:
        assert self._mm is not None
        start = p.offset
        return self._mm[start : start + 2] == GZIP_MAGIC
    
    def _get_gz_timestamp(self, p: BdiFile) -> int:
        assert self._mm is not None
        start = p.offset
        return struct.unpack("<I", self._mm[start + 4 : start + 8])[0]
    
    def _is_arc_file(self, p: BdiFile) -> bool:
        assert self._mm is not None
        start = p.offset
        return self._mm[start : start + 8] == ARC_MAGIC


def _scramble_audio(b: bytes) -> bytes:
    """Scramble audio files (inverse of descramble in extraction)"""
    decoded = bytearray(b[:0x80])
    for i in range(0x80):
        j = (7 + 11 * i) & 0x7F
        decoded[i] = b[j] ^ j
    return bytes(decoded) + b[0x80:]


def get_file_data(file: BdiFile, extracted_dir: Path, patched_dir: Path) -> bytes:
    """Get file data, preferring patched version over extracted"""
    # Check patched directory first
    patched_path = patched_dir / file.rel_path
    if patched_path.exists():
        print(f"  Using patched: {file.rel_path}")
        data = patched_path.read_bytes()
    else:
        # Fall back to extracted directory
        extracted_path = extracted_dir / file.rel_path
        if not extracted_path.exists():
            raise FileNotFoundError(f"File not found in either directory: {file.rel_path}")
        data = extracted_path.read_bytes()
    
    return data


def repack_bdi(
    original_bdi: Path,
    hashes_path: Path,
    extracted_dir: Path,
    patched_dir: Path,
    output_bdi: Path,
    crc_bits: int = 15
):
    """Repack BDI file using original metadata and file data from extracted/patched folders"""
    
    print(f"Reading original BDI metadata from: {original_bdi}")
    
    # Read original BDI to get metadata
    with BdiReader(original_bdi, hashes_path, crc_bits=crc_bits) as bdi:
        timestamp = bdi.timestamp
        files = bdi.files
        
        from datetime import datetime
        dt = datetime.fromtimestamp(timestamp)
        print(f"Original timestamp: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total files: {len(files)}")
        print(f"\nRepacking files...")
        
        # Prepare output buffer
        output_data = bytearray()
        
        # Calculate header size
        index_table_size = (1 << crc_bits) * 2  # Index table (shorts)
        file_count = len(files) + 2  # +2 for the dummy entries
        header_size = index_table_size + (file_count + 2) * 8  # +2 for first dummy entry
        
        # Build file data list
        file_data_list = []
        
        for file in files:
            # Get file data (patched or extracted)
            data = get_file_data(file, extracted_dir, patched_dir)
            
            # Apply audio scrambling if needed
            if file.rel_path.suffix in (".na", ".at3"):
                data = _scramble_audio(data)
            
            # Apply compression if original was compressed
            if file.is_compressed:
                out = b"\x1f\x8b"              # magic
                out += b"\x08"                  # deflate
                out += b"\x08"                  # filename
                out += struct.pack("<I", file.gzip_ts) # timestamp
                out += b"\x00"                  # level 0
                out += b"\x03"                  # UNIX
                out += file.rel_path.name.encode() + b"\x00"
                out += crunch64.gzip.compress(data, level=6)
                data = out
            
            file_data_list.append(data)
        
        # Calculate offsets and padding
        current_offset = (header_size + 0x7FF) & ~0x7FF
        file_entries = []
        
        for i, (file, data) in enumerate(zip(files, file_data_list)):
            # Align to 2048-byte boundary
            alignment = 2048
            padding = (alignment - ((current_offset + file.size) % alignment)) % alignment
            
            # Store entry info
            file_entries.append({
                'hash': file.hash,
                'offset': current_offset,
                'padding': padding,
                'size': len(data),
                'data': data,
                'is_file': file.is_file
            })
            
            current_offset += len(data) + padding
        
        # Build the BDI file
        # 1. Build index table (using lower N bits of CRC32)
        index_table = [0x0000] * (1 << crc_bits)
        
        for i, entry in enumerate(file_entries[:-1]):
            crc_index = entry['hash'] & ((1 << crc_bits) - 1)
            j = 0
            while index_table[crc_index + j] != 0:
                j += 1
            index_table[crc_index + j] = i + 2  # +2 because entry 0 is dummy
        
        # Write index table
        for idx in index_table:
            output_data += struct.pack("<H", idx)
        
        # 2. Write dummy entry (holds file count and timestamp)
        output_data += struct.pack("<I", 0)  # dummy hash
        output_data += struct.pack("<I", len(files) - 1)  # file count
        output_data += struct.pack("<I", 0)  # dummy hash
        output_data += struct.pack("<I", timestamp)  # timestamp
        
        # 3. Write file entries (hash + packed offset)
        for entry in file_entries:
            packed_offset = entry['offset'] & 0x7FFFF800
            packed_offset |= entry['padding'] & 0x000007FF
            if entry['is_file']:
                packed_offset |= 0x80000000
            
            output_data += struct.pack("<I", entry['hash'])
            output_data += struct.pack("<I", packed_offset)

        output_data += b'\x00' * ((2048 - (len(output_data) % 2048)) % 2048)

        # 4. Write file data with padding
        for entry in file_entries:
            output_data += entry['data']
            output_data += b'\x00' * entry['padding']
        
        # Write output file
        print(f"\nWriting repacked BDI to: {output_bdi}")
        output_bdi.parent.mkdir(parents=True, exist_ok=True)
        output_bdi.write_bytes(output_data)
        
        print(f"Done! Output size: {len(output_data):,} bytes")


def main():
    # Auto-detect repo root (3 levels up from script: scripts -> tb_tools -> tools -> repo)
    script_dir = Path(__file__).parent.resolve()
    repo_root = script_dir.parent.parent.parent
    
    parser = argparse.ArgumentParser(
        description="Repack BDI archives with original metadata"
    )
    
    parser.add_argument(
        "--original",
        help="path to original BDI file",
        type=Path,
        default=repo_root / "0_disc/PSP_GAME/USRDIR/namco.bdi",
        metavar="PATH",
    )
    parser.add_argument(
        "--hashes",
        help="path to JSON with hash-name pairs",
        type=Path,
        default=repo_root / "project/hashes_trial_toir.json",
        metavar="PATH",
    )
    parser.add_argument(
        "--extracted",
        help="path to extracted files directory",
        type=Path,
        default=repo_root / "1_extracted/all",
        metavar="PATH",
    )
    parser.add_argument(
        "--patched",
        help="path to patched files directory",
        type=Path,
        default=repo_root / "3_patched/all",
        metavar="PATH",
    )
    parser.add_argument(
        "--output",
        help="path to output repacked BDI file",
        type=Path,
        default=repo_root / "3_patched/namco.bdi",
        metavar="PATH",
    )
    parser.add_argument(
        "--crc-bits",
        help="number of CRC bits for index table",
        type=int,
        default=15,
        metavar="N",
    )
    
    args = parser.parse_args()
    
    repack_bdi(
        original_bdi=args.original,
        hashes_path=args.hashes,
        extracted_dir=args.extracted,
        patched_dir=args.patched,
        output_bdi=args.output,
        crc_bits=args.crc_bits
    )


if __name__ == "__main__":
    main()