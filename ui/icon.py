"""
ui/icon.py — Programmatic menu-bar icon generator.

Draws a database cylinder (MySQL / Amazon RDS style) as a pure-Python PNG
using only built-in modules (struct + zlib).  No Pillow required.

States
------
idle   → blue cylinder   (MySQL palette — no forwarding active)
active → green cylinder + white right-arrow overlay (forwarding is live)
"""
import os
import struct
import zlib
import tempfile

# ---------------------------------------------------------------------------
# Arrow pixel-art coordinates (22×22 reference grid)
# Shaft: 2-pixel-thick horizontal bar.  Head: triangular, pointing right.
# ---------------------------------------------------------------------------
_ARROW_PTS_22 = [
    # shaft
    (7, 14), (8, 14), (9, 14), (10, 14), (11, 14), (12, 14), (13, 14),
    (7, 15), (8, 15), (9, 15), (10, 15), (11, 15), (12, 15), (13, 15),
    # arrowhead triangle (tip at x=17, symmetric around y=14.5)
    (13, 12), (13, 13), (13, 16), (13, 17),
    (14, 12), (14, 13), (14, 14), (14, 15), (14, 16), (14, 17),
    (15, 13), (15, 14), (15, 15), (15, 16),
    (16, 14), (16, 15),
    (17, 14), (17, 15),
]


def make_status_icon(state: str = 'idle', size: int = 22) -> str:
    """Generate a database-cylinder PNG and return the file path.

    Parameters
    ----------
    state : 'idle' | 'active'
    size  : square pixel size (22 for standard; 44 for Retina)
    """
    s = size / 22.0  # linear scale factor

    if state == 'active':
        body_rgb   = (0x2E, 0x7D, 0x32)  # Material Green 800
        top_rgb    = (0x66, 0xBB, 0x6A)  # Material Green 400 (top-cap highlight)
        stripe_rgb = (0x1B, 0x5E, 0x20)  # Material Green 900 (stripe lines)
    else:
        body_rgb   = (0x15, 0x65, 0xC0)  # Material Blue 800 (MySQL-like)
        top_rgb    = (0x42, 0xA5, 0xF5)  # Material Blue 400 (top-cap highlight)
        stripe_rgb = (0x0D, 0x47, 0xA1)  # Material Blue 900 (stripe lines)

    # Cylinder geometry (22-unit space, scaled by s)
    cx    = 11.0 * s
    rx    = 8.5  * s   # horizontal radius
    ry    = 2.8  * s   # ellipse vertical half-height
    top_y = 5.5  * s   # centre y of top ellipse
    bot_y = 16.5 * s   # centre y of bottom ellipse
    left  = cx - rx
    right = cx + rx

    # Transparent RGBA pixel buffer
    pixels = [[(0, 0, 0, 0)] * size for _ in range(size)]

    def _ellipse_alpha(px, py, ecx, ecy, erx, ery):
        """4× sub-pixel coverage → smooth anti-aliased alpha (0–255)."""
        hits = sum(
            ((px + ox - ecx) / erx) ** 2 + ((py + oy - ecy) / ery) ** 2 <= 1.0
            for ox in (0.25, 0.75) for oy in (0.25, 0.75)
        )
        return min(255, hits * 64)

    # Cylinder body + top/bottom caps
    for y in range(size):
        for x in range(size):
            in_body = left <= x + 0.5 <= right and top_y <= y + 0.5 <= bot_y
            a_top   = _ellipse_alpha(x, y, cx, top_y, rx, ry)
            a_bot   = _ellipse_alpha(x, y, cx, bot_y, rx, ry)
            if in_body:
                pixels[y][x] = (*body_rgb, 255)
            elif a_top:
                pixels[y][x] = (*top_rgb, min(255, a_top))
            elif a_bot:
                pixels[y][x] = (*body_rgb, min(255, a_bot))

    # Two horizontal stripe lines (data-layer separators)
    for frac in (1 / 3, 2 / 3):
        sy = int(top_y + frac * (bot_y - top_y))
        if 0 <= sy < size:
            for x in range(max(0, int(left)), min(size, int(right) + 1)):
                if pixels[sy][x][3] > 0:
                    pixels[sy][x] = (*stripe_rgb, pixels[sy][x][3])

    # Active state: overlay white right-pointing arrow
    if state == 'active':
        arrow_color = (255, 255, 255, 220)
        for nx, ny in _ARROW_PTS_22:
            ax, ay = round(nx * s), round(ny * s)
            if 0 <= ax < size and 0 <= ay < size:
                pixels[ay][ax] = arrow_color

    # Serialize pixels to a valid PNG byte stream
    raw = b''.join(
        bytes([0]) + bytes(ch for pixel in row for ch in pixel)
        for row in pixels
    )
    compressed = zlib.compress(raw, 9)

    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', crc)

    ihdr = struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)
    png = (
        b'\x89PNG\r\n\x1a\n'
        + _chunk(b'IHDR', ihdr)
        + _chunk(b'IDAT', compressed)
        + _chunk(b'IEND', b'')
    )

    path = os.path.join(tempfile.gettempdir(), f'ssmtunnel_icon_{state}_{size}.png')
    with open(path, 'wb') as fh:
        fh.write(png)
    return path
