#!/usr/bin/env python3
"""THE WORLD IN ONE PAGE — Thursday, 26 November 2026.

A deterministic program (pure Python standard library, no network, no
randomness, no timestamps) that draws a broadsheet front page summing up
the world news of Thursday 26 November 2026 and writes it as a 1024x1024
PNG to $MAKEFUN_OUTPUT_DIR/entry.png (default /output/entry.png).

Everything in this file was written from scratch for the
news-image-20261126 bounty: the font, the PNG encoder, the layout and
the text are all original work.

Run:  mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import os
import struct
import zlib

W, H = 1024, 1024

PAPER = (247, 243, 232)   # warm newsprint
INK = (18, 18, 18)        # near-black ink
RED = (168, 32, 24)       # masthead accent red
GREY = (96, 92, 84)       # secondary text
WHITE = (255, 255, 255)

# ---------------------------------------------------------------- PNG --

def _chunk(kind, data):
    c = struct.pack(">I", len(data)) + kind + data
    return c + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_png(path, pixels, w, h):
    """pixels: bytearray of RGB triples, row-major, w*h*3 bytes."""
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)  # filter: none
        raw += pixels[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", comp)
    png += _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)

# ------------------------------------------------------------ canvas ---


class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)
        self.fill(bg)

    def fill(self, color):
        r, g, b = color
        for i in range(0, len(self.px), 3):
            self.px[i] = r
            self.px[i + 1] = g
            self.px[i + 2] = b

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = color

    def fill_rect(self, x, y, w, h, color):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        for yy in range(y0, y1):
            base = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                i = base + (xx - x0) * 3
                self.px[i], self.px[i + 1], self.px[i + 2] = color

    def rect(self, x, y, w, h, color, t=1):
        self.fill_rect(x, y, w, t, color)
        self.fill_rect(x, y + h - t, w, t, color)
        self.fill_rect(x, y, t, h, color)
        self.fill_rect(x + w - t, y, t, h, color)

    def hline(self, x, y, w, color, t=1):
        self.fill_rect(x, y, w, t, color)

    def vline(self, x, y, h, color, t=1):
        self.fill_rect(x, y, t, h, color)

    def line(self, x0, y0, x1, y1, color, t=1):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        x, y = x0, y0
        while True:
            self.fill_rect(x, y, t, t, color)
            if x == x1 and y == y1:
                return
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def circle(self, cx, cy, r, color, t=1):
        x, y, d = 0, r, 3 - 2 * r
        while y >= x:
            for px, py in ((cx + x, cy + y), (cx - x, cy + y), (cx + x, cy - y),
                           (cx - x, cy - y), (cx + y, cy + x), (cx - y, cy + x),
                           (cx + y, cy - x), (cx - y, cy - x)):
                self.fill_rect(px, py, t, t, color)
            x += 1
            if d > 0:
                y -= 1
                d += 4 * (x - y) + 10
            else:
                d += 4 * x + 6

    def fill_circle(self, cx, cy, r, color):
        for yy in range(cy - r, cy + r + 1):
            dx = int((r * r - (yy - cy) ** 2) ** 0.5)
            self.fill_rect(cx - dx, yy, 2 * dx + 1, 1, color)

    def ellipse(self, cx, cy, rx, ry, color, t=1):
        import math
        for deg in range(0, 360, 2):
            a = math.radians(deg)
            self.fill_rect(int(cx + rx * math.cos(a)),
                           int(cy + ry * math.sin(a)), t, t, color)

    def fill_poly(self, pts, color):
        """Scanline fill of a simple polygon given as [(x, y), ...]."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(min(ys), max(ys) + 1):
            nodes = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    nodes.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            nodes.sort()
            for i in range(0, len(nodes) - 1, 2):
                self.fill_rect(int(nodes[i]), y,
                               max(1, int(nodes[i + 1]) - int(nodes[i])), 1,
                               color)


