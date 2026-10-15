"""Live preview sliders: how close are the browser's recomputed heights to a real rebuild?

    python tests/check_live_heights.py [IMG_9255]

1. At the current settings the coefficient formula must reproduce the preview mesh heights.
2. With changed settings (base, relief, crown, outline), the predicted top heights are compared
   with the exact top heights of a real rebuild at the same x, y.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import tile_processor as tp

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "real_tiles")
name = sys.argv[1] if len(sys.argv) > 1 else "IMG_9255"
corners = json.load(open(os.path.join(D, "corners.json"), encoding="utf-8"))[name]
img = open(os.path.join(D, "originals", name + ".jpg"), "rb").read()


def run(cfg):
    got = {}
    def on_parts(parts, stats, tex):
        layout, blob, hb = tp.preview_mesh(parts, heights=stats["_heights"])
        got.update(layout=layout, blob=blob, hb=hb, H=stats["_heights"])
    tp.process_tile(img, corners, None, cfg, on_parts=on_parts)
    return got


def predict(got, pad, floor, relief, crown, outline):
    off, hoff, zs, xy, body = 0, 0, [], [], []
    a_all = np.frombuffer(got["hb"], "<f4").reshape(-1, 5)
    for part in got["layout"]:
        v = np.frombuffer(got["blob"], "<f4", part["nv"] * 3, off).reshape(-1, 3); off += part["nv"] * 12 + part["nt"] * 12
        a = a_all[hoff:hoff + part["nv"]]; hoff += part["nv"]
        if "pad" in part["name"]:
            z = a[:, 0] * pad
        else:
            z = pad + a[:, 0] * (floor + relief * a[:, 1] + crown * a[:, 2] + outline * a[:, 3] + a[:, 4])
        zs.append(z); xy.append(v); body.append(np.full(len(v), "pad" not in part["name"]))
    return np.concatenate(zs), np.concatenate(xy), np.concatenate(body)


base = tp.TileConfig()
g0 = run(base)
z, v, body = predict(g0, base.pad_thickness_mm, base.groove_floor_mm, base.relief_height_mm,
                     base.dome_height_mm, base.outline_height_mm)
err0 = np.abs(z - v[:, 2])
print(f"1. same settings: vertex height error  median {np.median(err0):.3f} mm  95% {np.percentile(err0, 95):.3f}  max {err0.max():.3f}")

new = dict(pad_thickness_mm=10.0, relief_height_mm=4.5, dome_height_mm=2.5, outline_height_mm=1.6)
g1 = run(tp.TileConfig(**new))
zp, v, body = predict(g0, 10.0, base.groove_floor_mm, 4.5, 2.5, 1.6)
H = g1["H"]; h, m, size = H["h"], H["margin"], H["size"]
col = np.clip(np.round(v[:, 0] / h + m - 0.5).astype(int), 0, H["top"].shape[1] - 1)
row = np.clip(np.round((size - v[:, 1]) / h + m - 0.5).astype(int), 0, H["top"].shape[0] - 1)
a_all = np.frombuffer(g0["hb"], "<f4").reshape(-1, 5)
on_top = body & (a_all[:, 0] > 0.999)                 # vertices on a body's top surface
err1 = np.abs(zp[on_top] - H["top"][row, col][on_top])
print(f"2. changed settings {new}:")
print(f"   top-surface error vs real rebuild  median {np.median(err1):.3f} mm  95% {np.percentile(err1, 95):.3f}  max {err1.max():.3f}"
      f"  (heights range {H['top'].min():.1f}-{H['top'].max():.1f} mm)")
ok = np.percentile(err0, 95) < 0.15 and np.percentile(err1, 95) < 0.5     # preview-grade: < 0.5 mm
print("OK" if ok else "CHECK")
