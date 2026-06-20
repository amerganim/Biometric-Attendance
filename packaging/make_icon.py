"""Generate packaging/icon.ico — a simple 'face-scan' app icon.

Run once (committed output, so you don't need to re-run unless changing the design):
    .venv\\Scripts\\python.exe packaging\\make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
white = (255, 255, 255, 255)

# Blue rounded-square background.
d.rounded_rectangle([6, 6, S - 6, S - 6], radius=52, fill=(37, 99, 235, 255))

# Scanner corner brackets.
w, m, L = 14, 46, 44
def bracket(x, y, dx, dy):
    d.line([(x, y), (x + dx * L, y)], fill=white, width=w)
    d.line([(x, y), (x, y + dy * L)], fill=white, width=w)
bracket(m, m, 1, 1)
bracket(S - m, m, -1, 1)
bracket(m, S - m, 1, -1)
bracket(S - m, S - m, -1, -1)

# Simple face.
cx, cy = S // 2, S // 2 + 2
d.ellipse([cx - 44, cy - 50, cx + 44, cy + 46], outline=white, width=12)
d.ellipse([cx - 25, cy - 16, cx - 11, cy - 2], fill=white)   # left eye
d.ellipse([cx + 11, cy - 16, cx + 25, cy - 2], fill=white)   # right eye
d.arc([cx - 26, cy - 4, cx + 26, cy + 32], start=18, end=162, fill=white, width=10)  # smile

out = Path(__file__).resolve().parent / "icon.ico"
img.save(out, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("wrote", out)
