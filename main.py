#!/usr/bin/env python3
"""Make the coolest art - coolest-art-01.

Concept: "The Last Whale of the Sky"
A colossal whale glides through a starlit dusk sky, lit by a huge
blood-orange moon. A tiny lantern-bearer stands on its back.
One glance, one idea: scale, wonder, and a single warm light in the dark.

Pure Python 3.13 standard library only. No network. Deterministic:
same bytes on every run. Writes /output/entry.png (or $MAKEFUN_OUTPUT_DIR).
1024x1024, PNG, under 1 MiB.
"""
import math
import os
import random
import struct
import zlib

W = 1024
H = 1024


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(v, lo=0, hi=255):
    return lo if v < lo else hi if v > hi else v


def main():
    # Pixel buffer: bytearray of RGB, row-major.
    buf = bytearray(W * H * 3)

    def set_px(x, y, r, g, b):
        i = (y * W + x) * 3
        buf[i] = r
        buf[i + 1] = g
        buf[i + 2] = b

    def get_px(x, y):
        i = (y * W + x) * 3
        return buf[i], buf[i + 1], buf[i + 2]

    def blend_px(x, y, r, g, b, a):
        # a in 0..1, blend over existing
        if a <= 0:
            return
        if a >= 1:
            set_px(x, y, int(r), int(g), int(b))
            return
        i = (y * W + x) * 3
        buf[i] = int(buf[i] * (1 - a) + r * a)
        buf[i + 1] = int(buf[i + 1] * (1 - a) + g * a)
        buf[i + 2] = int(buf[i + 2] * (1 - a) + b * a)

    # --- 1. Sky gradient: deep indigo top -> violet -> warm dusk horizon ---
    # Horizon stays dark; the orange is a thin band, not a third of the frame.
    stops = [
        (0.00, (7, 11, 36)),
        (0.45, (27, 20, 69)),
        (0.70, (62, 30, 76)),
        (0.85, (110, 42, 62)),
        (0.94, (168, 61, 46)),
        (1.00, (210, 92, 52)),
    ]
    for y in range(H):
        t = y / (H - 1)
        # find segment
        for k in range(len(stops) - 1):
            t0, c0 = stops[k]
            t1, c1 = stops[k + 1]
            if t0 <= t <= t1:
                f = 0 if t1 == t0 else (t - t0) / (t1 - t0)
                # smoothstep for softer bands
                f = f * f * (3 - 2 * f)
                r = int(lerp(c0[0], c1[0], f))
                g = int(lerp(c0[1], c1[1], f))
                b = int(lerp(c0[2], c1[2], f))
                break
        else:
            r, g, b = stops[-1][1]
        row = bytes((r, g, b)) * W
        buf[y * W * 3:(y + 1) * W * 3] = row

    rng = random.Random(20261113)

    # --- 2. Stars: deterministic, denser at top, avoid moon disc ---
    moon_cx, moon_cy, moon_r = 712, 268, 168
    for _ in range(420):
        x = rng.randint(0, W - 1)
        y = rng.randint(0, int(H * 0.72))
        # skip inside moon
        if (x - moon_cx) ** 2 + (y - moon_cy) ** 2 < (moon_r + 18) ** 2:
            continue
        mag = rng.random()
        if mag < 0.55:
            v = 180
            s = 1
        elif mag < 0.88:
            v = 230
            s = 1
        else:
            v = 255
            s = 2
        # twinkle variation by position, deterministic
        tw = 0.75 + 0.25 * math.sin(x * 0.37 + y * 0.11)
        v = int(v * tw)
        for dy in range(s):
            for dx in range(s):
                xx, yy = x + dx, y + dy
                if 0 <= xx < W and 0 <= yy < H:
                    blend_px(xx, yy, v, v, int(v * 0.95), 0.9)

    # --- 3. Moon: huge, warm, with glow halo and soft craters ---
    # Glow halo: radial falloff outside disc
    halo_r = 285
    for y in range(max(0, moon_cy - halo_r), min(H, moon_cy + halo_r + 1)):
        for x in range(max(0, moon_cx - halo_r), min(W, moon_cx + halo_r + 1)):
            dx = x - moon_cx
            dy = y - moon_cy
            d = math.sqrt(dx * dx + dy * dy)
            if d > moon_r and d < halo_r:
                a = 0.38 * (1 - (d - moon_r) / (halo_r - moon_r)) ** 2
                blend_px(x, y, 255, 190, 120, a)
    # Disc
    for y in range(max(0, moon_cy - moon_r), min(H, moon_cy + moon_r + 1)):
        for x in range(max(0, moon_cx - moon_r), min(W, moon_cx + moon_r + 1)):
            dx = x - moon_cx
            dy = y - moon_cy
            d2 = dx * dx + dy * dy
            if d2 <= moon_r * moon_r:
                d = math.sqrt(d2)
                # limb darkening + warm center
                f = d / moon_r
                base = 255 - int(28 * f)
                r = base
                g = int(232 - 22 * f)
                b = int(184 - 30 * f)
                # craters: few soft darker patches, deterministic positions
                for (cx, cy, cr, shade) in (
                    (650, 220, 26, 18),
                    (750, 300, 34, 14),
                    (690, 330, 18, 20),
                    (770, 210, 15, 16),
                    (620, 300, 12, 18),
                ):
                    cd = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                    if cd < cr:
                        s = 1 - cd / cr
                        r = int(r - shade * s)
                        g = int(g - shade * s)
                        b = int(b - shade * s)
                # edge anti-alias
                if d > moon_r - 1.5:
                    a = (moon_r - d) / 1.5
                    blend_px(x, y, r, g, b, max(0.0, min(1.0, a)))
                else:
                    set_px(x, y, r, g, b)

    # --- 4. Low clouds / mist bands: soft dark ellipses ---
    clouds = [
        (180, 830, 320, 42, 0.32, (22, 16, 48)),
        (760, 870, 380, 48, 0.30, (28, 18, 52)),
        (500, 910, 460, 55, 0.35, (16, 12, 40)),
        (120, 760, 200, 26, 0.22, (30, 22, 60)),
        (880, 740, 180, 24, 0.20, (30, 22, 60)),
    ]
    for (cx, cy, rx, ry, alpha, col) in clouds:
        for y in range(max(0, cy - ry), min(H, cy + ry + 1)):
            for x in range(max(0, cx - rx), min(W, cx + rx + 1)):
                d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
                if d < 1:
                    a = alpha * (1 - d) * (1 - d)
                    blend_px(x, y, col[0], col[1], col[2], a)

    # --- 5. Whale: one smooth body, drawn as a single profile ---
    # Half-height control points (x, half-height). Interpolated smoothly.
    # Body is lighter navy than the sky so it reads as a shape, not a hole.
    def half_h(x):
        pts = [(140, 26), (260, 78), (420, 112), (560, 118), (720, 108), (860, 88), (940, 34), (965, 8)]
        for i in range(len(pts) - 1):
            x0, h0 = pts[i]
            x1, h1 = pts[i + 1]
            if x0 <= x <= x1:
                f = (x - x0) / (x1 - x0)
                f = f * f * (3 - 2 * f)
                return lerp(h0, h1, f)
        return pts[-1][1]

    def center_y(x):
        # back arches gently up in the middle
        return 545 - 28 * math.sin((x - 140) / 825 * math.pi)

    def fill_triangle(p0, p1, p2, col):
        minx = max(0, int(min(p0[0], p1[0], p2[0])) - 1)
        maxx = min(W - 1, int(max(p0[0], p1[0], p2[0])) + 1)
        miny = max(0, int(min(p0[1], p1[1], p2[1])) - 1)
        maxy = min(H - 1, int(max(p0[1], p1[1], p2[1])) + 1)

        def sign(ax, ay, bx, by, cx, cy):
            return (ax - cx) * (by - cy) - (bx - cx) * (ay - cy)

        for y in range(miny, maxy + 1):
            for x in range(minx, maxx + 1):
                d1 = sign(x, y, p0[0], p0[1], p1[0], p1[1])
                d2 = sign(x, y, p1[0], p1[1], p2[0], p2[1])
                d3 = sign(x, y, p2[0], p2[1], p0[0], p0[1])
                neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
                pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
                if not (neg and pos):
                    set_px(x, y, col[0], col[1], col[2])

    # Tail flukes first (behind body): big, swept, whale-like
    fill_triangle((150, 538), (36, 438), (96, 548), (38, 48, 82))
    fill_triangle((150, 552), (40, 648), (98, 556), (38, 48, 82))
    # Pectoral fin
    fill_triangle((580, 632), (512, 724), (640, 640), (30, 40, 70))

    # Body: scanline fill, uniform colour by vertical position
    for x in range(140, 966):
        h = half_h(x)
        cy = center_y(x)
        top = int(cy - h)
        bot = int(cy + h)
        for y in range(max(0, top), min(H, bot + 1)):
            f = (y - top) / max(1, bot - top)  # 0 top, 1 bottom
            r = int(lerp(44, 26, f))
            g = int(lerp(56, 36, f))
            b = int(lerp(96, 62, f))
            # warm rim light on the top 10 px
            if y - top < 10:
                glow = 1 - (y - top) / 10
                r = int(lerp(r, 255, glow * 0.65))
                g = int(lerp(g, 196, glow * 0.65))
                b = int(lerp(b, 130, glow * 0.65))
            set_px(x, y, r, g, b)

    # Mouth line: subtle darker curve near the head
    for t in range(0, 90):
        x = 860 + t
        y = int(578 + 0.12 * t - 0.002 * t * t)
        for dy in range(0, 2):
            if 0 <= x < W and 0 <= y + dy < H:
                blend_px(x, y + dy, 16, 20, 38, 0.7)

    # Whale eye: clear, warm, with highlight
    ex, ey = 872, 522
    for y in range(ey - 10, ey + 11):
        for x in range(ex - 10, ex + 11):
            d = math.sqrt((x - ex) ** 2 + (y - ey) ** 2)
            if d < 10:
                a = 1 - d / 10
                blend_px(x, y, 255, 200, 120, a)
    set_px(ex + 2, ey - 2, 255, 255, 255)
    set_px(ex + 3, ey - 2, 255, 255, 255)

    # Blowhole spout: a spray of glowing droplets arcing up from the head
    spout_rng = random.Random(99)
    for i in range(70):
        ang = spout_rng.uniform(-0.9, 0.9)
        dist = spout_rng.uniform(18, 110)
        sx = int(810 + math.sin(ang) * dist * 0.7)
        sy = int(458 - math.cos(ang) * dist)
        sz = spout_rng.randint(1, 3)
        alpha = 0.9 * (1 - dist / 130)
        for dy in range(sz):
            for dx in range(sz):
                if 0 <= sx + dx < W and 0 <= sy + dy < H:
                    blend_px(sx + dx, sy + dy, 190, 220, 255, alpha)

    # --- 6. Lantern-bearer: tiny silhouette on the whale's back ---
    # Back top at x=542 is y~400, so feet at 400, shoulders at 376.
    fx, fy = 542, 376
    # body: small vertical line + head dot
    for y in range(fy, fy + 22):
        for x in range(fx - 2, fx + 3):
            set_px(x, y, 8, 10, 22)
    for y in range(fy - 6, fy + 1):
        for x in range(fx - 3, fx + 4):
            if (x - fx) ** 2 + (y - (fy - 3)) ** 2 <= 9:
                set_px(x, y, 8, 10, 22)
    # cloak / coat flare
    fill_triangle((fx - 2, fy + 10), (fx + 2, fy + 10), (fx + 7, fy + 24), (8, 10, 22))
    fill_triangle((fx - 2, fy + 10), (fx + 2, fy + 10), (fx - 7, fy + 24), (8, 10, 22))
    # lantern held out to the right: small warm square + glow
    lx, ly = fx + 14, fy + 8
    # glow halo
    for y in range(ly - 34, ly + 35):
        for x in range(lx - 34, lx + 35):
            if 0 <= x < W and 0 <= y < H:
                d = math.sqrt((x - lx) ** 2 + (y - ly) ** 2)
                if d < 34:
                    a = 0.55 * (1 - d / 34) ** 2
                    blend_px(x, y, 255, 170, 80, a)
    for y in range(ly - 4, ly + 5):
        for x in range(lx - 3, lx + 4):
            set_px(x, y, 255, 214, 130)
    # lantern frame
    for x in range(lx - 4, lx + 5):
        set_px(x, ly - 5, 20, 12, 8)
        set_px(x, ly + 5, 20, 12, 8)

    # --- 7. Birds: small distant silhouettes, upper left ---
    birds = [(180, 210), (230, 185), (270, 225), (150, 260), (310, 190)]
    for (bx, by) in birds:
        # two short strokes forming a V
        for t in range(0, 10):
            x1 = bx - t
            y1 = by - int(t * 0.45)
            x2 = bx + t
            y2 = by - int(t * 0.45)
            if 0 <= x1 < W and 0 <= y1 < H:
                set_px(x1, y1, 12, 14, 30)
            if 0 <= x2 < W and 0 <= y2 < H:
                set_px(x2, y2, 12, 14, 30)

    # --- 8. Bottom mist: soft warm haze above the horizon ---
    for y in range(920, H):
        f = (y - 920) / (H - 920)
        a = 0.18 * f
        for x in range(0, W, 2):
            # subtle horizontal streaks, deterministic
            streak = 0.5 + 0.5 * math.sin(x * 0.02 + y * 0.3)
            blend_px(x, y, 255, 130, 70, a * (0.6 + 0.4 * streak))
            blend_px(x + 1, y, 255, 130, 70, a * (0.6 + 0.4 * streak))

    # --- PNG encode: RGB, filter None, zlib level 9 ---
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter type 0
        raw.extend(buf[y * W * 3:(y + 1) * W * 3])
    comp = zlib.compress(bytes(raw), 9)

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        c += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return c

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "entry.png")
    with open(out_path, "wb") as f:
        f.write(png)


if __name__ == "__main__":
    main()
