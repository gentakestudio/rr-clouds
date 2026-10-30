"""Live sun for the Roulette Radio globe: what NASA's Solar Dynamics Observatory saw in extreme ultraviolet (AIA 171 Angstrom) in the last hours.
Input: the browse frames on sdo.gsfc.nasa.gov (one every 10 minutes, 5 minutes behind real time, no CORS, so the page cannot read them itself).
Output: sun.webp, one grey picture: six frames of the last ten hours, oldest first, three across and two down. The page's shader knows that layout and puts NASA's gold back.
Every cell: black background, the disc exactly centred, its bright rim at 40 % of the cell's width, the burned-in caption gone, faded to black at 1.24 disc radii.
The older frames are turned forward to the newest one's moment (the newest stays untouched), so the frames line up and a loop shows the Sun changing, not a rocking globe.
The archive also holds blank frames, cut ones, the Moon crossing the disc, off-pointed and smeared frames: each frame is checked and those are skipped.
Too few good frames, or anything else wrong: exits non-zero and leaves outdir exactly as it was.
Usage: python make_sun.py outdir [cell=512] [quality=85]   (prints "ok <newest frame> <bytes>", details on stderr)"""
import datetime as dt, io, math, os, re, shutil, sys, tempfile, time, urllib.error, urllib.request
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

BASE = 'https://sdo.gsfc.nasa.gov/assets/img/browse'
UA = {'User-Agent': 'RouletteRadio/1.0 (+https://rouletteradio.com)'}
N, STEP, COLS, ROWS = 6, 120, 3, 2     # six frames two hours apart, 3 x 2. The page's shader has the 6 and the 3 x 2 too
RIM = .4                      # the bright rim's radius as a share of the cell's width
FADE = 1.04, 1.24             # the picture fades out between these radii; the frame's edge is 1.25 radii away in January, so this stays inside it
CENTRE = 511.3, 511.75        # the disc's usual centre in a 1024 px frame (pixel indices), steady to 0.3 px all year
MAX_AGE = 360                 # minutes: the newest good frame must be this fresh
MAX_FETCH = 48                # frames tried in one run, so a long outage cannot turn into hundreds of downloads (the longest seen took 33)
BUDGET = 150                  # seconds for the downloads, so a stalled server cannot hold up the clouds
DAY_DEG = 13.2                # the disc's turn as seen from Earth, degrees a day, near its equator (measured here: 13.1 to 13.2)

def log(*a): print(*a, file=sys.stderr, flush=True)

def get(url, tries=2):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r: return r.read()
        except Exception as e:
            if i == tries - 1 or (isinstance(e, urllib.error.HTTPError) and e.code == 404): raise
            time.sleep(3)

def utc(stamp): return dt.datetime.strptime(stamp, '%Y%m%d_%H%M%S').replace(tzinfo=dt.timezone.utc)
def iso(stamp): return utc(stamp).strftime('%Y-%m-%dT%H:%M:%SZ')

def listing(day, px):
    """One UTC day's frames as stamps like 20261030_093658 (a day that has not started there yet is simply empty)."""
    try: return re.findall(rf'href="(\d{{8}}_\d{{6}})_{px}_0171\.jpg"', get(f'{BASE}/{day:%Y/%m/%d}/').decode('latin-1'))
    except Exception as e:
        log('listing', day, 'failed:', repr(e)[:90]); return []

def expected_rim(t):
    """The rim's radius in a 1024 px frame. The frames have a fixed scale, so the disc grows and shrinks with the Earth's distance from the Sun: 397 px in July, 410 px in January."""
    n = (t - dt.datetime(2000, 1, 1, 12, tzinfo=dt.timezone.utc)).total_seconds() / 86400
    g = math.radians((357.528 + .9856003 * n) % 360)
    return 959.63 / (1.00014 - .01671 * math.cos(g) - .00014 * math.cos(2 * g)) / 2.3785

def tilt(t):
    """How far the Sun's north pole leans towards us, radians (up to 7.25 degrees either way through the year)."""
    n = (t - dt.datetime(2000, 1, 1, 12, tzinfo=dt.timezone.utc)).total_seconds() / 86400
    lon = math.radians(280.46 + .9856474 * n + 1.915 * math.sin(math.radians(357.528 + .9856003 * n)))
    return math.asin(math.sin(lon - math.radians(73.667 + 1.3958333 * (n / 36525 + 1))) * math.sin(math.radians(7.25)))

