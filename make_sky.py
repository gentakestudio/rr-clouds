# Asteroid and comet flybys for the Roulette Radio globe's "today in the sky".
# Input: two NASA/JPL SBDB Close-Approach (cad.api) answers: asteroids within 0.05 au (about 20 lunar distances) and comets within 1 au.
# Output: sky.json - for each flyby: name, time (UTC, ISO), distance (km), speed (km/s) and an estimated size (m, from H with albedo 0.14).
# Usage: python make_sky.py cad_asteroids.json cad_comets.json outdir   (prints "ok <count>")
import sys, json, datetime

AU = 149597870.7
MON = {m: i for i, m in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], 1)}

def rows(path, kind):
    try:
        j = json.load(open(path, encoding='utf-8'))
    except Exception:
        return []
    f = j.get('fields', []); out = []
    for r in j.get('data', []) or []:
        d = dict(zip(f, r))
        y, mo, rest = d['cd'].split('-'); day, hm = rest.split(' ')
        t = datetime.datetime(int(y), MON[mo], int(day), int(hm[:2]), int(hm[3:5]), tzinfo=datetime.timezone.utc)
        name = (d.get('fullname') or d['des']).strip()
        e = {'k': kind, 'n': name, 't': t.strftime('%Y-%m-%dT%H:%MZ'), 'km': round(float(d['dist']) * AU), 'v': round(float(d['v_rel']), 1)}
        if d.get('diameter'):
            e['m'] = round(float(d['diameter']) * 1000)
        elif d.get('h'):
            e['m'] = round(1329 / 0.14 ** 0.5 * 10 ** (-float(d['h']) / 5) * 1000)
        out.append(e)
    return out

ev = rows(sys.argv[1], 'a') + rows(sys.argv[2], 'c')
ev.sort(key=lambda e: e['t'])
json.dump({'at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'), 'src': 'NASA/JPL SBDB Close-Approach Data', 'ev': ev},
          open(sys.argv[3] + '/sky.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('ok', len(ev))