# --------------------------------------------------------- 5x7 font --
# Original hand-drawn 5-wide, 7-tall bitmap glyphs, rows top to bottom.
# Only capitals, digits and common punctuation are needed: the whole
# page is set in capitals, newspaper style.

FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    ";": ("00000", "01100", "01100", "00000", "01100", "00100", "01000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '"': ("01010", "01010", "00000", "00000", "00000", "00000", "00000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "%": ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "*": ("00000", "00100", "10101", "01110", "10101", "00100", "00000"),
    "#": ("01010", "01010", "11111", "01010", "11111", "01010", "01010"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "@": ("01110", "10001", "10111", "10101", "10110", "10000", "01110"),
    "[": ("01110", "01000", "01000", "01000", "01000", "01000", "01110"),
    "]": ("01110", "00010", "00010", "00010", "00010", "00010", "01110"),
    ">": ("10000", "01000", "00100", "00010", "00100", "01000", "10000"),
    "<": ("00001", "00010", "00100", "01000", "00100", "00010", "00001"),
}

GW, GH = 5, 7  # glyph cell


def char_advance(scale):
    return GW * scale + scale  # glyph + one scaled pixel of tracking


def text_w(s, scale):
    return len(s) * char_advance(scale) - scale if s else 0


def draw_glyph(cv, ch, x, y, scale, color, bold=False):
    g = FONT.get(ch)
    if g is None:
        g = FONT[" "]
    for row in range(GH):
        bits = g[row]
        for col in range(GW):
            if bits[col] == "1":
                cv.fill_rect(x + col * scale, y + row * scale,
                             scale, scale, color)
                if bold:
                    cv.fill_rect(x + col * scale + scale, y + row * scale,
                                 scale, scale, color)


def draw_text(cv, s, x, y, scale, color, bold=False, align="left"):
    s = s.upper()
    w = text_w(s, scale)
    if align == "center":
        x -= w // 2
    elif align == "right":
        x -= w
    cx = x
    for ch in s:
        draw_glyph(cv, ch, cx, y, scale, color, bold)
        cx += char_advance(scale)
    return w


def wrap_text(s, scale, max_w):
    """Word-wrap to lines no wider than max_w pixels."""
    lines, cur = [], ""
    for word in s.upper().split(" "):
        trial = word if not cur else cur + " " + word
        if text_w(trial, scale) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped(cv, s, x, y, scale, color, max_w, line_h, max_lines=None,
                 bold=False):
    lines = wrap_text(s, scale, max_w)
    if max_lines is not None:
        lines = lines[:max_lines]
    for i, ln in enumerate(lines):
        draw_text(cv, ln, x, y + i * line_h, scale, color, bold)
    return len(lines)


# ------------------------------------------------------------ icons ---
# Small black-ink pictograms drawn with the same primitives. Each takes
# the top-left corner of a square box and its size.


def icon_globe(cv, x, y, s, color=INK, t=2):
    cx, cy, r = x + s // 2, y + s // 2, s // 2 - 1
    cv.circle(cx, cy, r, color, t)
    cv.ellipse(cx, cy, r // 2, r, color, t)
    cv.hline(cx - r, cy, 2 * r + 1, color, t)
    cv.line(cx - r + 4, cy - r + 6, cx + r - 4, cy + r - 6, color, t)
    cv.line(cx + r - 4, cy - r + 6, cx - r + 4, cy + r - 6, color, t)


def icon_derrick(cv, x, y, s, color=INK, t=2):
    # Oil derrick: two slanted legs, crossbars, a flame on top.
    w = s
    cv.line(x + 6, y + s - 2, x + w // 2 - 4, y + 8, color, t)
    cv.line(x + w - 6, y + s - 2, x + w // 2 + 4, y + 8, color, t)
    for frac in (0.35, 0.55, 0.75):
        yy = int(y + s * frac)
        xl = int(x + 6 + (w // 2 - 10) * (1 - frac))
        xr = int(x + w - 6 - (w // 2 - 10) * (1 - frac))
        cv.hline(xl, yy, xr - xl, color, t)
    cv.line(x + 6, y + s - 2, x + w - 6, y + s - 2, color, t)
    fx, fy = x + w // 2, y + 2
    cv.fill_poly([(fx, fy), (fx + 5, fy + 8), (fx, fy + 6),
                  (fx - 5, fy + 8)], RED)


def icon_bars(cv, x, y, s, color=INK, t=2):
    bw = s // 4
    for i, h in enumerate((0.35, 0.6, 1.0)):
        hh = int(s * h)
        cv.fill_rect(x + i * (bw + 2), y + s - hh, bw, hh, color)
    cv.hline(x, y + s - 1, s, color, t)


def icon_shield(cv, x, y, s, color=INK, t=2):
    pts = [(x + s // 2, y + 1), (x + s - 2, y + s // 4),
           (x + s - 2, y + s // 2), (x + s // 2, y + s - 1),
           (x + 2, y + s // 2), (x + 2, y + s // 4)]
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        cv.line(x0, y0, x1, y1, color, t)
    cv.fill_rect(x + s // 2 - 1, y + s // 3, 2, s // 3, color)


def icon_burst(cv, x, y, s, color=INK, t=2):
    import math
    cx, cy = x + s // 2, y + s // 2
    for k in range(8):
        a = math.radians(k * 45)
        x1 = int(cx + (s // 2 - 2) * math.cos(a))
        y1 = int(cy + (s // 2 - 2) * math.sin(a))
        cv.line(cx, cy, x1, y1, color, t)
    cv.fill_circle(cx, cy, s // 8, color)


def icon_flame(cv, x, y, s, color=INK, t=2):
    cx = x + s // 2
    cv.fill_poly([(cx, y + 2), (cx + s // 3, y + s // 2),
                  (cx + s // 5, y + s - 2), (cx - s // 5, y + s - 2),
                  (cx - s // 3, y + s // 2)], color)
    cv.fill_circle(cx, y + s // 2 + 4, s // 8, RED)


def icon_rocket(cv, x, y, s, color=INK, t=2):
    cx = x + s // 2
    cv.fill_poly([(cx, y + 1), (cx + s // 6, y + s // 3),
                  (cx + s // 6, y + 2 * s // 3), (cx - s // 6, y + 2 * s // 3),
                  (cx - s // 6, y + s // 3)], color)
    cv.fill_poly([(cx - s // 6, y + s // 2), (cx - s // 2, y + s - 2),
                  (cx - s // 6, y + 2 * s // 3)], color)
    cv.fill_poly([(cx + s // 6, y + s // 2), (cx + s // 2, y + s - 2),
                  (cx + s // 6, y + 2 * s // 3)], color)
    cv.fill_circle(cx, y + s // 3 + 2, s // 10, PAPER)
    cv.fill_poly([(cx - 3, y + 2 * s // 3), (cx + 3, y + 2 * s // 3),
                  (cx, y + s - 1)], RED)


def icon_factory(cv, x, y, s, color=INK, t=2):
    cv.fill_rect(x + 2, y + s // 2, s - 4, s // 2 - 2, color)
    cv.fill_rect(x + 3, y + s // 4, 5, s // 4, color)
    cv.fill_rect(x + 12, y + s // 6, 5, s // 3, color)
    for i in range(3):
        wx = x + 6 + i * 10
        cv.fill_rect(wx, y + s // 2 + 5, 6, 6, PAPER)


# ---------------------------------------------------------- content ---
# All stories were checked against reporting dated Thursday 26 November
# 2026 (Qatar Tribune, NDTV, Manila Times, Zot News, SimpleLife, AP
# wires). Wording is kept to what was reported; no invented figures.

MASTHEAD = "THE WORLD IN ONE PAGE"
DATELINE = "THURSDAY, 26 NOVEMBER 2026"

LEAD_HEAD = ["HOUTHIS CLAIM STRIKE ON SAUDI REFINERY",
             "AS BRENT TOPS $94"]
LEAD_DECK = ("Yemen's Houthis say they hit Ras Tanura, the kingdom's "
             "largest refinery, in retaliation for coalition strikes.")
LEAD_BODY = (
    "Yemen's Houthi movement said it had attacked Saudi Arabia's "
    "largest oil refinery at Ras Tanura, in retaliation for coalition "
    "strikes. The claim could not be independently verified. "
    "The Saudi-led coalition said a projectile hit the Red Sea port of "
    "Jazan, causing minor damage. The Houthis warned aircraft away "
    "from Saudi airspace and threatened Red Sea ports if Hodeidah is "
    "attacked. The war now touches both routes for Gulf oil: Hormuz "
    "and the Red Sea.")

MARKETS = ("MARKETS - BRENT TOPS $94 - TAIWAN -1,927 PTS - "
           "FED: MODEST GROWTH")

# (kicker, icon, headline, body)
STORIES = [
    ("TRADE", icon_bars,
     "TRUMP TARIFF WAVE HITS TAIWAN AND ALLIES",
     "US tariffs of up to 15 percent proposed on Taiwan goods; Japan "
     "and China also covered."),
    ("SECURITY", icon_shield,
     "NATO BOOSTS WATCH ON EASTERN FLANK",
     "NATO boosted air watch on its eastern flank; Poland plans a "
     "no-fly zone."),
    ("UKRAINE", icon_burst,
     "KYIV HITS FIVE JETS; SEVEN DIE IN DRONE RAIDS",
     "Kyiv says it hit five Russian jets at Savasleyka; Russian "
     "drones killed seven."),
    ("EGYPT", icon_flame,
     "AT LEAST 30 DEAD IN CAIRO FUEL-TRUCK FIRE",
     "At least 30 died as a fuel truck overturned and caught fire on "
     "a ring road near Cairo."),
    ("SPACE", icon_rocket,
     "FIRST FOREIGN ASTRONAUT SET FOR TIANGONG",
     "Pakistan's Zeeshan Ali will be the first foreign astronaut "
     "on China's Tiangong."),
    ("WORK", icon_factory,
     "GARMENT WORKERS WIN 36% PAY RISE",
     "Bangladesh raised the garment workers' minimum wage by 36 "
     "percent, a win for millions."),
]

# (bold head, body)
BRIEFS = [
    ("EUROSTAR HALTS TRAINS",
     "Paris walkout halts London-Paris trains."),
    ("UN DOUBTS GAZA SACKINGS",
     "UN doubts sacking of nine Gaza aid workers."),
    ("END CUBA FUEL BLOCKADE",
     "WHO urges end to US fuel blockade on Cuba."),
    ("RAMAPHOSA REPORT UNLAWFUL",
     "Ramaphosa impeachment report ruled unlawful."),
    ("15-YEAR-OLD HITS 204",
     "Sooryavanshi, 15, hits record 204 off 53 balls."),
    ("MADRID THRASH PSV 5-1",
     "Stunner and brace as Madrid win 5-1."),
]

FOOTER = ("THE WORLD IN ONE PAGE - THURSDAY, 26 NOVEMBER 2026 - "
          "COMPILED FROM THE DAY'S WIRES")


# ----------------------------------------------------------- layout ---

M = 36            # page margin
CW = W - 2 * M    # content width


def draw_masthead(cv):
    cv.hline(M, 28, CW, INK, 2)
    # globe emblems flanking the title
    icon_globe(cv, M + 6, 46, 52)
    icon_globe(cv, W - M - 58, 46, 52)
    draw_text(cv, MASTHEAD, W // 2, 52, 6, INK, bold=True, align="center")
    cv.hline(M, 108, CW, INK, 3)
    draw_text(cv, DATELINE, W // 2, 120, 2, INK, bold=True, align="center")
    draw_text(cv, "ONE DAY, ONE PAGE", M, 120, 2, GREY)
    draw_text(cv, "NO. 26", W - M, 120, 2, GREY, align="right")
    cv.hline(M, 142, CW, INK, 3)


def draw_lead(cv, y):
    # Headline, three lines, with a derrick illustration on the right.
    hy = y
    for ln in LEAD_HEAD:
        draw_text(cv, ln, M, hy, 4, INK, bold=True)
        hy += 38
    # deck
    dy = hy + 10
    n = draw_wrapped(cv, LEAD_DECK, M, dy, 2, INK, CW, 18)
    # body in three columns
    by0 = dy + n * 18 + 12
    col_w = (CW - 2 * 24) // 3
    lines = wrap_text(LEAD_BODY, 2, col_w)
    per = (len(lines) + 2) // 3
    for c in range(3):
        cx = M + c * (col_w + 24)
        for i, ln in enumerate(lines[c * per:(c + 1) * per]):
            draw_text(cv, ln, cx, by0 + i * 16, 2, INK)
        if c < 2:
            cv.vline(cx + col_w + 12, by0, per * 16, GREY, 1)
    return by0 + per * 16 + 6


def draw_markets(cv, y):
    cv.fill_rect(M, y, CW, 40, INK)
    draw_text(cv, MARKETS, W // 2, y + 13, 2, WHITE, bold=True,
              align="center")
    return y + 40


def draw_story_cell(cv, x, y, w, h, kicker, icon, head, body):
    cv.rect(x, y, w, h, INK, 1)
    ix, iy, isz = x + 10, y + 8, 30
    icon(cv, ix, iy, isz)
    draw_text(cv, kicker, x + 50, y + 16, 2, RED, bold=True)
    cv.hline(x + 10, y + 44, w - 20, GREY, 1)
    n = draw_wrapped(cv, head, x + 10, y + 52, 2, INK, w - 20, 20,
                     max_lines=2, bold=True)
    draw_wrapped(cv, body, x + 10, y + 52 + n * 20 + 6, 2, INK, w - 20,
                 16, max_lines=4)


def draw_grid(cv, y):
    gap = 14
    cell_w = (CW - 2 * gap) // 3
    cell_h = 176
    for r in range(2):
        for c in range(3):
            kicker, icon, head, body = STORIES[r * 3 + c]
            x = M + c * (cell_w + gap)
            draw_story_cell(cv, x, y + r * (cell_h + gap), cell_w, cell_h,
                            kicker, icon, head, body)
    return y + 2 * cell_h + gap


def draw_briefs(cv, y):
    cv.hline(M, y, CW, INK, 3)
    draw_text(cv, "IN BRIEF", M, y + 10, 3, INK, bold=True)
    cv.hline(M, y + 44, CW, INK, 1)
    gap = 20
    col_w = (CW - 2 * gap) // 3
    by = y + 54
    for r in range(2):
        for c in range(3):
            head, body = BRIEFS[r * 3 + c]
            x = M + c * (col_w + gap)
            yy = by + r * 46
            draw_text(cv, head, x, yy, 2, INK, bold=True)
            draw_wrapped(cv, body, x, yy + 18, 2, GREY, col_w, 15,
                         max_lines=2)
    return by + 2 * 46


def draw_footer(cv, y):
    cv.hline(M, y, CW, INK, 2)
    draw_text(cv, FOOTER, W // 2, y + 8, 1, GREY, align="center")


def build():
    cv = Canvas(W, H, PAPER)
    draw_masthead(cv)
    y = draw_lead(cv, 158)
    y = draw_markets(cv, y + 10)
    y = draw_grid(cv, y + 12)
    y = draw_briefs(cv, y + 12)
    draw_footer(cv, y + 8)
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    cv = build()
    size = write_png(path, cv.px, W, H)
    print("wrote %s (%d bytes)" % (path, size))


if __name__ == "__main__":
    main()
