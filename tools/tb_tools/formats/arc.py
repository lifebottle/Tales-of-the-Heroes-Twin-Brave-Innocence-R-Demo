import gzip
import struct
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path

import crunch64
from tb_tools.formats.ppt import PPT_MAGIC, Ppt
from tb_tools.utils.fileio import FileIO

ARC_MAGIC = b"EZBIND\x00\x00"
GZIP_MAGIC = b"\x1f\x8b"
ZIP_MAGIC = b"PK"


def _grouper(iterable, n, fillvalue=None):
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


@dataclass(slots=True)
class ArcFile:
    name: str
    data: bytes
    hash: int
    is_compressed: bool = False
    is_arc: bool = False
    gzip_ts: int = 0

    # Stuff used when overlaying
    _name_off: int = 0
    _data_off: int = 0
    _data_size: int = 0


class Arc:
    def __init__(self, path: Path | bytes):
        with FileIO(path) as f:
            if f.read(8) != ARC_MAGIC:
                raise ValueError("Invalid EZBIND magic!")

            count = f.read_int32()
            self.alignment = f.read_int32()
            data = f.read_struct(f"<{count * 4}I")
            names = []
            for _ in range(count):
                names.append(f.read_string())
            self._names = names

            files = []
            for name_idx, size, offset, hsh in _grouper(data, 4):
                data = f.read_at(offset, size)
                is_comp = False
                is_arc = False
                gzip_ts = 0

                if data[:2] == ZIP_MAGIC:
                    raise ValueError("ZIP-based compressed files not supported!")

                if data[:2] == GZIP_MAGIC:
                    gzip_ts = f.read_uint32(offset + 4)
                    data = gzip.decompress(data)
                    is_comp = True

                if len(data) > 8 and data[:8] == ARC_MAGIC:
                    is_arc = True

                name = f.read_string(pos=name_idx)

                calc_hash = 0
                for c in name:
                    calc_hash *= 0x25
                    calc_hash += ord(c)
                    calc_hash &= 0xFFFFFFFF

                if calc_hash != hsh:
                    raise ValueError("Mismatched hashes in file list!")

                file = ArcFile(name, data, hsh, is_comp, is_arc, gzip_ts)
                files.append(file)
            self.files: list[ArcFile] = files

    def overlay(self, folder: Path) -> bytes:
        out_arc = b""
        with FileIO(out_arc, "wb") as arc:
            arc.write(ARC_MAGIC)
            arc.write_uint32(len(self.files))
            arc.write_uint32(self.alignment)

            # File table, fill out later
            arc.write(b"\x00" * len(self.files) * 4 * 4)

            # Name table
            for file in self.files:
                file._name_off = arc.tell()
                arc.write(file.name.encode() + b"\x00")

            # File contents
            arc.write_padding(self.alignment)
            for file in self.files:
                repl_path = folder / file.name

                if repl_path.suffix == ".ppt":
                    repl_path = repl_path.with_suffix(".png")

                # doesn't exist? Pic the OG
                if not repl_path.exists():
                    data = file.data

                # ARC files can be a folder or file
                elif file.is_arc:
                    if repl_path.is_dir():
                        data = Arc(file.data).overlay(repl_path)
                    else:
                        data = repl_path.read_bytes()

                # PPT files are converted from PNG
                elif len(file.data) > 4 and file.data[:4] == PPT_MAGIC:
                    ppt = Ppt(file.data)
                    ppt.update(repl_path)
                    data = ppt.get_bytes()
                else:
                    data = repl_path.read_bytes()

                if file.is_compressed:
                    # TODO: Factor this out
                    out = b"\x1f\x8b"              # magic
                    out += b"\x08"                  # deflate
                    out += b"\x08"                  # filename
                    out += struct.pack("<I", file.gzip_ts) # timestamp
                    out += b"\x00"                  # level 0
                    out += b"\x03"                  # UNIX
                    out += file.name.encode() + b"\x00"
                    out += crunch64.gzip.compress(data, level=6)
                    data = out

                file._data_off = arc.tell()
                file._data_size = len(data)

                arc.write(data)
                arc.write_padding(self.alignment)

            # Finish file table
            arc.seek(0x10)
            for file in self.files:
                arc.write_uint32(file._name_off)
                arc.write_uint32(file._data_size)
                arc.write_uint32(file._data_off)
                arc.write_uint32(file.hash)

            return bytes(arc.get_buffer())

    def save_all(self, path: Path) -> None:
        path.mkdir(exist_ok=True, parents=True)
        for file in self.files:
            o = path / file.name
            data = file.data

            # keep this in case we want to make BDIs from nothing
            # if file.is_compressed:
            #     o.with_suffix(".gz" + "".join(o.suffixes))

            if file.is_arc:
                Arc(data).save_all(o)
            elif len(data) > 4 and data[:4] == PPT_MAGIC:
                Ppt(data).save_png(o)
            else:
                o.write_bytes(data)
