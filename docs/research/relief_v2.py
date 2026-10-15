"""Drop-in replacement for inflate_regions / the profile part of cushion_body_mesh.

Height field ("extrude everything to the shared top, then carve the edges down into the seams"):

    d  = smooth seam distance (mm): Varadhan / screened-Poisson distance,
         L²∇²ψ − ψ = −1 inside every colour patch, ψ = 0 on colour seams (and the tile edge),
         d = −L·ln(1 − ψ).  Exactly 0 on seams, slope 1 at seams, medial-axis creases rounded over ~L.
    T  = z0 + floor + [ D1·f(d / W) + D2·(1 − exp(−d / W2)) ] · pin(d_fine / shoulder)

    f(t) = 1 − (1 − t)³·(1 + a·t),  a = 3 − s0        edge round-over: f(0)=0, f'(0)=s0, f(1)=1, f'(1)=f''(1)=0 (C²)
    D1 = total − D2                                  edge band depth; W = band width (mm)
    D2·(1 − e^{−d/W2})                               gentle plateau crown: slope D2/W2·e^{−d/W2}, flatter the bigger the patch
    pin                                              0.8 mm ease at every seam (exact groove floor, rounds the valley bottom)

Only numpy / scipy / opencv are used.
"""
from __future__ import annotations

import math
import numpy as np
import cv2


