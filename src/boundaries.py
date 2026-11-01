"""
boundaries.py — district outlines for the map, parsed and projected in pure Python.

Source: 內政部國土測繪中心「鄉(鎮、市、區)界線」, the official administrative
boundary shapefile (政府資料開放授權條款-第1版). It ships as SHP only, in
geographic TWD97 (lat/lon), while every building coordinate on this site is
TWD97 / TM2 in metres. So this module does three things with no dependencies:

  1. reads the .shp polygon records and the .dbf attribute table
  2. projects lat/lon -> TM2 (forward transverse Mercator, GRS80)
  3. simplifies each ring so 41 districts fit in tens of kilobytes

Adding geopandas/pyshp/pyproj for this would pull a compiled GIS stack into a
project whose entire pitch is that it has no build step. The shapefile format is
a published, simple binary layout and transverse Mercator is a closed-form
formula; both are ~60 lines.

The projection is not taken on trust: `validate()` checks that buildings fall
inside the district polygon their own 實價登錄 record names. That catches a wrong
central meridian, a swapped axis or a bad datum immediately, because all three
would put points in the wrong polygon.
"""

import math
import os
import struct

# ── TWD97 / TM2 (EPSG:3826) ──────────────────────────────────────────────────
A = 6378137.0                     # GRS80 semi-major axis
F = 1 / 298.257222101             # GRS80 flattening
LON0 = math.radians(121.0)        # central meridian
K0 = 0.9999
FE, FN = 250000.0, 0.0


def lonlat_to_tm2(lon, lat):
    """Forward transverse Mercator. Returns (x, y) in metres."""
    e2 = 2 * F - F * F
    ep2 = e2 / (1 - e2)
    phi, lam = math.radians(lat), math.radians(lon)
    sin_p, cos_p, tan_p = math.sin(phi), math.cos(phi), math.tan(phi)
    N = A / math.sqrt(1 - e2 * sin_p * sin_p)
    T = tan_p * tan_p
    C = ep2 * cos_p * cos_p
    Ang = (lam - LON0) * cos_p
    M = A * (
        (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * phi
        - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * phi)
        + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * phi)
        - (35 * e2 ** 3 / 3072) * math.sin(6 * phi)
    )
    x = FE + K0 * N * (
        Ang + Ang ** 3 / 6 * (1 - T + C)
        + Ang ** 5 / 120 * (5 - 18 * T + T * T + 72 * C - 58 * ep2)
    )
    y = FN + K0 * (
        M + N * tan_p * (
            Ang ** 2 / 2 + Ang ** 4 / 24 * (5 - T + 9 * C + 4 * C * C)
            + Ang ** 6 / 720 * (61 - 58 * T + T * T + 600 * C - 330 * ep2)
        )
    )
    return x, y


# ── shapefile ────────────────────────────────────────────────────────────────

def read_dbf(path):
    """Minimal dBASE III reader. Returns a list of dicts of stripped strings."""
    with open(path, "rb") as f:
        raw = f.read()
    n_rec, hdr_len, rec_len = struct.unpack("<ihh", raw[4:12])
    fields, off = [], 32
    while raw[off] != 0x0D:
        name = raw[off:off + 11].split(b"\x00")[0].decode("utf-8", "ignore")
        length = raw[off + 16]
        fields.append((name, length))
        off += 32
    rows, pos = [], hdr_len
    for _ in range(n_rec):
        rec, p = {}, pos + 1                      # +1 skips the deletion flag
        for name, length in fields:
            rec[name] = raw[p:p + length].decode("utf-8", "ignore").strip()
            p += length
        rows.append(rec)
        pos += rec_len
    return rows