def luma(a): return a[..., 0] * .2126 + a[..., 1] * .7152 + a[..., 2] * .0722
def grey(a): return (luma(a.astype(np.float32)) + .5).clip(0, 255).astype(np.uint8)      # one channel: 27 % fewer bytes and a quarter of the GPU memory

def find_rim(L, r0):
    """The disc in a 1024 px picture: the brightest point on each ray near the radius r0, then a circle through those points, dropping outliers.
    Returns x, y (pixel indices), radius, the scatter around the circle in px and the share of rays used. The sharpest edge will not do: the disc's own structure confuses it."""
    th = np.arange(720) * np.pi / 360
    rr = np.arange(r0 - 13, r0 + 13, .25)
    c = (L.shape[0] - 1) / 2
    x, y = c + np.outer(np.cos(th), rr), c + np.outer(np.sin(th), rr)
    ix, iy = x.astype(int), y.astype(int); fx, fy = x - ix, y - iy
    p = L[iy, ix] * (1 - fx) * (1 - fy) + L[iy, ix + 1] * fx * (1 - fy) + L[iy + 1, ix] * (1 - fx) * fy + L[iy + 1, ix + 1] * fx * fy
    w = 7; s = np.cumsum(np.c_[np.zeros(len(p)), p], 1); p = (s[:, w:] - s[:, :-w]) / w; rr = rr[w // 2:][:p.shape[1]]    # 1.5 px along the ray
    r = rr[p.argmax(1)]; x, y = c + np.cos(th) * r, c + np.sin(th) * r
    keep = (r > rr[2]) & (r < rr[-3])           # a peak at the window's end is no peak
    if keep.sum() < 100: return None
    for _ in range(8):
        A = np.c_[2 * x[keep], 2 * y[keep], np.ones(keep.sum())]
        a, b, k = np.linalg.lstsq(A, x[keep] ** 2 + y[keep] ** 2, rcond=None)[0]
        R = math.sqrt(k + a * a + b * b); res = np.hypot(x - a, y - b) - R
        keep = abs(res) < max(2.5 * res[keep].std(), .4)
        if keep.sum() < 100: return None
    return a, b, R, float(res[keep].std()), float(keep.mean())

def check(im, t):
    """Is this a whole, sharp, centred sun? Returns (x, y, radius) on the 1024 px scale and None, or None and the reason."""
    a = np.asarray(im if im.width == 1024 else im.resize((1024, 1024), Image.BOX), np.float32)
    L = luma(a); r0 = expected_rim(t); f = find_rim(L, r0)
    if f is None: return None, 'no disc found'
    x, y, R, sd, used = f
    off = math.hypot(x - CENTRE[0], y - CENTRE[1])
    if off > 1.5: return None, f'off-pointed by {off:.1f} px'
    if abs(R - r0) > 1.5: return None, f'rim at {R:.1f} px, expected {r0:.1f}'
    if sd > 1 or used < .6: return None, f'not round (scatter {sd:.2f} px, {used:.0%} of the rim)'
    yy, xx = np.indices(L.shape); r = np.hypot(xx - x, yy - y); on = r < .97 * R; d = L[on]
    hole = (L[r < 1.1 * R] < 3).mean()         # 0 on every good frame: the disc and the corona next to it are never black
    if hole > .001: return None, f'{hole:.1%} of the disc and its edge is black'
    if not 40 < d.mean() < 170: return None, f'disc brightness {d.mean():.0f}'
    edge = abs(4 * L[1:-1, 1:-1] - L[:-2, 1:-1] - L[2:, 1:-1] - L[1:-1, :-2] - L[1:-1, 2:])[on[1:-1, 1:-1]].mean()      # the Laplacian: 6 or more on a sharp frame, 3.4 at most on a smeared one
    if edge < 4.5: return None, f'smeared ({edge:.1f})'
    return (x, y, R), None

def fetch(stamp, px):
    """One frame, decoded and checked. Returns (stamp, picture, fit) or None."""
    t = utc(stamp)
    try:
        b = get(f'{BASE}/{t:%Y/%m/%d}/{stamp}_{px}_0171.jpg')
        im = Image.open(io.BytesIO(b)); im.load(); im = im.convert('RGB')      # load() fails on a cut file
    except Exception as e:
        log('skip', stamp, 'cannot read:', repr(e)[:90]); return None
    if im.size != (px, px): log('skip', stamp, 'size', im.size); return None
    fit, why = check(im, t)
    if why: log('skip', stamp, why); return None
    return stamp, im, fit

def choose(stamps, n, step, px, now):
    """Walks back from the newest frame, taking the first good frame and then one good frame every `step` minutes. After an outage the steps are simply longer."""
    span = (n - 1) * step * 2 + MAX_AGE
    got, tried, t0 = [], 0, time.time()
    for s in sorted(set(stamps), reverse=True):
        t = utc(s); age = (now - t).total_seconds() / 60
        if age > (span if got else MAX_AGE) or tried >= MAX_FETCH or time.time() - t0 > BUDGET: break
        if got and (utc(got[-1][0]) - t).total_seconds() / 60 < step - 5: continue
        tried += 1
        f = fetch(s, px)
        if f: got.append(f)
        if len(got) == n: break
    return got[::-1], tried      # oldest first

def align(im, fit, minutes, lean):
    """Turns the disc forward by `minutes`, faster at the equator than near the poles. Off the disc nothing moves, and the shift eases to nothing at the rim."""
    a = np.asarray(im, np.float32); n = im.width; s = n / 1024
    cx, cy, Rs = (fit[0] + .5) * s - .5, (fit[1] + .5) * s - .5, fit[2] * s * .991       # the rim stands 0.9 % above the surface
    yy, xx = np.indices((n, n)); u, v = (xx - cx) / Rs, (cy - yy) / Rs
    z = np.sqrt(np.clip(1 - u * u - v * v, 0, 1)); cb, sb = math.cos(lean), math.sin(lean)
    sy, zh = v * cb + z * sb, z * cb - v * sb           # sy: the sine of the latitude
    lat, lon = np.arcsin(np.clip(sy, -1, 1)), np.arctan2(u, zh)
    s2 = sy * sy
    lon = lon - np.radians((DAY_DEG - 2.4 * s2 - 1.8 * s2 * s2) * minutes / 1440)
    x2, z2h = np.cos(lat) * np.sin(lon), np.cos(lat) * np.cos(lon)
    v2, z2 = sy * cb - z2h * sb, sy * sb + z2h * cb
    w = np.clip((np.minimum(z, np.maximum(z2, 0)) - .02) / .18, 0, 1) * (u * u + v * v < .999); w = w * w * (3 - 2 * w)
    fx, fy = xx + (cx + x2 * Rs - xx) * w, yy + (cy - v2 * Rs - yy) * w
    ix, iy = np.clip(fx.astype(int), 0, n - 2), np.clip(fy.astype(int), 0, n - 2); fx, fy = (fx - ix)[..., None], (fy - iy)[..., None]
    a = a[iy, ix] * (1 - fx) * (1 - fy) + a[iy, ix + 1] * fx * (1 - fy) + a[iy + 1, ix] * (1 - fx) * fy + a[iy + 1, ix + 1] * fx * fy
    return Image.fromarray((a + .5).clip(0, 255).astype(np.uint8))

def to_cell(im, fit, size):
    """One cell: caption gone, the disc exactly centred, the rim at RIM of the width, faded out."""
    x, y, R = fit; s = im.width / 1024
    # a soft dark box over the caption: its nearest letter is only 1.18 radii out, where the corona is still bright, so a radial fade alone would have to cut the corona there
    box = Image.new('L', im.size, 0); ImageDraw.Draw(box).rectangle((-40, 976 * s, 506 * s, im.height + 40), fill=255)
    box = box.filter(ImageFilter.GaussianBlur(5 * s))
    pad = int(14 * s)            # the crop reaches 1.25 radii, a pixel past the frame in January
    im = ImageOps.expand(Image.composite(Image.new('RGB', im.size, 0), im, box), pad, 0)
    X, Y, h = (x + .5) * s + pad, (y + .5) * s + pad, R * s / (2 * RIM)
    a = np.asarray(im.resize((size, size), Image.LANCZOS, box=(X - h, Y - h, X + h, Y + h)), np.float32)
    c = (size - 1) / 2; yy, xx = np.indices((size, size))
    t = np.clip((FADE[1] - np.hypot(xx - c, yy - c) / (RIM * size)) / (FADE[1] - FADE[0]), 0, 1)
    return (a * (t * t * (3 - 2 * t))[..., None] + .5).clip(0, 255).astype(np.uint8)

def change(cells):
    """Mean absolute difference between neighbouring cells on the disc, 0..255."""
    size = cells[0].shape[0]; c = (size - 1) / 2; yy, xx = np.indices((size, size)); d = np.hypot(xx - c, yy - c) < .95 * RIM * size
    return [float(abs(a.astype(np.float32) - b.astype(np.float32))[d].mean()) for a, b in zip(cells, cells[1:])]

def publish(frames, out, size, q):
    """Writes sun.webp beside outdir, reads it back, and only then moves it in: outdir never holds a partial result."""
    last = utc(frames[-1][0]); lean = tilt(last)
    cells = [grey(to_cell(align(im, fit, (last - utc(s)).total_seconds() / 60, lean) if s != frames[-1][0] else im, fit, size)) for s, im, fit in frames]
    atlas = np.zeros((ROWS * size, COLS * size), np.uint8)
    for i, c in enumerate(cells): atlas[(i // COLS) * size: (i // COLS + 1) * size, (i % COLS) * size: (i % COLS + 1) * size] = c
    os.makedirs(out, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='sun-', dir=os.path.dirname(os.path.abspath(out)))      # beside outdir, not in it: a killed run leaves nothing to publish
    try:
        Image.fromarray(atlas).save(f'{tmp}/sun.webp', quality=q, method=6)
        # read back what was really written
        back = np.asarray(Image.open(f'{tmp}/sun.webp').convert('L'), np.float32)
        if back.shape != atlas.shape: sys.exit('the written file has the wrong size')
        for i in range(N):
            c = back[(i // COLS) * size: (i // COLS + 1) * size, (i % COLS) * size: (i % COLS + 1) * size]
            if abs(c.mean() - cells[i].mean()) > 3: sys.exit(f'cell {i} does not match')
            if max(c[0].max(), c[-1].max(), c[:, 0].max(), c[:, -1].max()) > 12: sys.exit(f'cell {i} does not fade out')
        big = np.asarray(Image.fromarray(c.astype(np.uint8)).resize((1024, 1024), Image.BICUBIC), np.float32)      # the newest cell
        f = find_rim(big, 1024 * RIM)
        if f is None or math.hypot(f[0] - 511.5, f[1] - 511.5) > 1 or abs(f[2] - 1024 * RIM) > 1.5: sys.exit('the result is not centred')
        bytes_out = os.path.getsize(f'{tmp}/sun.webp')
        os.replace(f'{tmp}/sun.webp', f'{out}/sun.webp')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return bytes_out, cells

def main(out, size=512, q=85):
    t0 = time.time(); now = dt.datetime.now(dt.timezone.utc)
    px = 1024 if size <= 512 else 2048     # a 1024 px cell needs the sharper source
    span = (N - 1) * STEP * 2 + MAX_AGE
    stamps = []
    for day in sorted({(now - dt.timedelta(minutes=m)).date() for m in (0, span // 2, span)}): stamps += listing(day, px)     # 26 h can cross two midnights
    if not stamps: sys.exit('no frames listed')
    frames, tried = choose(stamps, N, STEP, px, now)
    if len(frames) < N: sys.exit(f'too few good frames: {len(frames)} of {N} after trying {tried}, nothing written')
    bytes_out, cells = publish(frames, out, size, q)
    log(f'{N} frames from {tried} tried, oldest {frames[0][0]}, change per step {np.mean(change(cells)):.2f} of 255, {bytes_out} bytes, {time.time() - t0:.1f} s')
    print('ok', iso(frames[-1][0]), bytes_out)

if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    main(a[0], *[int(v) for v in a[1:]])
