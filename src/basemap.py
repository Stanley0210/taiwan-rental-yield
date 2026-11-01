"""
basemap.py — streets, MRT, water and stations for the map.

Source: OpenStreetMap via the Overpass API, queried ONCE at build time and cached
to disk. Licence ODbL, which requires attribution; the page credits
"© OpenStreetMap contributors" next to the map.

This is a build-time dependency, never a runtime one. The published page still
makes exactly one network request — for its own payload — and there is a test
that fails if an off-origin URL ever appears in housing.js. Tiles would have
broken that; baked geometry does not.

Everything is projected to TWD97 / TM2 with boundaries.lonlat_to_tm2 so it shares
one coordinate space with the buildings and the district outlines, and simplified
with a per-layer tolerance in METRES — so the tolerance means something physical
rather than being a magic number.

Layer design follows what the layer is FOR:

  water     largest features, coarsest tolerance; they orient the eye and the
            Taipei basin is unreadable without 淡水河 and 基隆河
  roads     split into a major set (motorway/trunk/primary) drawn at all zooms
            and a secondary set revealed on zoom-in, because 3,700 secondary
            roads at full extent is a grey smear, not information
  mrt       the strongest single orienting feature in Taipei, and the variable
            most people actually price property against
  stations  points with names, labelled only when zoomed in
"""

import json
import os

import boundaries as BD

CACHE = os.environ.get("GEO_CACHE", "data/geo")
OVERPASS = "https://overpass-api.de/api/interpreter"

# Taipei + New Taipei, generously bounded.
BBOX_WIDE = (24.67, 121.29, 25.32, 122.02)
# The built-up basin. Secondary roads and water outside it are not worth bytes.
BBOX_CORE = (24.75, 121.35, 25.25, 121.75)
# The whole island. Used ONLY for the metro layers.
#
# The station layer used to come out of BBOX_CORE with the rest of the basemap,
# which meant it held the Taipei network and nothing else -- 131 stations. The
# yield-vs-distance section still gave every building a "distance to the nearest
# station", so a Kaohsiung flat scored 274,843 m and a Taichung one 112,217 m.
# Those are distances to Taipei, and they made a national panel out of what was
# really a map of which city you are in.
#
# Stations are points and subway lines are short, so widening just these two to
# the island costs almost nothing in bytes, while roads, rivers and water stay
# bounded to the basin where they are worth their weight.
BBOX_TW = (21.90, 120.00, 25.35, 122.05)

_QUERIES = {
    "roads_major": ('[out:json][timeout:180];'
                    '(way["highway"~"^(motorway|trunk|primary)$"](%f,%f,%f,%f););'
                    'out geom;') % BBOX_WIDE,
    "extras": ('[out:json][timeout:300];('
               'way["highway"="secondary"](%f,%f,%f,%f);'
               'way["waterway"="river"](%f,%f,%f,%f);'
               'way["natural"="water"](%f,%f,%f,%f);'
               ');out geom;') % (BBOX_CORE * 3),
    # 高雄捷運 and 高雄輕軌, 臺中捷運, 桃園機場捷運 and 臺北捷運. light_rail is
    # included because 高雄's circular line is tagged that way and it is a metro
    # to anyone standing at a stop.
    "metro": ('[out:json][timeout:300];('
              'way["railway"~"^(subway|light_rail)$"](%f,%f,%f,%f);'
              'node["station"~"^(subway|light_rail)$"](%f,%f,%f,%f);'
              ');out geom;') % (BBOX_TW * 2),
}


def _fetch(name, cache_dir):
    path = os.path.join(cache_dir, name + ".json")
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        return path
    os.makedirs(cache_dir, exist_ok=True)
    try:
        import requests
        print(f"[base] querying Overpass for {name} (once; then cached)")
        r = requests.post(OVERPASS, data=_QUERIES[name].encode("utf-8"), timeout=330)
        if r.status_code != 200 or len(r.content) < 10000:
            print(f"[base] {name}: http {r.status_code}, {len(r.content)} bytes")
            return ""
        with open(path, "wb") as f:
            f.write(r.content)
        return path
    except Exception as e:
        print(f"[base] {name}: {e}")
        return ""


def _load(name, cache_dir):
    p = _fetch(name, cache_dir)
    if not p:
        return []
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("elements", [])
    except Exception as e:
        print(f"[base] parse {name}: {e}")
        return []


def _tag(e, *keys):
    t = e.get("tags") or {}
    for k in keys:
        if k in t:
            return t[k]
    return None


def _lines(elements, pred, tol, min_pts=2):
    """Project + simplify matching ways into lists of [x, y] pairs."""
    out = []
    for e in elements:
        if e.get("type") != "way" or not pred(e):
            continue
        g = e.get("geometry") or []
        if len(g) < min_pts:
            continue
        pts = [BD.lonlat_to_tm2(p["lon"], p["lat"]) for p in g]
        s = BD._rdp(pts, tol)
        if len(s) >= min_pts:
            out.append([[int(round(x)), int(round(y))] for x, y in s])
    return out


