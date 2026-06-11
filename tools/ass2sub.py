#!/usr/bin/env python3
# ass2sub.py - convert an Aegisub .ass file into the compact .sub binary
#
# PlayResX/Y is 480x272 (== the movie framebuffer), so ASS coordinates map 1:1 to the screen.
#
# Output binary (little-endian):
#   u32 count
#   count x { i32 start, i32 end, i32 penY, u32 textOff, u32 textLen }  (20 B)
#   text blob: raw EUC-JP bytes; 0x0A separates wrapped lines (\N in ASS)
# penY = top-of-text Y in screen pixels. textOff is from start of file.
#
# Usage:  python ass2sub.py "trial_toir.ass" trial_toir.sub [fps] [lineHeight]

import sys
import re
import struct

DEF_FPS = 60.0      # EBOOT clock is the display vcount (~60 Hz)
DEF_H = 15          # approx on-screen line height at the current 0.75x font


def parse_time(t):
    # H:MM:SS.cc  (centiseconds)
    h, m, rest = t.split(":")
    s, cs = rest.split(".")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100.0


def read_text(path):
    data = open(path, "rb").read()
    for enc in ("utf-8-sig", "euc-jp", "cp932", "utf-8"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def main():
    if len(sys.argv) < 3:
        print("usage: ass2sub.py <in.ass> <out.sub> [fps] [lineHeight]")
        return 1
    in_path, out_path = sys.argv[1], sys.argv[2]
    fps = float(sys.argv[3]) if len(sys.argv) > 3 else DEF_FPS
    line_h = int(sys.argv[4]) if len(sys.argv) > 4 else DEF_H

    play_res_y = 272
    in_events = False
    fmt = None
    cues = []

    for ln in read_text(in_path).splitlines():
        low = ln.strip()
        if low.startswith("PlayResY:"):
            play_res_y = int(low.split(":", 1)[1].strip())
        elif low == "[Events]":
            in_events = True
        elif low.startswith("[") and low != "[Events]":
            in_events = False
        elif in_events and low.startswith("Format:"):
            fmt = [f.strip() for f in low.split(":", 1)[1].split(",")]
        elif in_events and low.startswith("Dialogue:"):
            body = ln.split(":", 1)[1]
            parts = body.split(",", len(fmt) - 1)
            d = dict(zip(fmt, parts))
            start = parse_time(d["Start"].strip())
            end = parse_time(d["End"].strip())
            try:
                margin_v = int((d.get("MarginV", "0").strip() or "0"))
            except ValueError:
                margin_v = 0
            text = d.get("Text", "")

            # \pos(x,y) Y override
            mpos = re.search(r"\\pos\(\s*[-\d.]+\s*,\s*([-\d.]+)\s*\)", text)
            pen_y = None
            if mpos:
                pen_y = int(round(float(mpos.group(1))))
            # onvert \N / \n -> 0x0A newline
            text = re.sub(r"\{[^}]*\}", "", text)
            text = text.replace("\\N", "\n").replace("\\n", "\n")
            if pen_y is None:
                pen_y = play_res_y - margin_v - line_h
                if pen_y < 0:
                    pen_y = 0

            euc = bytearray()
            for ch in text:
                euc += b"\x0a" if ch == "\n" else ch.encode("euc-jp", "replace")

            if euc:
                cues.append((int(round(start * fps)), int(round(end * fps)),
                             pen_y, bytes(euc)))

    count = len(cues)
    ent_size = 20
    text_base = 4 + count * ent_size
    ents = bytearray()
    blob = bytearray()
    off = text_base
    for (s, e, y, t) in cues:
        ents += struct.pack("<iiiII", s, e, y, off, len(t))
        blob += t
        off += len(t)

    out = struct.pack("<I", count) + bytes(ents) + bytes(blob)
    open(out_path, "wb").write(out)
    print("wrote %s: %d cues (fps=%g, lineH=%d, PlayResY=%d)"
          % (out_path, count, fps, line_h, play_res_y))
    for (s, e, y, t) in cues:
        print("  f%d..f%d  Y=%d  %dB" % (s, e, y, len(t)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
