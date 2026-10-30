"""Background radiation near Roulette Radio's stations, from Safecast (CC0), for the Classic skin's terminal.
rad_grid.json (kept in this repo) holds one archive value per cell of stations; each run refreshes the oldest cells.
rad.json (published) adds the live sensors. Run: python make_rad.py site/rad.json [cells to refresh]
Safecast's bGeigie and most fixed sensors use LND 7317/7318 tubes, about 334 cpm per uSv/h; the 7128 tube about 108.
Other devices in the archive have other tubes (M4011 about 154, LND712 about 108), and some bad clocks and readings, and their rows do not say so: only bGeigie logs are trusted.
Safecast also holds logs from aircraft (1-5 uSv/h at cruising height): they are not the ground, so they are left out. Rows moving at flight speed go,
which also catches the many flights not marked as one and a ground log that ends in a flight; logs marked "Cosmic" go too.
Asking every log's subtype would take hours, so only logs that read high are asked; the answers stay in rad_imports.json."""
import collections, json, math, sys, time, statistics, urllib.error, urllib.request, urllib.parse, datetime as dt
UA = {"User-Agent": "RouletteRadio/1.0 (+https://rouletteradio.com)"}
API = "https://api.safecast.org/measurements.json"
SUSPECT = .25    # uSv/h: a log with a median at or above this is checked; aircraft read well above it
FLIGHT = 100     # m/s, faster than any train; airliners log 200-320
MIN_ROWS = 30    # 2.5 minutes of a bGeigie: fewer is a quick test or what is left of a flight, not a picture of the place
YEARS = 5        # the last years if they hold enough rows, otherwise all of them
BUDGET = 120     # seconds for the archive cells; whatever is left waits for the next run, the file still goes out
def get(u, t=40): return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t))
def usv(m):
    v, u = m.get("value"), (m.get("unit") or "").lower()
    if v is None or not m.get("measurement_import_id"): return None
    if u == "cpm": return v / 334
    if u in ("usv", "microsievert", "usv/h"): return v
    return None
def good(m, now):
    v, t = usv(m), m.get("captured_at")
    return v is not None and t and m.get("latitude") is not None and m.get("longitude") is not None and 0.005 < v < 50 and 2010 <= int(t[:4]) and when(m) <= now    # the archive has rows dated 2080
def when(m): return dt.datetime.fromisoformat(m["captured_at"].replace("Z", "+00:00"))
def metres(a, b):
    la, lb = math.radians(a["latitude"]), math.radians(b["latitude"])
    h = math.sin((lb - la) / 2) ** 2 + math.cos(la) * math.cos(lb) * math.sin(math.radians(b["longitude"] - a["longitude"]) / 2) ** 2
    return 12742000 * math.asin(min(1, math.sqrt(h)))
def in_the_air(rows):
    """The ids of the rows moving at flight speed, from neighbouring rows of the same log."""
    logs, air = collections.defaultdict(list), set()
    for m in rows: logs[m.get("measurement_import_id"), m.get("user_id"), m.get("device_id")].append(m)
    for ms in logs.values():
        ms.sort(key=when)
        for a, b in zip(ms, ms[1:]):
            s = (when(b) - when(a)).total_seconds()
            if 1 <= s <= 120 and metres(a, b) / s > FLIGHT: air.update((a["id"], b["id"]))
    return air
def cosmic(i, seen):
    k = str(i)
    if k not in seen:
        try: seen[k] = 1 if (get(f"https://api.safecast.org/bgeigie_imports/{i}.json").get("subtype") or "") == "Cosmic" else 0
        except urllib.error.HTTPError: return False    # the API fails on some old logs: the speed rule has already looked at them, and the next run asks again
        time.sleep(.2)
    return seen[k] == 1
def archive(lat, lon, seen, now):
    for since in (now - dt.timedelta(days=YEARS * 365), None):     # the API's order parameter does nothing, so recent rows can only be had by date
        p = {"latitude": lat, "longitude": lon, "distance": 75000, "per_page": 1000}   # distance is in metres
        if since: p["captured_after"] = f"{since:%Y-%m-%d %H:%M:%S}"
        rows = [m for m in get(API + "?" + urllib.parse.urlencode(p)) if good(m, now)]
        air = in_the_air(rows)
        rows = [m for m in rows if m["id"] not in air]
        logs = collections.defaultdict(list)
        for m in rows: logs[m.get("measurement_import_id")].append(usv(m))
        air = {i for i, v in logs.items() if i and statistics.median(v) >= SUSPECT and cosmic(i, seen)}
        rows = [m for m in rows if m.get("measurement_import_id") not in air]
        if len(rows) >= MIN_ROWS: return round(statistics.median(usv(m) for m in rows), 3), max(int(m["captured_at"][:4]) for m in rows)
    return None
def live():
    now, out = dt.datetime.now(dt.timezone.utc), []
    for d in get("https://tt.safecast.org/devices", 60):
        la, lo, w = d.get("loc_lat"), d.get("loc_lon"), d.get("when_captured")
        if la is None or lo is None or not w: continue
        try: age = (now - dt.datetime.fromisoformat(w.replace("Z", "+00:00"))).total_seconds()
        except ValueError: continue
        if age > 172800: continue    # two days
        c = [d[k] / 334 for k in ("lnd_7318u", "lnd_7318c") if d.get(k)] + [d["lnd_7128ec"] / 108 for k in ("lnd_7128ec",) if d.get(k)]
        c = [x for x in c if 0.005 < x < 50]
        if c: out.append([round(la, 2), round(lo, 2), round(min(c), 3), w[:13]])
    return out
def main(out, n):
    g = json.load(open("rad_grid.json", encoding="utf-8")); stamp = int(time.time()); done = 0; end = stamp + BUDGET
    now = dt.datetime.now(dt.timezone.utc)
    try: seen = json.load(open("rad_imports.json", encoding="utf-8"))
    except FileNotFoundError: seen = {}
    for c in sorted(g, key=lambda c: c.get("t", 0))[:n]:
        if time.time() > end and n <= 100: break    # a long fill by hand (n above 100) runs to the end
        c["t"] = stamp    # tried, even if it fails: a failing cell keeps its old value and waits for its next turn
        try:
            r = archive(c["la"], c["lo"], seen, now)
            if r: c["v"], c["y"] = r
            else: c.pop("v", None); c.pop("y", None)
            done += 1
        except Exception as e: print("cell failed:", e)
        time.sleep(.5)
    json.dump(g, open("rad_grid.json", "w", encoding="utf-8"), separators=(",", ":"))
    json.dump(seen, open("rad_imports.json", "w", encoding="utf-8"), separators=(",", ":"))
    try: l = live()
    except Exception as e: print("live sensors failed:", e); l = []
    rows = [[c["la"], c["lo"], c["v"], c["y"]] for c in g if "v" in c]
    if len(rows) < 100: sys.exit("too few cells: not publishing")
    json.dump({"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "g": rows, "l": l}, open(out, "w", encoding="utf-8"), separators=(",", ":"))
    print("rad:", len(rows), "cells,", len(l), "live sensors,", done, "refreshed,", sum(seen.values()), "aircraft logs known")
if __name__ == "__main__": main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 30)
