# Live aurora for the Roulette Radio globe.
# Input: NOAA SWPC OVATION aurora forecast (ovation_aurora_latest.json: [longitude 0..359, latitude -90..90, probability 0..100]).
# Output: aurora.webp, single channel, white = likely aurora, equirectangular like the cloud mask (lng -180 at the left, lat +90 at the top).
# Usage: python make_aurora.py ovation.json outdir   (prints "ok <forecast time> <max>")
import sys, json
import numpy as np
from PIL import Image, ImageFilter

j = json.load(open(sys.argv[1], encoding='utf-8'))
g = np.zeros((181, 360), np.float32)
for lon, lat, v in j['coordinates']:
    g[90 - int(lat), (int(lon) + 180) % 360] = v
g = np.maximum(g - 3, 0)   # the model's background noise (1-3 %) stays dark
if g.max() <= 0: sys.exit('no aurora data')
# probability 0..100 -> 0..255 (a 50 % chance already shows bright), then smooth out the one-degree cells
im = Image.fromarray(np.clip(g / 50 * 255, 0, 255).astype(np.uint8), 'L').resize((720, 360), Image.BICUBIC).filter(ImageFilter.GaussianBlur(1.2))
im.save(f'{sys.argv[2]}/aurora.webp', quality=85, method=6)
print('ok', j.get('Forecast Time', ''), int(g.max()))
