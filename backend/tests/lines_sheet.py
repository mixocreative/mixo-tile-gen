"""Outline-detection verification sheet over the 16 real tiles:
photo | detected outline centre-lines (magenta) | final label map | hillshade of the actual top surface.
Writes docs/research/lines_final.jpg and prints per-tile timings. Run: python tests/lines_sheet.py [names...]"""
import json, math, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, cv2
import tile_processor as tp

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "fixtures", "real_tiles")      # permanent fixture set (never edit)
OUT = os.path.join(os.path.dirname(os.path.dirname(HERE)), "docs", "research")
os.makedirs(OUT, exist_ok=True)
C = json.load(open(os.path.join(D, "corners.json")))
cfg = tp.TileConfig()
cfg.validate()
n_px = int(round(cfg.tile_size_mm * cfg.px_per_mm))
mm_per_px = cfg.tile_size_mm / n_px


def top_surface(labels, palette, cfg, ridge_dist, grid=0.25):
    """Composite height map (max over colour bodies) using the real cushion_body_mesh profile code
    path, at a coarser grid for speed (marching cubes is skipped by catching the early-return)."""
    size = cfg.tile_size_mm
    n = int(round(size / grid)); margin = int(math.ceil(1.0 / (size / n))) + 3
    psi = tp.seam_field(labels, mm_per_px, 1.0, edge_is_seam=cfg.edge_is_seam)
    tile = np.full((n + 2 * margin,) * 2, cfg.pad_thickness_mm + cfg.groove_floor_mm, np.float32)
    phis = tp.partition_fields(labels, size, n, margin, cfg.edge_is_seam)
    band = np.full(labels.shape, cfg.fillet_radius_mm, np.float32)
    for ci in range(len(palette)):
        own = (labels == ci).astype(np.uint8)
        if not own.any():
            continue
        top, (r0, r1, c0, c1) = tp.cushion_body_mesh(phis[ci], size, cfg.pad_thickness_mm,
                                                     cfg.groove_floor_mm, cfg.relief_height_mm + cfg.dome_height_mm,
                                                     cfg.corner_radius_mm, grid, psi, band_w=band, crown_h=cfg.dome_height_mm,
                                                     crown_w=cfg.dome_reach_mm, bead_h=cfg.bead_height_mm, bead_r=cfg.bead_width_mm,
                                                     edge_is_seam=cfg.edge_is_seam, ridge_dist=ridge_dist,
                                                     line_h=cfg.outline_height_mm, line_w=cfg.outline_width_mm, return_top=True,
                                                     clearance=cfg.clearance_mm)
        tile[r0:r1, c0:c1] = np.maximum(tile[r0:r1, c0:c1], top)
    return tile[margin:margin + n, margin:margin + n]


def hillshade(z, grid):
    gy, gx = np.gradient(z, grid)
    nz = 1 / np.sqrt(gx ** 2 + gy ** 2 + 1)
    lx, ly, lz = -0.5, -0.5, 0.707
    s = np.clip((-gx * nz) * lx + (-gy * nz) * ly + nz * lz, 0, 1)
    img = (40 + 215 * s ** 0.8).astype(np.uint8)
    return cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)


rows = []
names = sys.argv[1:] or sorted(k for k in C)
for nm in names:
    img = open(os.path.join(D, nm + ".jpg"), "rb").read()
    rgb, cs = tp.decode_image(img)
    w = rgb.shape[1] / cs
    corners = (np.float32(C[nm][1]) * w / 2048).tolist()
    flat = tp.warp_tile(rgb, corners, n_px, cs, inset=0.015)
    t0 = time.time()
    labels, palette, _ = tp.quantize_auto(flat, k_cap=cfg.num_colors, shade_de=cfg.merge_delta_e)
    n = len(palette)
    labels = tp.majority_filter(labels, n, int(round(cfg.smoothing_mm / mm_per_px)))
    labels = tp.remove_specks(labels, n, int(cfg.min_feature_mm2 / mm_per_px ** 2), keep_len_px=4.0 / mm_per_px,
                              palette=palette, keep_de=25.0, keep_min_px=int(1.0 / mm_per_px ** 2))
    t1 = time.time()
    ridge, comps = tp.detect_outlines(flat, mm_per_px)
    t2 = time.time()
    labels, snapped = tp.snap_outline_colours(labels, palette, flat, comps)
    t3 = time.time()
    z = top_surface(labels, palette, cfg, ridge)
    t4 = time.time()
    centre = ridge < 0.5 * mm_per_px + 1e-3
    ov = flat.copy(); ov[centre] = (255, 0, 255)
    lab_img = palette[labels]
    hs = cv2.resize(hillshade(z, 0.25), (n_px, n_px), interpolation=cv2.INTER_AREA)
    comp_len = sum(int(c[1].sum()) for c in comps) * mm_per_px
    print(f"{nm:22s} colours={n} outlines={len(comps):3d} total={comp_len:6.0f} mm snapped={snapped:2d} "
          f"detect={t2-t1:.2f}s snap={t3-t2:.2f}s (colour step {t1-t0:.2f}s, height map {t4-t3:.1f}s)")
    row = np.hstack([cv2.copyMakeBorder(x, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for x in (flat, ov, lab_img, hs)])
    cv2.putText(row, f"{nm}: photo | outlines ({len(comps)}, snapped {snapped}) | labels k={n} | top surface", (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 4)
    cv2.putText(row, f"{nm}: photo | outlines ({len(comps)}, snapped {snapped}) | labels k={n} | top surface", (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 1)
    rows.append(row)
sheet = np.vstack(rows)
out = os.path.join(OUT, "lines_final.jpg" if len(names) > 1 else f"lines_{names[0]}.jpg")
cv2.imwrite(out, cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
print("wrote", out)
