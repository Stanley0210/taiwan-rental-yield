#!/usr/bin/env bash
# Rebuild housing_data.json from the government registry, and say whether the
# result matches the published one byte for byte.
#
#   bin/rebuild-housing.sh            rebuild, then verify against the sidecar
#   bin/rebuild-housing.sh --verify   verify only, no rebuild
#
# 實價登錄 gains a season every quarter and the site's numbers move with it, so
# "I got a different answer" is only informative once the inputs are pinned.
# The source hash printed here is the pin (the season zips), and from v1.9 the
# refs hash beside it pins every reference CSV under data/ref/; docs/REPRODUCING.md
# explains what a mismatch on each line means.
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PY:-venv/bin/python3}"
[ -x "$PY" ] || PY=python3
OUT="${LVR_OUT:-housing_data.json}"

sha() { shasum -a 256 "$1" 2>/dev/null | awk '{print $1}' \
        || sha256sum "$1" | awk '{print $1}'; }

# The build rewrites the sidecar, so "compare the rebuilt file with its own
# sidecar" can never fail. The published hash is the one in git; hold on to it
# before building. (--verify has no build step and reads the sidecar as is.)
if [ "${1:-}" != "--verify" ]; then
  want=$(git show HEAD:"$OUT.sha256" 2>/dev/null | awk '{print $1}')
  [ -n "$want" ] || want=$(awk '{print $1}' < "$OUT.sha256" 2>/dev/null)
  keep="$(mktemp)"; cp "$OUT" "$keep" 2>/dev/null || true
  echo "==> rebuilding $OUT  (downloads ~200 MB of season zips on a cold cache)"
  "$PY" src/underwrite.py
else
  [ -f "$OUT.sha256" ] || { echo "!! $OUT.sha256 missing"; exit 1; }
  want=$(awk '{print $1}' < "$OUT.sha256")
  keep=""
fi

[ -f "$OUT" ] || { echo "!! $OUT missing -- run without --verify first"; exit 1; }
got=$(sha "$OUT")

echo
echo "    published  $want"
echo "    rebuilt    $got"
if [ "$want" = "$got" ]; then
  echo "==> MATCH -- byte-identical to the published payload"
  exit 0
fi

echo "==> MISMATCH"
echo
"$PY" - "$OUT" "$keep" <<'PYEOF'
import json, os, sys
cur = json.load(open(sys.argv[1], encoding="utf-8"))
m = cur["meta"]
pv = m.get("provenance") or {}
src = pv.get("source") or {}
refs = pv.get("refs") or {}
print(f"    version {pv.get('version')}  built {pv.get('built')}  commit {pv.get('commit')}")
print(f"    source snapshot {src.get('sha256')}")
print(f"    refs snapshot   {refs.get('sha256')}")
print(f"    window {m['seasons'][0]}..{m['seasons'][1]} ({m['n_seasons']} seasons)")
missing = [f["season"] for f in src.get("files", []) if not f.get("sha256")]
if missing:
    print(f"    !! seasons absent from the cache: {', '.join(missing)}")
for r in refs.get("files", []):
    print(f"    ref {r['path']:36s} {r['sha256'][:12]}  fetched {r.get('fetched', '-')}")
absent = [r["path"] for r in refs.get("files", []) if not os.path.exists(r["path"])]
if absent:
    print(f"    !! reference files missing: {', '.join(absent)}")

# Was the previous payload kept? Then say exactly what moved. The build date
# and commit stamp change on every rebuild by construction, so a diff that is
# ONLY those two is a reproduction, not a mismatch.
keep = sys.argv[2] if len(sys.argv) > 2 else ""
if keep and os.path.exists(keep) and os.path.getsize(keep) > 0:
    old = json.load(open(keep, encoding="utf-8"))
    def walk(a, b, path, out):
        if type(a) != type(b):
            out.append(path); return
        if isinstance(a, dict):
            for k in sorted(set(a) | set(b)):
                if k not in a or k not in b: out.append(f"{path}/{k}")
                else: walk(a[k], b[k], f"{path}/{k}", out)
        elif isinstance(a, list):
            if len(a) != len(b): out.append(path)
            else:
                for i, (x, y) in enumerate(zip(a, b)):
                    walk(x, y, f"{path}[{i}]", out)
                    if len(out) > 200: return
        elif a != b:
            out.append(path)
    changed = []
    walk(old, cur, "", changed)
    stamp_only = {"/meta/provenance/built", "/meta/provenance/commit"}
    print()
    if set(changed) <= stamp_only:
        print("    Only the build date and commit stamp differ. Every number is the")
        print("    same: this IS a reproduction. (Those two fields cannot be pinned --")
        print("    see docs/REPRODUCING.md.)")
        sys.exit(0)
    import re
    # collapse array indices: 9,805 buildings[i]/mf lines are one fact
    shapes = sorted({re.sub(r"\[\d+\]", "[*]", c) for c in changed})
    print(f"    {len(changed)} paths differ from the previous payload ({len(shapes)} distinct shapes):")
    for c in shapes[:20]:
        print(f"      {c}")
    if len(shapes) > 20:
        print(f"      ... and {len(shapes) - 20} more")
print()
print("    Compare `source snapshot` with the published one first. If it differs,")
print("    the inputs differ (a newer season, or a partial download) and the")
print("    numbers are expected to move. If `refs snapshot` differs, an official")
print("    series was re-exported. If BOTH match and the payload hash does not,")
print("    the code changed -- that is the case worth reporting.")
PYEOF
rc=$?
[ -n "$keep" ] && rm -f "$keep"
exit $rc