def _polys(elements, pred, tol, min_area):
    out = []
    for e in elements:
        if e.get("type") != "way" or not pred(e):
            continue
        g = e.get("geometry") or []
        if len(g) < 4:
            continue
        pts = [BD.lonlat_to_tm2(p["lon"], p["lat"]) for p in g]
        if BD._area(pts) < min_area:
            continue
        s = BD._rdp(pts, tol)
        if len(s) >= 4:
            out.append([[int(round(x)), int(round(y))] for x, y in s])
    return out


def to_path(polylines, quant=4):
    """Encode many polylines as ONE delta-encoded SVG path string.

    OSM splits a road into thousands of two-point ways, so a nested
    [[[x,y],[x,y]], ...] structure spends more bytes on brackets and repeated
    7-digit TWD97 coordinates than on shape -- 467 KB for a basemap that draws
    in a single <path>. Emitting the `d` attribute at build time, with relative
    `l` commands on a `quant`-metre grid, cuts that by roughly 5x and also means
    the browser gets one path element per layer instead of 4,685.

    `quant` is metres per unit. At 4 m it is far below one screen pixel at any
    zoom this map offers, so nothing visible is lost.
    """
    out = []
    for line in polylines:
        if len(line) < 2:
            continue
        px = py = None
        for i, (x, y) in enumerate(line):
            qx, qy = int(round(x / quant)), int(round(y / quant))
            if i == 0:
                out.append("M%d %d" % (qx, qy))
            else:
                dx, dy = qx - px, qy - py
                if dx == 0 and dy == 0:
                    continue
                out.append("l%d %d" % (dx, dy))
            px, py = qx, qy
    return "".join(out)


def build(cache_dir=None):
    """All basemap layers, projected and simplified. {} if unavailable."""
    cache_dir = cache_dir or CACHE
    major = _load("roads_major", cache_dir)
    extra = _load("extras", cache_dir)
    metro = _load("metro", cache_dir)
    if not major and not extra and not metro:
        print("[base] no basemap data - the map will render without streets")
        return {}

    out = {
        "major": _lines(major, lambda e: _tag(e, "highway") in
                        ("motorway", "trunk", "primary"), 30.0),
        "secondary": _lines(extra, lambda e: _tag(e, "highway") == "secondary", 35.0),
        "mrt": _lines(metro, lambda e: _tag(e, "railway") in ("subway", "light_rail"),
                      25.0),
        "river": _lines(extra, lambda e: _tag(e, "waterway") == "river", 45.0),
        # 8 ha floor. Set at 60 ha this kept only 4 polygons and lost the
        # 淡水河 / 基隆河 surfaces, which are the features that make the Taipei
        # basin legible at a glance.
        "water": _polys(extra, lambda e: _tag(e, "natural") == "water", 45.0, 80000.0),
        "stations": [],
    }
    # The station's KIND ships with it. Whether 輕軌 counts as a station is a
    # judgement, not a fact, and it turns out to decide the answer: on heavy rail
    # alone 新北市 shows a 0.52pp yield gradient with separated intervals, and
    # adding 淡海輕軌 -- which serves the outer 淡水 area that WAS the far group --
    # collapses it to 0.01pp. A page that picked one definition silently would be
    # publishing a choice as a finding.
    seen = set()
    for e in metro:
        if e.get("type") != "node":
            continue
        kind = _tag(e, "station")
        if kind not in ("subway", "light_rail"):
            continue
        name = _tag(e, "name:zh", "name")
        if not name or name in seen:
            continue
        seen.add(name)
        x, y = BD.lonlat_to_tm2(e["lon"], e["lat"])
        out["stations"].append([int(round(x)), int(round(y)), name,
                                0 if kind == "subway" else 1])

    pts = sum(len(s) for k, v in out.items() if k != "stations" for s in v)
    quant = 4
    paths = {k: to_path(v, quant) for k, v in out.items() if k != "stations"}
    paths["stations"] = [[int(round(x / quant)), int(round(y / quant)), n, k]
                         for x, y, n, k in out["stations"]]
    paths["quant"] = quant
    paths["attribution"] = "\u00a9 OpenStreetMap contributors (ODbL)"
    size = sum(len(v) for v in paths.values() if isinstance(v, str))
    print(f"[base] {pts:,} points -> {size // 1024} KB of path data "
          f"({len(paths['stations'])} stations)")
    return paths


if __name__ == "__main__":
    b = build()
    print(json.dumps({k: len(v) for k, v in b.items()}, ensure_ascii=False))
