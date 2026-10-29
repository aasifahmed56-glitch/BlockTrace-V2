"""
Generate BlockTrace icons: 16x16, 32x32, 48x48, 128x128 PNGs and 440x280 promo tile.
Colors:
  Background: Dark Brown #2B1D17 (43, 29, 23)
  Accent/Nodes: Orange #E0621A (224, 98, 26)
  Secondary Accent / Highlights: Cream #F7EFE8 (247, 239, 232)
"""
import os
from PIL import Image, ImageDraw

ICON_DIR = os.path.join(os.path.dirname(__file__), "icons")
STORE_DIR = os.path.join(os.path.dirname(__file__), "store")
os.makedirs(ICON_DIR, exist_ok=True)
os.makedirs(STORE_DIR, exist_ok=True)

BG_COLOR = (43, 29, 23)      # #2B1D17
ORANGE = (224, 98, 26)       # #E0621A
CREAM = (247, 239, 232)      # #F7EFE8
ORANGE_LIGHT = (245, 130, 60)

def draw_network_icon(size):
    # Render at 4x for smooth antialiasing, then downsample
    scale = 4
    canvas_size = size * scale
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded rectangle background
    corner_radius = int(canvas_size * 0.22)
    draw.rounded_rectangle(
        [(0, 0), (canvas_size - 1, canvas_size - 1)],
        radius=corner_radius,
        fill=BG_COLOR
    )

    # Center and relative node positions
    cx, cy = canvas_size / 2, canvas_size / 2
    r_main = canvas_size * 0.14
    r_sub = canvas_size * 0.08
    line_w = max(int(canvas_size * 0.035), 2)

    # 4 satellite nodes around central hub
    nodes = [
        (cx - canvas_size * 0.26, cy - canvas_size * 0.22), # top-left
        (cx + canvas_size * 0.26, cy - canvas_size * 0.20), # top-right
        (cx - canvas_size * 0.24, cy + canvas_size * 0.24), # bottom-left
        (cx + canvas_size * 0.25, cy + canvas_size * 0.22), # bottom-right
    ]

    # Draw connection lines first (central node to satellites)
    for nx, ny in nodes:
        draw.line([(cx, cy), (nx, ny)], fill=ORANGE, width=line_w)

    # Also connect top-left to bottom-left, top-right to bottom-right
    draw.line([nodes[0], nodes[2]], fill=ORANGE, width=max(1, line_w - 2))
    draw.line([nodes[1], nodes[3]], fill=ORANGE, width=max(1, line_w - 2))

    # Satellite nodes
    for i, (nx, ny) in enumerate(nodes):
        fill_col = CREAM if i % 2 == 1 else ORANGE
        draw.ellipse([(nx - r_sub, ny - r_sub), (nx + r_sub, ny + r_sub)], fill=fill_col, outline=BG_COLOR, width=max(1, line_w // 2))

    # Center hub node (prominent orange node with cream core)
    draw.ellipse([(cx - r_main, cy - r_main), (cx + r_main, cy + r_main)], fill=ORANGE)
    core_r = r_main * 0.45
    draw.ellipse([(cx - core_r, cy - core_r), (cx + core_r, cy + core_r)], fill=CREAM)

    # Downsample with Lanczos
    return img.resize((size, size), Image.Resampling.LANCZOS)

for s in [16, 32, 48, 128]:
    out_path = os.path.join(ICON_DIR, f"icon-{s}.png")
    icon = draw_network_icon(s)
    icon.save(out_path, "PNG")
    print(f"Generated {out_path} ({s}x{s})")

# Generate 440x280 small promo tile
def draw_promo_tile():
    w, h = 440, 280
    scale = 2
    canvas_w, canvas_h = w * scale, h * scale
    img = Image.new("RGBA", (canvas_w, canvas_h), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Left side: prominent network node icon
    icon_size = int(canvas_h * 0.55)
    icon = draw_network_icon(icon_size // scale)
    icon_resized = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
    img.paste(icon_resized, (int(canvas_w * 0.1), int((canvas_h - icon_size) / 2)), icon_resized)

    # Decorative background network lines
    bg_lines = [
        ((canvas_w * 0.65, canvas_h * 0.2), (canvas_w * 0.85, canvas_h * 0.35)),
        ((canvas_w * 0.85, canvas_h * 0.35), (canvas_w * 0.75, canvas_h * 0.75)),
        ((canvas_w * 0.75, canvas_h * 0.75), (canvas_w * 0.60, canvas_h * 0.60)),
    ]
    for p1, p2 in bg_lines:
        draw.line([p1, p2], fill=(60, 42, 34), width=4)
        draw.ellipse([(p1[0]-8, p1[1]-8), (p1[0]+8, p1[1]+8)], fill=ORANGE)

    # Resize to 440x280
    final = img.resize((w, h), Image.Resampling.LANCZOS)
    out_path = os.path.join(STORE_DIR, "promo-tile-440x280.png")
    final.save(out_path, "PNG")
    print(f"Generated {out_path} (440x280)")

draw_promo_tile()

