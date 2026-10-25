# rr-clouds

Live cloud cover for the 3D globe of [Roulette Radio](https://rouletteradio.com).

Every hour a GitHub Actions job takes the latest **NOAA GMGSI** (Global Mosaic of Geostationary Satellite Imagery) longwave infrared mosaic from NOAA's nowCOAST map service, turns it into a cloud mask (`make_clouds.py`) and publishes it on GitHub Pages:

- `clouds.json`: the time and source of the latest mask, e.g. `{"t":"2026-10-25T16:50:12Z","v":"2026102516","src":"NOAA GMGSI",...}`
- `clouds2k.webp` (2048x1024) and `clouds4k.webp` (4096x2048): white = cloud, equirectangular, longitude -180 at the left, latitude +90 at the top.

The mosaic covers about 72.7°S to 72.7°N. Beyond that, and wherever the mosaic has no data, the static NASA Blue Marble cloud map (`static_clouds4k.webp`) is blended in. Infrared shows cold cloud tops best: warm low cloud and fog show weakly, and cold snow or ice can look like thin cloud.

`log.csv` records each run: time, share of valid pixels between 60°S and 60°N, mean cloud opacity.

## Sources and licences

- Cloud data: NOAA/NESDIS GMGSI via nowCOAST (U.S. Government data, open to the public). The masks are a modified product of that data; no NOAA endorsement is implied.
- Polar fill: NASA Blue Marble clouds (NASA Goddard Space Flight Center, Reto Stöckli), public domain.
- Code: MIT.
