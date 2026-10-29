"""Generate the MSIX tile/logo images from the PWA icon.

Usage: python make_assets.py <icon-512.png> <out_dir>
"""

import sys
from pathlib import Path

from PIL import Image

BACKGROUND = (43, 29, 23, 255)  # #2B1D17, the app's theme colour

# name -> (width, height, icon scale relative to the shorter side, filled background)
ASSETS = {
    "StoreLogo.png": (50, 50, 1.0, False),
    "Square44x44Logo.png": (44, 44, 1.0, False),
    "Square44x44Logo.targetsize-44_altform-unplated.png": (44, 44, 1.0, False),
    "Square150x150Logo.png": (150, 150, 0.66, True),
    "Wide310x150Logo.png": (310, 150, 0.66, True),
    "SplashScreen.png": (620, 300, 0.6, False),
}


def main(src: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    icon = Image.open(src).convert("RGBA")
    for name, (w, h, scale, filled) in ASSETS.items():
        canvas = Image.new("RGBA", (w, h), BACKGROUND if filled else (0, 0, 0, 0))
        side = round(min(w, h) * scale)
        sized = icon.resize((side, side), Image.LANCZOS)
        canvas.alpha_composite(sized, ((w - side) // 2, (h - side) // 2))
        canvas.save(out / name)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
