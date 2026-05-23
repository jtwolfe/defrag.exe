"""
Generate icon.png / icon.ico / icon.icns from a single procedural design.

Run from the repo root:
    python tools/make_icons.py

Outputs:
    assets/icon.png        — 1024x1024 master
    assets/icon.ico        — Windows multi-res (16,32,48,64,128,256)
    assets/icon.icns       — macOS multi-res (16,32,64,128,256,512,1024)

Design: a Win9x-styled bevel containing a tiny defrag grid — the same VGA-16
palette the game uses (navy / cyan / yellow / green / magenta / red).
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw

# Win9x / VGA-16 palette
BEVEL_LIGHT = (255, 255, 255)
BEVEL_DARK  = (128, 128, 128)
BG          = (192, 192, 192)   # classic Win9x grey
NAVY        = (0, 0, 128)
CELL_COLORS = [
    (  0, 255,   0),  # good (green)
    (255, 255,   0),  # moving (yellow)
    (255,   0,   0),  # frag (red)
    (255,   0, 255),  # system (magenta)
    (  0, 255, 255),  # data (cyan)
]

# 4x4 cell map (legible down to 16px). Digits index into CELL_COLORS.
GRID_SMALL = [
    "0011",
    "0122",
    "1223",
    "0234",
]

# 8x8 detailed grid for larger sizes.
GRID_LARGE = [
    "00000011",
    "00012211",
    "00112221",
    "00112321",
    "01112322",
    "01122332",
    "00122334",
    "00012234",
]

def draw_master(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG)
    d = ImageDraw.Draw(img)

    # Outer bevel — light on top-left, dark on bottom-right (raised-button look)
    b = max(1, size // 32)
    d.rectangle([0, 0, size - 1, b - 1], fill=BEVEL_LIGHT)               # top
    d.rectangle([0, 0, b - 1, size - 1], fill=BEVEL_LIGHT)               # left
    d.rectangle([0, size - b, size - 1, size - 1], fill=BEVEL_DARK)      # bottom
    d.rectangle([size - b, 0, size - 1, size - 1], fill=BEVEL_DARK)      # right

    # Inner navy panel
    pad = max(2, size // 10)
    panel = [pad, pad, size - pad - 1, size - pad - 1]
    d.rectangle(panel, fill=NAVY)

    # Grid of cells. Use the small 4x4 layout for tiny icons.
    grid = GRID_SMALL if size < 64 else GRID_LARGE
    rows = len(grid)
    cols = len(grid[0])
    inner_w = panel[2] - panel[0] - 1
    inner_h = panel[3] - panel[1] - 1
    gap = max(1, size // 128)
    cell_w = max(1, (inner_w - gap * (cols + 1)) // cols)
    cell_h = max(1, (inner_h - gap * (rows + 1)) // rows)
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch == '.':
                continue
            color = CELL_COLORS[int(ch) % len(CELL_COLORS)]
            x = panel[0] + gap + c * (cell_w + gap)
            y = panel[1] + gap + r * (cell_h + gap)
            d.rectangle([x, y, x + cell_w - 1, y + cell_h - 1], fill=color)
    return img


def main():
    assets = Path(__file__).parent.parent / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    # 1024 master, then downscale per format
    master = draw_master(1024)
    master.save(assets / "icon.png")

    # PIL's ICO/ICNS savers don't honor append_images — they resample the
    # source image to each requested size. Render a crisp 256 master for ICO
    # and the 1024 master for ICNS, then let PIL downsample.
    sizes_ico  = [16, 32, 48, 64, 128, 256]
    sizes_icns = [16, 32, 64, 128, 256, 512, 1024]

    ico_master = draw_master(256)
    ico_master.save(
        assets / "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes_ico],
    )

    master.save(
        assets / "icon.icns",
        format="ICNS",
        sizes=[(s, s) for s in sizes_icns],
    )

    print(f"Wrote {assets/'icon.png'}")
    print(f"Wrote {assets/'icon.ico'}")
    print(f"Wrote {assets/'icon.icns'}")


if __name__ == "__main__":
    main()
