import gzip
import json
import mmap
import struct
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

import crunch64
from tb_tools.formats.arc import ARC_MAGIC, Arc
from tb_tools.formats.ppt import Ppt
from tb_tools.utils.fileio import FileIO
from tqdm.rich import tqdm

GZIP_MAGIC = b"\x1f\x8b"


@dataclass
class BdiFile:
    hash: int
    offset: int
    size: int
    # Marks either NBI (False) or everything else (True)
    is_file: bool
    rel_path: Path
    is_compressed: bool = False
    is_arc: bool = False
    replacement: Path | None = None
    _gzip_ts: int = 0


class Bdi:
    def __init__(self, path: Path, names_path: Path | None = None, crc_bits: int = 15):
        self.path: Path = path
        self.names_path: Path | None = names_path
        self._fp: BinaryIO | None = None
        self._mm = None
        self._crc_bits = crc_bits
        self.files: list[BdiFile] = []
        self.name_map: dict[int, str] = {}
        self._name_mapi: dict[str, int] = {}
        self.file_map: dict[int, BdiFile] = {}
        self.timestamp: int = 0
        self.initialized = False

        self._parse_hashes()

    def __enter__(self):
        self._fp = self.path.open("rb")
        self._mm = mmap.mmap(self._fp.fileno(), 0, access=mmap.ACCESS_READ)
        self._parse_header()
        self.initialized = True
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        if self._mm is not None:
            self._mm.close()
            self._mm = None
        if self._fp is not None:
            self._fp.close()
            self._fp = None

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
            self._name_mapi = {v: k for k, v in data.items()}

    def _parse_header(self):
        fp = self._fp
        assert fp is not None

        # Format starts with an index table using the lower N bits of
        # the filename CRC32 hash as the index, each entry is a short
        # so skip that
        fp.seek((1 << self._crc_bits) * 2)

        # First 2 entries are dummies that hold the file count and
        # a creation timestamp, after that each file entry is 2 ints
        # file hash followed by packed offset + padding
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
            file.is_arc = self._is_arc_file(file)
            if file.is_compressed:
                file._gzip_ts = self._get_gz_timestamp(file)
            self.files.append(file)
            self.file_map[file_hash] = file

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

    def _scramble_audio(self, b: bytes) -> bytes:
        decoded = bytearray(0x80)
        for i in range(0x80):
            j = (7 + 11 * i) & 0x7F
            decoded[j] = b[i] ^ j
        return bytes(decoded) + b[0x80:]

    def _read_blob(
        self, p: BdiFile, decompress: bool = True, unscramble: bool = True
    ) -> tuple[Path, bytes]:
        fp = self._fp
        mm = self._mm

        assert fp is not None
        assert mm is not None

        start = p.offset
        end = start + p.size

        b = mm[start:end]

        # Handle gzipped files
        if decompress and p.is_compressed:
            b = gzip.decompress(b)

        # Handle scrambled audio
        if unscramble and p.rel_path.suffix in (".na", ".at3"):
            b = self._scramble_audio(b)

        return p.rel_path, b

    def hash_name(self, name: str) -> int:
        return zlib.crc32(name.encode("ascii"))

    def _get_replacement_data(self, file: BdiFile, folder: Path) -> bytes:
        repl_path = folder / file.rel_path

        if repl_path.suffix == ".ppt":
            repl_path = repl_path.with_suffix(".png")

        # Doesn't exist? Pick the original
        if not repl_path.exists():
            return self._read_blob(file, False, False)[1]

        # We always read the original ppt, so no need for
        # name markers
        if file.rel_path.suffix == ".ppt":
            ppt = Ppt(self._read_blob(file)[1])
            ppt.update(repl_path)
            data = ppt.get_bytes()

        # Arcs can either be provided as an overlay folder
        # or fully built file
        elif file.is_arc:
            print(repl_path)
            if repl_path.is_dir():
                arc = Arc(self._read_blob(file)[1])
                data = arc.overlay(repl_path)
            else:
                data = repl_path.read_bytes()

        # Audio needs the header scrambled
        elif repl_path.suffix in (".na", ".at3"):
            data = self._scramble_audio(repl_path.read_bytes())

        # Nothing special to do
        else:
            data = repl_path.read_bytes()

        if file.is_compressed:
            # TODO: Factor this out
            out = b"\x1f\x8b"              # magic
            out += b"\x08"                  # deflate
            out += b"\x08"                  # filename
            out += struct.pack("<I", file._gzip_ts) # timestamp
            out += b"\x00"                  # level 0
            out += b"\x03"                  # UNIX
            out += file.rel_path.name.encode() + b"\x00"
            out += crunch64.gzip.compress(data, level=6)
            return out

        return data

    def update_and_save(self, new_bdi: Path, folder: Path):
        if not self.initialized:
            raise ValueError("BDI file not initialized yet!")

        if not folder.is_dir():
            raise ValueError("Path supplied is not a folder!")

        with FileIO(new_bdi, "wb") as nbdi:
            # Calculate header size
            index_table_size = (1 << self._crc_bits) * 2  # Index table (shorts)
            file_count = len(self.files) + 2  # +2 for the dummy entries
            header_size = index_table_size + (file_count + 2) * 8

            nbdi.write(b"\x00" * header_size)
            nbdi.write_padding(0x800)
            last_entry = len(self.files) - 1
            for i, file in enumerate(self.files):
                # Write index in table
                if i != last_entry:
                    crc_index = file.hash & ((1 << self._crc_bits) - 1)
                    j = 0
                    while nbdi.read_uint16((crc_index + j) * 2) != 0:
                        j += 1
                      # +2 because entry 0 is dummy
                    nbdi.write_uint16(i + 2, (crc_index + j) * 2)

                # Write file contents
                offset = nbdi.tell()
                data = self._get_replacement_data(file, folder)
                nbdi.write(data)
                padding = nbdi.write_padding(0x800)
                # print(f"0x{offset:08X} 0x{padding:08X}")

                # Write file info in file table
                packed_offset = offset & 0x7FFFF800
                packed_offset |= padding & 0x000007FF
                if file.is_file:
                    packed_offset |= 0x80000000
                nbdi.write_uint32(file.hash, (index_table_size + 16) + i * 8)
                nbdi.write_uint32(packed_offset, (index_table_size + 20) + i * 8)

            # Write dummy entries (holds file count and timestamp)
            nbdi.write_uint32(0, index_table_size + 0)  # dummy hash
            nbdi.write_uint32(len(self.files) - 1, index_table_size + 4)
            nbdi.write_uint32(0, index_table_size + 8)  # dummy hash
            nbdi.write_uint32(self.timestamp, index_table_size + 12)

    def get_file(self, name: str) -> tuple[Path, bytes] | tuple[None, None]:
        if not self.initialized:
            raise ValueError("BDI file not initialized yet!")

        if name.startswith("$"):
            _hash = int(name[1:], base=16)
        else:
            _hash = self._name_mapi.get(name, 0)

        p: BdiFile | None = self.file_map.get(_hash)
        if p is not None:
            return self._read_blob(p)

        return None, None

    def get_timestamp(self) -> str:
        dt = datetime.fromtimestamp(self.timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def iter_files(self) -> Iterator[tuple[Path, bytes]]:
        if not self.initialized:
            raise ValueError("BDI file not initialized yet!")

        for file in self.files:
            yield self._read_blob(file)

    def save_all(self, out_dir: Path):
        for rel_path, data in self.iter_files():
            out_path: Path = out_dir / rel_path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(data)

    def save_all_p(self, out_dir: Path):
        with tqdm(total=len(self.files), desc="Extracting") as pbar:
            for rel_path, data in self.iter_files():
                pbar.set_description(f"{rel_path.as_posix()}")

                out_path: Path = out_dir / rel_path
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(data)
                pbar.update(1)
