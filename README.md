# rr-clouds

Live cloud cover for the 3D globe of [Roulette Radio](https://rouletteradio.com).

Every hour a GitHub Actions job takes the latest **NOAA GMGSI** (Global Mosaic of Geostationary Satellite Imagery) longwave infrared mosaic from NOAA's nowCOAST map service, turns it into a cloud mask (`make_clouds.py`) and publishes it on GitHub Pages:

- `clouds.json`: the time and source of the latest mask, e.g. `{"t":"2026-10-25T16:50:12Z","v":"2026102516","src":"NOAA GMGSI",...}`
- `clouds2k.webp` (2048x1024) and `clouds4k.webp` (4096x2048): white = cloud, equirectangular, longitude -180 at the left, latitude +90 at the top.

The mosaic covers about 72.7°S to 72.7°N. Beyond that, and wherever the mosaic has no data, the static NASA Blue Marble cloud map (`static_clouds4k.webp`) is blended in. Infrared shows cold cloud tops best: warm low cloud and fog show weakly, and cold snow or ice can look like thin cloud.

`log.csv` records each published mask: the mosaic's time, the run's time, share of valid pixels between 60°S and 60°N, mean cloud opacity. A run publishes nothing when the newest mosaic is already published or is more than 3 hours old.

`rad.json` holds background radiation near the site's stations for its Classic skin: `g` is one archive value per cell of stations `[lat, lon, uSv/h, latest year]` (the median of the Safecast ground readings within 75 km from the last five years, or from all years if those are too few; rows moving at flight speed and logs marked as flights are left out, and only bGeigie logs count: other devices differ in tubes and clocks; `rad_grid.json` keeps them, `rad_imports.json` remembers which logs were checked, and each run refreshes the oldest cells it has time for, at most 30), `l` is the live sensors heard in the last two days `[lat, lon, uSv/h, hour]`. It is a rough picture, not a warning system.

`sun.webp` (1536x1024, grey): six frames of NASA's SDO/AIA 171 from the last ten hours, oldest top left, three across and two down; each cell is centred with the rim at 40% of its width and black beyond 1.24 radii. `clouds.json` names it in `sun` and gives the newest frame's time in `sunT`. If NASA has no good frames, the last good picture is carried over.

## Sources and licences

- Cloud data: NOAA/NESDIS GMGSI via nowCOAST (U.S. Government data, open to the public). The masks are a modified product of that data; no NOAA endorsement is implied.
- Polar fill: NASA Blue Marble clouds (NASA Goddard Space Flight Center, Reto Stöckli), public domain.
- Background radiation: Safecast (https://safecast.org), CC0.
- Sun: NASA/SDO AIA 171. Courtesy of NASA/SDO and the AIA, EVE, and HMI science teams. Cropped, aligned and turned to grey by this job; no NASA endorsement is implied.
- Code: MIT.