# ----------------------------------------------------------------------------- raster solve
def seam_field(labels: np.ndarray, mm_per_px: float, L_mm: float = 1.0,
               edge_is_seam: bool = True) -> np.ndarray:
    """ψ in [0, 1) on the colour raster: screened-Poisson field L²∇²ψ − ψ = −1 inside every colour
    patch with ψ = 0 on every colour seam (and on the tile edge when edge_is_seam). One sparse solve
    for the whole tile (same matrix structure as the old Poisson membrane). d = −L·ln(1 − ψ) is a
    smooth distance-to-seam: exact 0 and unit slope at the seams, creases rounded over ~L."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import spsolve

    H, W = labels.shape
    if edge_is_seam:
        lab = np.pad(labels, 1, constant_values=-1)
    else:
        lab = np.pad(labels, 1, mode="edge")                      # Neumann-ish: edge pixel mirrors itself
    c = lab[1:-1, 1:-1]
    nbr = [lab[:-2, 1:-1] == c, lab[2:, 1:-1] == c, lab[1:-1, :-2] == c, lab[1:-1, 2:] == c]
    interior = nbr[0] & nbr[1] & nbr[2] & nbr[3]
    idx = -np.ones((H, W), np.int64)
    n = int(interior.sum())
    psi = np.zeros((H, W), np.float32)
    if n == 0:
        return psi
    idx[interior] = np.arange(n)
    ys, xs = np.nonzero(interior)
    a = (L_mm / mm_per_px) ** 2                                   # L² in px²
    rows, cols, vals = [np.arange(n)], [np.arange(n)], [np.full(n, 4 * a + 1.0)]
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        yy, xx = np.clip(ys + dy, 0, H - 1), np.clip(xs + dx, 0, W - 1)
        nb = idx[yy, xx]
        if not edge_is_seam:                                      # mirror at the tile edge
            off = ((ys + dy) < 0) | ((ys + dy) >= H) | ((xs + dx) < 0) | ((xs + dx) >= W)
            nb = np.where(off, np.arange(n), nb)
        ok = nb >= 0
        rows.append(np.arange(n)[ok]); cols.append(nb[ok]); vals.append(np.full(ok.sum(), -a))
    A = coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsc()
    sol = spsolve(A, np.ones(n))
    psi[interior] = np.clip(sol, 0, 1 - 1e-7)
    return psi


# ----------------------------------------------------------------------------- fine-grid refine
def refine_seam_field(psi_raster: np.ndarray, mask_fine: np.ndarray, L_mm: float, h_mm: float,
                      sweeps: int = 40) -> np.ndarray:
    """Resample ψ onto the fine mesh grid and relax it there (Jacobi) against the fine, smooth
    patch mask. The raster solution already has the right large-scale shape; the sweeps only
    repair the boundary layer, i.e. the 1/3 mm staircase of the colour raster that otherwise
    gets baked into every seam. ψ = 0 outside mask_fine."""
    psi = cv2.resize(psi_raster.astype(np.float32), (mask_fine.shape[1], mask_fine.shape[0]),
                     interpolation=cv2.INTER_CUBIC)
    m = mask_fine.astype(np.float32)
    psi = np.clip(psi, 0, 1) * m
    a = (L_mm / h_mm) ** 2
    ker = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]], np.float32)
    for _ in range(sweeps):
        nb = cv2.filter2D(psi, -1, ker, borderType=cv2.BORDER_CONSTANT)
        psi = (a * nb + 1.0) / (4 * a + 1.0) * m
    return psi


def seam_distance(psi: np.ndarray, L_mm: float) -> np.ndarray:
    return (-L_mm * np.log1p(-np.clip(psi, 0, 1 - 1e-7))).astype(np.float32)


# ----------------------------------------------------------------------------- profile
def edge_roundover(t: np.ndarray, s0: float = 1.5) -> np.ndarray:
    """0 at the seam, 1 on the plateau; start slope s0 (normalised), C² where it meets the plateau."""
    t = np.clip(t, 0, 1)
    return 1 - (1 - t) ** 3 * (1 + (3 - s0) * t)


def cushion_profile(d: np.ndarray, total: float, band_w: float = 10.0, seam_slope: float = 1.5,
                    crown_h: float = 2.0, crown_w: float = 20.0) -> np.ndarray:
    """Height above the groove floor from the smooth seam distance d (mm).
    total = max height above the floor (every big patch tops out here)."""
    crown_h = min(crown_h, total)
    d1 = total - crown_h
    return d1 * edge_roundover(d / band_w, seam_slope) + crown_h * (1 - np.exp(-d / crown_w))


# ----------------------------------------------------------------------------- body mesh (v2)
def cushion_body_mesh_v2(own, grow, size, z0, floor, total, shoulder, corner_r, grid_mm,
                         psi_raster, L_mm=1.0, band_w=10.0, seam_slope=1.5, crown_h=2.0, crown_w=20.0,
                         sweeps=40, edge_is_seam=True, edge_band_w=6.0, edge_drop=0.5,
                         return_field=False):
    """Same contract as tile_processor.cushion_body_mesh, with the new profile.
    psi_raster = seam_field(labels, ...).  When edge_is_seam is False the tile edge is not a
    groove: the cushion runs to the edge and only rolls off by `edge_drop`·total over edge_band_w."""
    from tile_processor import _fine_grid_sdf, _rounded_square_sdf, _orient_outward

    n = int(round(size / grid_mm))
    h = size / n
    margin = int(math.ceil(1.0 / h)) + 3
    big, d_grow = _fine_grid_sdf(grow, size, n, margin)
    rows, cols = np.nonzero(big)
    if len(rows) == 0:
        return None
    r0, r1 = max(rows.min() - margin, 0), min(rows.max() + margin + 1, big.shape[0])
    c0, c1 = max(cols.min() - margin, 0), min(cols.max() + margin + 1, big.shape[1])
    _, d_own = _fine_grid_sdf(own, size, n, margin)
    d_own, d_grow = d_own[r0:r1, c0:c1], d_grow[r0:r1, c0:c1]

    xs = (np.arange(c0, c1) - margin + 0.5) * h
    ys_img = (np.arange(r0, r1) - margin + 0.5) * h
    d_tile = _rounded_square_sdf(xs[None, :], ys_img[:, None], size, corner_r)
    lateral = np.maximum(d_grow, d_tile)

    inside = d_own < 0
    if edge_is_seam:
        inside &= d_tile < 0
        d_fine = np.maximum(np.minimum(-d_own, -d_tile), 0).astype(np.float32)
    else:
        d_fine = np.maximum(-d_own, 0).astype(np.float32)
    pin = 1 - (1 - np.clip(d_fine / shoulder, 0, 1)) ** 2

    psi = np.pad(cv2.resize(psi_raster, (n, n), interpolation=cv2.INTER_CUBIC), margin)[r0:r1, c0:c1]
    psi = refine_seam_field(psi, inside, L_mm, h, sweeps) if sweeps > 0 else np.clip(psi, 0, 1) * inside
    d = seam_distance(psi, L_mm)
    prof = cushion_profile(d, total, band_w, seam_slope, crown_h, crown_w)
    if not edge_is_seam:
        te = edge_roundover(np.clip(-d_tile, 0, None) / edge_band_w, 1.5)
        prof = prof * ((1 - edge_drop) + edge_drop * te)
    top = (z0 + floor + prof * pin).astype(np.float32)
    if return_field:
        return top, (r0, r1, c0, c1, margin, h)

    from skimage.measure import marching_cubes
    eps = min(0.02, floor / 4)
    lo = max(z0 + 2 * eps, z0 + floor - 0.1)
    band = np.arange(lo, float(top.max()), max(0.2, total / 24))
    zs = np.concatenate([[z0 - eps, z0 + eps], band, [float(top.max()) + 0.1]]).astype(np.float32)
    sdf = np.maximum(zs[None, None, :] - top[:, :, None], (z0 - zs)[None, None, :])
    sdf = np.maximum(sdf, lateral.astype(np.float32)[:, :, None])
    if sdf.min() >= 0:
        return None
    verts, faces, _, _ = marching_cubes(sdf, 0.0, allow_degenerate=False)
    v = np.empty_like(verts, dtype=np.float64)
    v[:, 0] = (c0 + verts[:, 1] - margin + 0.5) * h
    v[:, 1] = size - (r0 + verts[:, 0] - margin + 0.5) * h
    v[:, 2] = np.interp(verts[:, 2], np.arange(len(zs)), zs)
    f = _orient_outward(v, faces.astype(np.int64))
    return v, f
