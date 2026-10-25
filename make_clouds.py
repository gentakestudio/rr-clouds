# Live cloud mask for the Roulette Radio globe.
# Input: NOAA GMGSI global longwave IR mosaic from nowCOAST (4096x2048 PNG, CRS:84, -180..180 / -90..90, grey = brightness: white is cold,
# alpha 0 outside about ±72.7°) and the static NASA cloud mask that fills the poles. Output: clouds2k.webp / clouds4k.webp, single channel,
# white = cloud, equirectangular (lng -180 at the left, lat +90 at the top), the same layout as the globe's static clouds.
# Usage: python make_clouds.py gmgsi.png static_clouds4k.webp outdir [g0 g1 gamma]   (prints the stats line the workflow logs)
import sys
import numpy as np
from PIL import Image, ImageFilter

src, static, out = sys.argv[1], sys.argv[2], sys.argv[3]
G0, G1, GAM = (float(x) for x in (sys.argv[4:7] if len(sys.argv) >= 7 else (88, 168, 0.9)))

im = Image.open(src).convert('LA')
if im.size != (4096, 2048): im = im.resize((4096, 2048), Image.BILINEAR)
a = np.asarray(im, dtype=np.float32)
g, alpha = a[..., 0], a[..., 1] / 255.0
H, W = g.shape
lat = 90 - (np.arange(H) + 0.5) / H * 180
alat = np.abs(lat)[:, None]

def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)

# no data: outside the mosaic (alpha 0) and the saturated blocks the mosaic sometimes has (255 over a wide area)
sat = (g >= 253).astype(np.float32)
sat_wide = np.asarray(Image.fromarray((sat * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(12)), dtype=np.float32) / 255 > 0.9
valid = (alpha > 0.5) & ~sat_wide

# brightness to opacity: clear ground and sea are darker than G0, thick cold cloud tops brighter than G1.
# Snow and ice are cold too, so the threshold rises towards the poles
lift = 40 * smooth(45, 70, alat)
op = smooth(G0 + lift, G1 + lift * 0.6, g) ** GAM

# poles and gaps: the static NASA mask, blended in over the last degrees of the mosaic
st = np.asarray(Image.open(static).convert('L').resize((W, H), Image.BILINEAR), dtype=np.float32) / 255
edge = smooth(72.5, 66, alat)                                  # 1 inside ±66°, 0 beyond ±72.5°
w = valid.astype(np.float32) * edge
w = np.asarray(Image.fromarray((w * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), dtype=np.float32) / 255
mask = w * op + (1 - w) * st

# a light blur against the satellite's pixel stair-steps, then sanity checks before anything is written
m = Image.fromarray(np.clip(mask * 255 + 0.5, 0, 255).astype(np.uint8), 'L').filter(ImageFilter.GaussianBlur(0.8))
band = np.asarray(m, dtype=np.float32)[(np.abs(lat) < 60)] / 255
frac_valid = float(valid[np.abs(lat) < 60].mean())
mean = float(band.mean())
print(f'valid ±60°: {frac_valid:.3f}  mean opacity ±60°: {mean:.3f}')
if frac_valid < 0.9 or not (0.15 < mean < 0.75):
    sys.exit('sanity check failed: not writing')
m.save(f'{out}/clouds4k.webp', quality=82, method=6)
m.resize((2048, 1024), Image.LANCZOS).save(f'{out}/clouds2k.webp', quality=82, method=6)
print(f'ok {frac_valid:.3f} {mean:.3f}')
