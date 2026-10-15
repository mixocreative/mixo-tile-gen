"""Photo | label map for the real tiles with the current colour pipeline (no meshing). Writes tests/out/user/labels_*.jpg"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, numpy as np, tile_processor as tp
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "real_tiles")
C = json.load(open(os.path.join(D, "corners.json")))
names = sys.argv[1:] or list(C)
cfg = tp.TileConfig().validate(); n_px = int(round(cfg.tile_size_mm * cfg.px_per_mm)); mmpp = cfg.tile_size_mm / n_px
rows = []
for nm in names:
    t = time.time(); f, c = C[nm]
    rgb, s = tp.decode_image(open(os.path.join(D, nm + ".jpg"), "rb").read())
    flat = tp.warp_tile(rgb, np.float32(c) * (rgb.shape[1] / s) / 2048, n_px, s, inset=0.015)
    g, gp = (tp.remove_glare(flat, mmpp) if os.environ.get("GLARE") else (flat, 0))
    lab, pal, m = tp.quantize_auto(g, k_cap=cfg.num_colors)
    lab = tp.majority_filter(lab, len(pal), int(round(cfg.smoothing_mm / mmpp)))
    lab = tp.remove_specks(lab, len(pal), int(cfg.min_feature_mm2 / mmpp ** 2), 4 / mmpp, pal, 25.0, int(1 / mmpp ** 2))
    if not os.environ.get("NOABSORB"): lab, ab = tp.absorb_glare_islands(lab, pal, mmpp)
    else: ab = 0
    print(f"absorbed={ab} {nm:22s} k={len(pal)} glare_px={gp} {time.time()-t:.1f}s")
    a = cv2.resize(cv2.cvtColor(flat, cv2.COLOR_RGB2BGR), (300, 300)); b = cv2.resize(cv2.cvtColor(pal[lab], cv2.COLOR_RGB2BGR), (300, 300), interpolation=cv2.INTER_NEAREST)
    row = np.hstack([a, b]); cv2.putText(row, f"{nm} k={len(pal)}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3); cv2.putText(row, f"{nm} k={len(pal)}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    rows.append(row)
while len(rows) % 4: rows.append(np.full_like(rows[0], 255))
cv2.imwrite(os.path.join(os.path.dirname(D), "..", "out", os.environ.get("OUT", "labels_all.jpg")), np.vstack([np.hstack(rows[i:i+4]) for i in range(0, len(rows), 4)]), [cv2.IMWRITE_JPEG_QUALITY, 88])
