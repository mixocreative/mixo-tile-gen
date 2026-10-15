"""Puzzle-fit check: sum of colour-body footprint areas vs tile area (overlap -> >, gap -> <),
plus watertightness. Usage: python tests/check_borders.py <tile> [clearance_mm]"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, trimesh, tile_processor as tp
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "real_tiles")
C = json.load(open(os.path.join(D, "corners.json")))
nm = sys.argv[1]; clr = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
f, c = C[nm]; data = open(os.path.join(D, nm + ".jpg"), "rb").read()
rgb, s = tp.decode_image(data); w = rgb.shape[1] / s
if os.environ.get("NODEC"): tp._decimate = lambda v, f, target_faces: (v, f)
cap = []; tp.export_parts = lambda parts, fmt: cap.extend(parts) or b""
cfg = tp.TileConfig(clearance_mm=clr); t = time.time()
tp.process_tile(data, (np.float32(c) * w / 2048).tolist(), None, cfg)
import cv2
z0 = cfg.pad_thickness_mm; S = cfg.tile_size_mm; px = 0.05; N = int(S / px)
cover = np.zeros((N, N), np.uint8); bad = []; perim = 0.0
for name, _, v, fc in cap:
    m = trimesh.Trimesh(v, fc, process=False)
    if not m.is_watertight: bad.append(name)
    if name == "backing_pad": continue
    sec = m.section(plane_origin=[0, 0, z0 + 0.15], plane_normal=[0, 0, 1])   # through vertical walls
    if sec is None: continue
    loops = [np.round(l[:, :2] / px).astype(np.int32) for l in sec.discrete]
    perim += sec.length
    body = np.zeros((N, N), np.uint8); cv2.fillPoly(body, loops, 1)   # even-odd: holes stay empty
    cover += body
r = cfg.corner_radius_mm
inside = np.zeros((N, N), np.uint8)
cv2.rectangle(inside, (int(r/px), 0), (N - int(r/px), N), 1, -1); cv2.rectangle(inside, (0, int(r/px)), (N, N - int(r/px)), 1, -1)
for cx in (r, S - r):
    for cy in (r, S - r): cv2.circle(inside, (int(cx/px), int(cy/px)), int(r/px), 1, -1)
core = cv2.erode(inside, np.ones((9, 9), np.uint8)).astype(bool)          # ignore the outer-edge rim pixels
k3 = np.ones((3, 3), np.uint8)   # a gap/overlap wider than 0.15 mm (3 px) survives a 3x3 erosion; 1-px fill-rounding hairlines don't
raw_gap = ((cover == 0) & core).sum() * px * px
gap_px = int(cv2.erode(((cover == 0) & core).astype(np.uint8), k3).sum())
over_px = int(cv2.erode(((cover >= 2) & core).astype(np.uint8), k3).sum())
gap = gap_px; over = over_px
if os.environ.get("GAPWHERE"):
    g = (cover == 0) & core; dist = cv2.distanceTransform(inside, cv2.DIST_L2, 5) * px
    ys, xs = np.nonzero(g); dd = dist[ys, xs]
    print("gap px:", len(ys), "dist-to-tile-edge mm percentiles 5/50/95:", np.percentile(dd, [5, 50, 95]).round(2) if len(dd) else None)
    vis = cv2.cvtColor((np.clip(cover, 0, 2) * 100).astype(np.uint8), cv2.COLOR_GRAY2BGR); vis[g] = (0, 0, 255)
    cv2.imwrite(os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", f"gapmap_{nm}.png"), cv2.resize(vis, (1500, 1500), interpolation=cv2.INTER_AREA))
    big = cv2.connectedComponentsWithStats(g.astype(np.uint8))[2][1:, 4]; print("gap blobs:", len(big), "largest px:", sorted(big)[-5:])
print(f"{nm} clearance={clr}: gap wider than 0.15 mm: {gap} px (raw incl. 1-px hairlines {raw_gap:.1f}), overlap wider than 0.15 mm: {over} px, "
      f"expected gap ≈ {clr*perim/2:.1f} mm² (total wall length {perim:.0f} mm), watertight={'ALL' if not bad else bad}, {time.time()-t:.0f}s")