def read_shp_polygons(path):
    """Return one list of rings per record; each ring is a list of (lon, lat).

    Only shape type 5 (Polygon) is handled -- it is the only type this dataset
    contains, and silently accepting others would produce empty districts.
    """
    with open(path, "rb") as f:
        raw = f.read()
    out, pos, end = [], 100, len(raw)
    while pos < end:
        _, clen = struct.unpack(">ii", raw[pos:pos + 8])
        body = pos + 8
        shp_type, = struct.unpack("<i", raw[body:body + 4])
        if shp_type != 5:
            out.append([])
            pos = body + clen * 2
            continue
        n_parts, n_pts = struct.unpack("<ii", raw[body + 36:body + 44])
        p = body + 44
        parts = list(struct.unpack("<%di" % n_parts, raw[p:p + 4 * n_parts]))
        p += 4 * n_parts
        coords = struct.unpack("<%dd" % (2 * n_pts), raw[p:p + 16 * n_pts])
        rings = []
        for i, start in enumerate(parts):
            stop = parts[i + 1] if i + 1 < n_parts else n_pts
            rings.append([(coords[2 * j], coords[2 * j + 1]) for j in range(start, stop)])
        out.append(rings)
        pos = body + clen * 2
    return out


# ── simplification ───────────────────────────────────────────────────────────

