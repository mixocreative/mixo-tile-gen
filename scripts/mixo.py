"""mixo: make tile reliefs from the command line (no web page).

  Local (pure Python on this computer, no AI, no internet needed after the first setup):
    python scripts/mixo.py photo.jpg --corners "510,564 2616,534 2514,2508 594,2478"
    python scripts/mixo.py photo.jpg --corners ... --format objtex --out roses.obj.zip

  Online (send the photo to an engine, e.g. the live one):
    python scripts/mixo.py photo.jpg --corners ... --server https://mixo-tile-gen-616971929665.asia-east1.run.app

  Many photos at once, corners from a JSON file {"photo-name-without-.jpg": [[x,y] TL,TR,BR,BL], ...}:
    python scripts/mixo.py a.jpg b.jpg --corners-json corners.json --format 3mftex

Corners are the tile's four glaze corners in the photo's own pixels (top-left, top-right,
bottom-right, bottom-left; any order works). Without corners the centred square of the photo
is used. Change any setting with --set name=value (names as in the README, e.g. tile_size_mm=100).

Formats: 3mf (default, prints in glaze colours) | 3mftex (same + the photo as a texture for viewers)
         glb | glbtex | stl (zip, one STL per colour) | obj (zip, colours) | objtex (zip, photo texture)
         bundle (one zip with all of the above; pick some with --set formats=3mf,objtex)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXT = {"3mf": "3mf", "3mftex": "textured.3mf", "glb": "glb", "glbtex": "textured.glb",
       "stl": "stl.zip", "obj": "obj.zip", "objtex": "textured.obj.zip", "bundle": "all.zip"}


def parse_corners(text: str):
    pts = [[float(v) for v in p.split(",")] for p in text.replace(";", " ").split()]
    if len(pts) != 4 or any(len(p) != 2 for p in pts):
        raise SystemExit('--corners needs four "x,y" pairs, e.g. "510,564 2616,534 2514,2508 594,2478"')
    return pts


def parse_sets(items):
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        if not _:
            raise SystemExit(f"--set expects name=value, got {it!r}")
        out[k.strip()] = v.strip()
    return out


def run_local(photo: Path, corners, fmt: str, sets: dict) -> bytes:
    sys.path.insert(0, str(ROOT / "backend"))
    import dataclasses
    import tile_processor as tp

    fields = {f.name: f.type for f in dataclasses.fields(tp.TileConfig)}
    kw = {"output_format": fmt}
    for k, v in sets.items():
        if k not in fields:
            raise SystemExit(f"unknown setting {k!r}. Known: {', '.join(sorted(fields))}")
        cur = getattr(tp.TileConfig(), k)
        kw[k] = (v.lower() in ("1", "true", "yes", "on")) if isinstance(cur, bool) else type(cur)(v)

    def progress(p, msg):
        print(f"\r  {int(p * 100):3d}%  {msg:<40}", end="", flush=True)

    data, stats = tp.process_tile(photo.read_bytes(), corners, None, tp.TileConfig(**kw), progress=progress)
    print(f"\r  100%  done: {stats['bodies']} colour bodies, {stats.get('triangles', 0):,} triangles".ljust(60))
    return data


def run_online(server: str, photo: Path, corners, fmt: str, sets: dict) -> bytes:
    fields = {"output_format": fmt, **sets}
    if corners:
        fields["corners"] = json.dumps(corners)
    boundary = uuid.uuid4().hex
    body = bytearray()
    for k, v in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{photo.name}"\r\n'
             "Content-Type: image/jpeg\r\n\r\n").encode() + photo.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(server.rstrip("/") + "/process-tile", data=bytes(body), method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    print("  sending to the engine (a sleeping engine takes up to a minute to wake) ...", flush=True)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"engine error {e.code}: {e.read().decode(errors='replace')[:300]}")


def ensure_local_env() -> None:
    """Local mode needs the engine's packages: re-run inside the app's private .venv (created on first use)."""
    try:
        import cv2, skimage, sklearn, scipy, trimesh, fast_simplification  # noqa: F401
        return
    except ImportError:
        pass
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from run_local import ensure_env
    py = ensure_env()
    if Path(sys.executable).resolve() != Path(py).resolve():
        raise SystemExit(subprocess.call([str(py), __file__, *sys.argv[1:]]))


def main() -> None:
    ap = argparse.ArgumentParser(prog="mixo", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photos", nargs="+", type=Path)
    ap.add_argument("--corners", help='four "x,y" glaze corners in photo pixels (single photo)')
    ap.add_argument("--corners-json", type=Path, help="JSON file {photo-name: [[x,y]x4]} for several photos")
    ap.add_argument("--format", default="3mf", choices=sorted(EXT))
    ap.add_argument("--out", type=Path, help="output file (single photo) or folder (several photos)")
    ap.add_argument("--server", help="engine address to use instead of this computer, e.g. https://….run.app")
    ap.add_argument("--set", action="append", metavar="NAME=VALUE", help="change a setting, e.g. tile_size_mm=100")
    a = ap.parse_args()

    if not a.server:
        ensure_local_env()
    sets = parse_sets(a.set)
    table = json.loads(a.corners_json.read_text(encoding="utf-8")) if a.corners_json else {}
    if a.corners and len(a.photos) > 1:
        raise SystemExit("--corners is for one photo; use --corners-json for several")
    for photo in a.photos:
        if not photo.exists():
            raise SystemExit(f"no such photo: {photo}")
        corners = parse_corners(a.corners) if a.corners else table.get(photo.stem)
        if corners is None:
            print(f"! {photo.name}: no corners given, using the centred square of the photo")
        if a.out and len(a.photos) == 1 and a.out.suffix:
            out = a.out
        else:
            out = (a.out or photo.parent) / f"{photo.stem}.{EXT[a.format]}"
        out.parent.mkdir(parents=True, exist_ok=True)
        print(f"{photo.name} -> {out}  ({'engine ' + a.server if a.server else 'this computer'})")
        t = time.time()
        data = run_online(a.server, photo, corners, a.format, sets) if a.server else run_local(photo, corners, a.format, sets)
        out.write_bytes(data)
        print(f"  saved {len(data) / 1e6:.1f} MB in {time.time() - t:.1f} s")


if __name__ == "__main__":
    main()
