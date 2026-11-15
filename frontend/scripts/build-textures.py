"""Build the optimized Earth textures in public/textures from the downloaded sources.

Sources (see public/textures/ATTRIBUTION.md):
  earth-blue-marble.jpg      NASA Blue Marble (public domain), already in public/textures
  8k_earth_nightmap.jpg      Solar System Scope, CC BY 4.0 (based on NASA Black Marble)
  8k_earth_clouds.jpg        Solar System Scope, CC BY 4.0 (based on NASA imagery)
  2k_earth_normal_map.tif    Solar System Scope, CC BY 4.0
  2k_earth_specular_map.tif  Solar System Scope, CC BY 4.0

Outputs, each in 4k (4096x2048) and 2k (2048x1024) tiers:
  earth-day-{4k,2k}.jpg      colour
  earth-night-{4k,2k}.jpg    city lights, base darkened so only lights remain
  earth-clouds-{4k,2k}.jpg   cloud opacity (greyscale)
  earth-surface-2k.png       R,G = normal x,y   B = ocean mask (1 = water)

Usage: python scripts/build-textures.py /tmp/tex
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/tex")
OUT = Path(__file__).resolve().parent.parent / "public" / "textures"
TIERS = {"4k": (4096, 2048), "2k": (2048, 1024)}


def save_jpg(img: Image.Image, name: str, quality: int) -> None:
    path = OUT / name
    img.save(path, quality=quality, optimize=True, progressive=True)
    print(f"{name:26s} {img.size[0]}x{img.size[1]} {path.stat().st_size / 1e6:5.2f} MB")


day = Image.open(OUT / "earth-blue-marble.jpg").convert("RGB")
night = Image.open(SRC / "8k_earth_nightmap.jpg").convert("RGB")
clouds = Image.open(SRC / "8k_earth_clouds.jpg").convert("L")

# Night map: remove the dim blue terrain base so the shader adds only light sources.
n = np.asarray(night, dtype=np.float32)
lum = n.max(axis=2)
lights = np.clip((lum - 24.0) / (255.0 - 24.0), 0, 1) ** 0.9
n_out = Image.fromarray((n * lights[..., None] * 1.6).clip(0, 255).astype(np.uint8), "RGB")

# Clouds: lift the faint haze to 0 so thin clouds do not fog the whole planet.
c = np.asarray(clouds, dtype=np.float32) / 255.0
c = np.clip((c - 0.12) / 0.88, 0, 1)
c_out = Image.fromarray((c * 255).astype(np.uint8), "L")

for tier, size in TIERS.items():
    save_jpg(day.resize(size, Image.LANCZOS), f"earth-day-{tier}.jpg", 86)
    save_jpg(n_out.resize(size, Image.LANCZOS), f"earth-night-{tier}.jpg", 82)
    save_jpg(c_out.resize(size, Image.LANCZOS), f"earth-clouds-{tier}.jpg", 82)

normal = np.asarray(Image.open(SRC / "2k_earth_normal_map.tif").convert("RGB").resize(TIERS["2k"], Image.LANCZOS))
spec = np.asarray(Image.open(SRC / "2k_earth_specular_map.tif").convert("L").resize(TIERS["2k"], Image.LANCZOS))
packed = np.dstack([normal[..., 0], normal[..., 1], spec]).astype(np.uint8)
Image.fromarray(packed, "RGB").save(OUT / "earth-surface-2k.png", optimize=True)
print(f"{'earth-surface-2k.png':26s} 2048x1024 {(OUT / 'earth-surface-2k.png').stat().st_size / 1e6:5.2f} MB")

# Report the normal map's strength so the shader scale can be chosen sensibly.
nx = normal[..., 0].astype(np.float32) / 127.5 - 1
ny = normal[..., 1].astype(np.float32) / 127.5 - 1
print(f"normal xy deviation: mean |x|={np.abs(nx).mean():.3f} p99 |x|={np.percentile(np.abs(nx), 99):.3f} p99 |y|={np.percentile(np.abs(ny), 99):.3f}")
print(f"water fraction {(spec > 127).mean():.2f} (Earth ~0.71)")
