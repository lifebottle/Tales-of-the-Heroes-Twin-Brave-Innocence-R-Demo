from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

import imagequant
from PIL import Image, ImageOps
from tb_tools.utils.fileio import FileIO


def _next_pow2(v):
    return 1 if v <= 1 else 1 << (v - 1).bit_length()


PPT_MAGIC = b"ppt\x00"
PPC_MAGIC = b"ppc\x00"
PPT_HEADER_SIZE = 0x20
PPC_HEADER_SIZE = 0x10


# Pixel Storage Mode
class PSM(IntEnum):
    RGBA_5551 = 1
    RGBA_4444 = 2
    RGBA_8888 = 3
    INDEXED_4 = 4
    INDEXED_8 = 5


@dataclass
class Size:
    width: int
    height: int


class Ppt:
    def __init__(self, path: Path | bytes, detile: bool = True) -> None:
        self.tex_psm: PSM = PSM.RGBA_8888
        self.pal_psm: PSM = PSM.RGBA_8888
        self.texbuf_mode: int = 0
        self.pal_cnt: int = 0
        self.gpu_size: Size = Size(0, 0)
        self.tex_size: Size = Size(0, 0)
        self.img_size: Size = Size(0, 0)
        self.palette: bytes = b""
        self.raster: bytes = b""

        with FileIO(path) as f:
            assert f.read(4) == PPT_MAGIC, "Wrong MAGIC for PPT file!"
            self.gpu_size = Size(f.read_uint16(), f.read_uint16())
            self.tex_psm = PSM(f.read_uint16())
            self.texbuf_mode = f.read_uint16()
            self.tex_size = Size(f.read_uint16(), f.read_uint16())
            self.img_size = Size(f.read_uint16(), f.read_uint16())
            self.reserved0 = f.read_uint32()
            self.pal_ptr = f.read_uint32()
            self.reserved1 = f.read_uint32()
            self._reserved0 = 0
            self._reserved1 = 0

            # if reserved0 != 0 or reserved1 != 0:
            #     print(f"PPT reserved fields are not 0! {reserved0} | {reserved1}")

            self._read_raster(f)
            self._read_palette(f)

            if detile:
                self._tiler(True)

    def _tiler(self, decode: bool) -> None:
        tile_w = 16
        tile_h = 8

        if self.tex_psm in (PSM.RGBA_5551, PSM.RGBA_4444):
            tile_w = 8
        elif self.tex_psm == PSM.RGBA_8888:
            tile_w = 4
        elif self.tex_psm == PSM.INDEXED_4:
            tile_w = 32
        elif self.tex_psm == PSM.INDEXED_8:
            tile_w = 16

        tex_w = self.tex_size.width
        tex_h = self.tex_size.height

        # bytes per row in output
        bytes_per_row = (self.tex_size.width * 16) // tile_w

        output = bytearray(bytes_per_row * tex_h)

        tiles_x = tex_w // tile_w
        tiles_y = tex_h // tile_h

        offset = 0

        for ty in range(tiles_y):
            for tx in range(tiles_x):
                x0 = tx * tile_w
                y0 = ty * tile_h

                # each tile row is always 16 bytes
                for row in range(tile_h):
                    y = y0 + row
                    dst = y * bytes_per_row + (x0 * 16) // tile_w

                    if decode:
                        output[dst : dst + 16] = self.raster[offset : offset + 16]
                    else:
                        output[offset : offset + 16] = self.raster[dst : dst + 16]
                    offset += 16

        self.raster = output

    def _decode_index4(self) -> bytes:
        # build 256-entry LUT
        pal = [self.palette[i : i + 4] for i in range(0, len(self.palette), 4)]
        buf = self.raster
        lut: list[bytes] = [None] * 256  # type: ignore

        for b in range(256):
            lo = b & 0xF
            hi = b >> 4
            lut[b] = pal[lo] + pal[hi]

        out = bytearray(len(buf) * 8)

        o = 0
        for b in buf:
            out[o : o + 8] = lut[b]
            o += 8

        return out

    def _decode_index8(self) -> bytes:
        pal = [self.palette[i : i + 4] for i in range(0, len(self.palette), 4)]
        buf = self.raster
        out = bytearray(len(buf) * 4)

        for i, idx in enumerate(buf):
            o = i * 4
            out[o : o + 4] = pal[idx]

        return out

    def _decode_rgba5551(self) -> bytes:
        buf = self.raster
        out = bytearray(len(buf) * 2)

        for i in range(0, len(buf), 2):
            val = buf[i] | (buf[i + 1] << 8)

            r = (val >> 0) & 0b11111
            g = (val >> 5) & 0b11111
            b = (val >> 10) & 0b11111

            r = (r << 3) | (r >> 2)
            g = (g << 3) | (g >> 2)
            b = (b << 3) | (b >> 2)
            a = 0xFF if ((val >> 15) & 1) != 0 else 0

            o = (i // 2) * 4
            out[o : o + 4] = (r, g, b, a)

        return out

    def _decode_rgba4444(self) -> bytes:
        buf = self.raster
        out = bytearray(len(buf) * 2)

        for i in range(0, len(buf), 2):
            val = buf[i] | (buf[i + 1] << 8)

            r = (val >> 0) & 0b1111
            g = (val >> 4) & 0b1111
            b = (val >> 8) & 0b1111
            a = (val >> 12) & 0b1111

            r = (r << 4) | r
            g = (g << 4) | g
            b = (b << 4) | b
            a = (a << 4) | a

            o = (i // 2) * 4
            out[o : o + 4] = (r, g, b, a)

        return out

    def _decode(self) -> bytes:
        rgba = b""
        if self.tex_psm == PSM.INDEXED_8:
            rgba = self._decode_index8()
        elif self.tex_psm == PSM.INDEXED_4:
            rgba = self._decode_index4()
        elif self.tex_psm == PSM.RGBA_4444:
            rgba = self._decode_rgba4444()
        elif self.tex_psm == PSM.RGBA_5551:
            rgba = self._decode_rgba5551()
        elif self.tex_psm == PSM.RGBA_8888:
            rgba = self.raster

        return rgba

    def save_png(self, path: Path) -> None:
        rgba = self._decode()
        size = (self.tex_size.width, self.tex_size.height)
        img = Image.frombytes("RGBA", size, bytes(rgba))

        # crop to original size
        img = img.crop((0, 0, self.img_size.width, self.img_size.height))

        # Keep this in case we ever want to make BIDs from nothing
        # img.save(path.with_suffix(f".{self.tex_psm.name}.png"))
        img.save(path.with_suffix(".png"))

    def _encode_index4(self, img: Image.Image) -> tuple[bytes, bytes]:
        img = imagequant.quantize_pil_image(
            img,
            dithering_level=0.25,
            max_colors=16,
            min_quality=0,
            max_quality=100,
        )

        raster8 = img.tobytes()

        raster = bytearray(len(raster8) // 2)

        for j, i in enumerate(range(0, len(raster8), 2)):
            lo = raster8[i] & 0xF
            hi = raster8[i + 1] & 0xF
            raster[j] = lo | (hi << 4)

        pal = img.getpalette("RGBA")

        assert pal is not None

        palette = bytes(pal)
        palette += b"\x00" * ((16 * 4) - (self.pal_cnt * 32))

        return raster, palette

    def _encode_index8(self, img: Image.Image) -> tuple[bytes, bytes]:
        img = imagequant.quantize_pil_image(
            img,
            dithering_level=0.25,
            max_colors=256,
            min_quality=0,
            max_quality=100,
        )

        raster = img.tobytes()
        pal = img.getpalette("RGBA")

        assert pal is not None

        palette = bytes(pal)
        palette += b"\x00" * ((256 * 4) - (self.pal_cnt * 32))

        return raster, palette

    def _encode_rgba5551(self, rgba: bytes) -> bytes:
        out = bytearray(len(rgba) // 2)

        j = 0
        for i in range(0, len(rgba), 4):
            r, g, b, a = rgba[i : i + 4]

            r5 = r >> 3
            g5 = g >> 3
            b5 = b >> 3
            a1 = 1 if a >= 128 else 0

            val = (a1 << 15) | (b5 << 10) | (g5 << 5) | (r5 << 0)

            out[j + 0] = val & 0xFF
            out[j + 1] = val >> 8
            j += 2

        return out

    def _encode_rgba4444(self, rgba: bytes) -> bytes:
        out = bytearray(len(rgba) // 2)

        j = 0
        for i in range(0, len(rgba), 4):
            r, g, b, a = rgba[i : i + 4]

            r4 = r >> 4
            g4 = g >> 4
            b4 = b >> 4
            a4 = a >> 4

            val = (a4 << 12) | (b4 << 8) | (g4 << 4) | r4

            out[j] = val & 0xFF
            out[j + 1] = val >> 8
            j += 2

        return out

    def update(self, path: Path, reuse_palette: bool = False) -> None:
        img = Image.open(path).convert("RGBA")

        img_width, img_height = img.size

        gpu_width = _next_pow2(img_width)
        gpu_height = _next_pow2(img_height)

        tex_width = (img_width + 0xF) & ~0xF
        tex_height = (img_height + 0x7) & ~0x7

        self.img_size = Size(img_width, img_height)
        self.tex_size = Size(tex_width, tex_height)
        self.gpu_size = Size(gpu_width, gpu_height)

        img = ImageOps.expand(
            img, (0, 0, tex_width - img_width, tex_height - img_height)
        )

        rgba = img.tobytes()

        if self.tex_psm == PSM.RGBA_5551:
            self.raster = self._encode_rgba5551(rgba)
        elif self.tex_psm == PSM.RGBA_4444:
            self.raster = self._encode_rgba4444(rgba)
        elif self.tex_psm == PSM.RGBA_8888:
            self.raster = rgba
        elif self.tex_psm == PSM.INDEXED_4:
            self.raster, self.palette = self._encode_index4(img)
        elif self.tex_psm == PSM.INDEXED_8:
            self.raster, self.palette = self._encode_index8(img)

    def save_ppt(self, path: Path, tiled: bool = False) -> None:
        if tiled:
            self._tiler(False)

        path.write_bytes(self.get_bytes())

    def get_bytes(self) -> bytes:
        dummy = b""
        with FileIO(dummy, "wb") as ppt:
            ppt.write(PPT_MAGIC)
            ppt.write_uint16(self.gpu_size.width)
            ppt.write_uint16(self.gpu_size.height)
            ppt.write_uint16(self.tex_psm)
            ppt.write_uint16(self.texbuf_mode)
            ppt.write_uint16(self.tex_size.width)
            ppt.write_uint16(self.tex_size.height)
            ppt.write_uint16(self.img_size.width)
            ppt.write_uint16(self.img_size.height)

            ppt.write_uint32(0)
            ppt.write_uint32(0)  # Wite pointer at the end
            ppt.write_uint32(0)

            self._tiler(False)
            ppt.write(self.raster)

            if self.palette:
                ppt.write_uint32(ppt.tell(), 0x18)
                ppt.write(PPC_MAGIC)
                ppt.write_uint16(self.pal_psm)
                ppt.write_uint16(self.pal_cnt)
                ppt.write_uint32(0)
                ppt.write_uint32(0)
                ppt.write(self.palette)
            
            return bytes(ppt.get_buffer())

    def print_info(self) -> None:
        print(f"PSM {self.tex_psm.name}")
        print(f"GPU {self.gpu_size.width}x{self.gpu_size.height}")
        print(f"IMG {self.img_size.width}x{self.img_size.height}")
        print(f"TEX {self.tex_size.width}x{self.tex_size.height}")

    def _read_palette(self, f: FileIO) -> None:
        if self.pal_ptr == 0:
            return

        assert f.read(4) == PPC_MAGIC, "Wrong MAGIC for PPC chunk!"

        pal_psm = f.read_uint16()
        self.pal_cnt = f.read_uint16()
        self._reserved0 = f.read_uint32()
        self._reserved1 = f.read_uint32()

        assert pal_psm == PSM.RGBA_8888, f"Invalid palette Storage Mode {pal_psm}!"

        # assert reserved0 == 0 and reserved1 == 0, "PPC reserved fields are not 0!"

        # Read palette data (32 bytes x N colors)
        self.palette = f.read(self.pal_cnt * 32)

        pal_size = 256 if self.tex_psm == PSM.INDEXED_8 else 16
        self.palette += b"\x00" * ((pal_size * 4) - (self.pal_cnt * 32))

    def _read_raster(self, f: FileIO) -> None:
        size = self.tex_size.width * self.tex_size.height

        if self.tex_psm in (PSM.RGBA_5551, PSM.RGBA_4444):
            self.raster = f.read(size * 2)
        elif self.tex_psm == PSM.RGBA_8888:
            self.raster = f.read(size * 4)
        elif self.tex_psm == PSM.INDEXED_4:
            self.raster = f.read(size // 2)
        elif self.tex_psm == PSM.INDEXED_8:
            self.raster = f.read(size)