def _rdp(pts, eps):
    """Ramer-Douglas-Peucker, iterative so a 20,000-point coastline ring cannot
    blow the recursion limit."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        ax, ay = pts[i]
        bx, by = pts[j]
        dx, dy = bx - ax, by - ay
        den = math.hypot(dx, dy)
        best, bi = -1.0, -1
        for k in range(i + 1, j):
            px, py = pts[k]
            d = (abs(dy * px - dx * py + bx * ay - by * ax) / den if den
                 else math.hypot(px - ax, py - ay))
            if d > best:
                best, bi = d, k
        if best > eps and bi > 0:
            keep[bi] = True
            stack.append((i, bi))
            stack.append((bi, j))
    return [p for p, k in zip(pts, keep) if k]


def _area(ring):
    s = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % len(ring)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def point_in_ring(x, y, ring):
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i - 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


# ── assembly ─────────────────────────────────────────────────────────────────

# The shapefile's own COUNTYID is the 實價登錄 county letter — verified against
# all 368 records, 22 counties for 22. Deriving the map from the file means a
# national build needs no county list here at all, and a county cannot be
# silently misfiled by a typo in a hand-written table.
def county_key(attrs_row):
    return (attrs_row.get("COUNTYID") or "").strip().lower() or None


# Kept for callers that still want the two-city scope explicitly.
CITY_COUNTY = {"臺北市": "a", "台北市": "a", "新北市": "f"}


# Taiwan proper plus 澎湖, 金門, 馬祖, 蘭嶼 and 綠島, in TWD97/TM2 metres.
#
# The MOI shapefile files 東沙 and 南沙太平島 under 高雄市旗津區, and 釣魚臺列嶼
# under 宜蘭縣頭城鎮. Keeping them makes the national extent 998 x 1,765 km, in
# which Taiwan is a smudge in one corner and 旗津區's own bbox spans 1,700 km --
# so its label anchor, its zoom-to-fit and its centroid are all meaningless.
# Measured extremes that must SURVIVE this box: 金門烈嶼 x=-39,041,
# 屏東恆春 y=2,422,005, 連江東引 y=2,919,171.
POPULATED = (-120000.0, 2400000.0, 400000.0, 2950000.0)


def build(shp_dir, tolerance=45.0, min_ring_area=120000.0, counties=None,
          dissolve=None, clip=POPULATED):
    """Projected, simplified district outlines.

    tolerance is in METRES (post-projection), so it means something physical:
    45 m is well below one screen pixel at the zoom this map opens at, and
    rings smaller than min_ring_area (12 ha) are dropped -- they are offshore
    rocks and river islets that cost bytes and render as specks.

    `counties` is an iterable of 實價登錄 county letters to keep. None keeps ALL
    22, which is what the national build wants. The letters are read off the
    shapefile's own COUNTYID rather than matched against a hand-written table of
    county names -- see county_key().

    `dissolve` is the set of counties whose districts must be FUSED into one
    city-level shape. 嘉義市 and 新竹市 are the cases: 實價登錄 writes 鄉鎮市區 as
    literally 「嘉義市」/「新竹市」 for every row, while this shapefile splits them
    into 2 and 3 polygons (東區/西區, 東區/北區/香山區). Without fusing them the
    district table ranks a key that no outline has, and 164 matched buildings
    cannot be drawn. The caller derives the set from the data rather than hard-
    coding it -- see the call in underwrite.py.
    """
    keep = set(counties) if counties else None
    fuse = set(dissolve or ())
    dropped = []
    base = None
    for f in os.listdir(shp_dir):
        if f.lower().endswith(".shp"):
            base = os.path.join(shp_dir, f[:-4])
            break
    if not base:
        print("[bnd] no .shp found")
        return []
    attrs = read_dbf(base + ".dbf")
    shapes = read_shp_polygons(base + ".shp")
    if len(attrs) != len(shapes):
        print(f"[bnd] attribute/shape mismatch: {len(attrs)} vs {len(shapes)}")
        return []
    city_key = next((k for k in ("COUNTYNAME", "COUNTY", "C_Name") if k in attrs[0]), None)
    town_key = next((k for k in ("TOWNNAME", "TOWN", "T_Name") if k in attrs[0]), None)
    if not city_key or not town_key:
        print(f"[bnd] unexpected dbf fields: {list(attrs[0])[:8]}")
        return []
    out = []
    for a, rings in zip(attrs, shapes):
        county = county_key(a)
        if not county or not rings or (keep is not None and county not in keep):
            continue
        proj = []
        for ring in rings:
            pr = [lonlat_to_tm2(lon, lat) for lon, lat in ring]
            if _area(pr) < min_ring_area:
                continue
            if clip:
                cx = sum(x for x, _ in pr) / len(pr)
                cy = sum(y for _, y in pr) / len(pr)
                if not (clip[0] <= cx <= clip[2] and clip[1] <= cy <= clip[3]):
                    dropped.append((a.get(city_key, ""), a[town_key], int(cx), int(cy)))
                    continue
            s = _rdp(pr, tolerance)
            if len(s) >= 4:
                proj.append([[int(round(x)), int(round(y))] for x, y in s])
        if proj:
            name = a.get(city_key) if county in fuse else a[town_key]
            out.append({"county": county, "district": name, "rings": proj})
    if fuse:
        # Fusing keeps every ring under one key; it is not a geometric union, so
        # the sub-district lines still draw. At the zoom a 2-3 district city is
        # ever seen that is invisible, and a real dissolve would need shared-edge
        # topology the RDP pass has already destroyed.
        merged = {}
        for d in out:
            if d["county"] not in fuse:
                continue
            k = (d["county"], d["district"])
            merged.setdefault(k, []).extend(d["rings"])
        out = [d for d in out if d["county"] not in fuse]
        out += [{"county": c, "district": n, "rings": r} for (c, n), r in merged.items()]
    if dropped:
        # Named, not silent: this is the site's own posture about its data.
        where = ", ".join(sorted({f"{c}{t}" for c, t, _, _ in dropped}))
        print(f"[bnd] clipped {len(dropped)} ring(s) outside the populated "
              f"extent, from: {where}")
    npts = sum(len(r) for d in out for r in d["rings"])
    print(f"[bnd] {len(out)} districts, {npts:,} points after simplification")
    return out


def dissolve_counties(shp_dir, tolerance=250.0, min_ring_area=2_000_000.0,
                      counties=None, clip=POPULATED):
    """One outline per county, computed from the district polygons themselves.

    At national zoom the map wants 臺南市 to be ONE block, not the 37 shapes it
    is made of. That needs a real union, and the shapefile turns out to support
    one exactly: neighbouring districts share their common border VERTEX FOR
    VERTEX. Measured on 臺南市 — 37,396 edges appear exactly twice and 9,823
    exactly once — so an edge used twice is internal and an edge used once is on
    the county outline. Keep the singles, chain them back into rings, and the
    result is the true boundary with no polygon-clipping library involved.

    This runs on the RAW lat/lon rings on purpose. RDP simplification moves
    vertices independently per district, which destroys the shared topology the
    method depends on, so the union has to happen first and be simplified after.

    Tolerance defaults higher than the district layer (250 m): this outline is
    only ever drawn at national zoom, where 250 m is well under a pixel.
    """
    base = None
    for f in sorted(os.listdir(shp_dir)):
        if f.lower().endswith(".shp"):
            base = os.path.join(shp_dir, f[:-4])
            break
    if not base:
        return []
    attrs = read_dbf(base + ".dbf")
    shapes = read_shp_polygons(base + ".shp")
    if len(attrs) != len(shapes):
        return []
    keep = set(counties) if counties else None

    by_county = {}
    for a, rings in zip(attrs, shapes):
        c = county_key(a)
        if not c or (keep is not None and c not in keep):
            continue
        by_county.setdefault(c, []).extend(rings)

    out = []
    for county, rings in by_county.items():
        used = {}
        for ring in rings:
            for i in range(len(ring) - 1):
                p, q = ring[i], ring[i + 1]
                k = (p, q) if p <= q else (q, p)
                used[k] = used.get(k, 0) + 1
        # Only the edges that belong to exactly one district are on the outline.
        adj = {}
        for (p, q), n in used.items():
            if n != 1:
                continue
            adj.setdefault(p, []).append(q)
            adj.setdefault(q, []).append(p)

        seen = set()
        loops = []
        for start in adj:
            if start in seen:
                continue
            loop, cur, prev = [start], start, None
            seen.add(start)
            while True:
                nxt = None
                for cand in adj.get(cur, ()):
                    if cand != prev and (cand not in seen or cand == start):
                        nxt = cand
                        break
                if nxt is None or nxt == start:
                    break
                loop.append(nxt)
                seen.add(nxt)
                prev, cur = cur, nxt
            if len(loop) >= 4:
                loops.append(loop)

        proj = []
        for loop in loops:
            pr = [lonlat_to_tm2(lon, lat) for lon, lat in loop]
            if _area(pr) < min_ring_area:
                continue
            if clip:
                cx = sum(x for x, _ in pr) / len(pr)
                cy = sum(y for _, y in pr) / len(pr)
                if not (clip[0] <= cx <= clip[2] and clip[1] <= cy <= clip[3]):
                    continue
            sm = _rdp(pr, tolerance)
            if len(sm) >= 4:
                proj.append([[int(round(x)), int(round(y))] for x, y in sm])
        if proj:
            out.append({"county": county, "rings": proj})
    npts = sum(len(r) for d in out for r in d["rings"])
    print(f"[bnd] dissolved {len(out)} county outlines, {npts:,} points")
    return out


def validate(districts, buildings):
    """Do buildings land inside the district their own record names?

    This is the projection's only real test. A wrong central meridian, a swapped
    axis or the wrong datum all place points somewhere plausible-looking but in
    the wrong polygon, and nothing else in the pipeline would notice.
    """
    by_key = {(d["county"], d["district"]): d["rings"] for d in districts}
    ok = bad = miss = 0
    for b in buildings:
        if b.get("mx") is None:
            continue
        rings = by_key.get((b["c"], b["d"]))
        if not rings:
            miss += 1
            continue
        if any(point_in_ring(b["mx"], b["my"], r) for r in rings):
            ok += 1
        else:
            bad += 1
    total = ok + bad
    rate = round(ok / total * 100, 2) if total else 0.0
    print(f"[bnd] {ok:,}/{total:,} buildings inside their own district ({rate}%)"
          + (f", {miss} with no polygon" if miss else ""))
    return {"inside": ok, "outside": bad, "no_polygon": miss, "rate": rate}


def centroids(districts):
    """Label anchor per district: centre of its largest ring's bounding box."""
    out = {}
    for d in districts:
        big = max(d["rings"], key=lambda r: _area([(p[0], p[1]) for p in r]))
        xs = [p[0] for p in big]
        ys = [p[1] for p in big]
        out[d["county"] + "|" + d["district"]] = [
            int((min(xs) + max(xs)) / 2), int((min(ys) + max(ys)) / 2)]
    return out


if __name__ == "__main__":
    import sys
    ds = build(sys.argv[1] if len(sys.argv) > 1 else "data/geo/twn")
    for d in ds[:5]:
        print(" ", d["county"], d["district"], sum(len(r) for r in d["rings"]), "pts")
