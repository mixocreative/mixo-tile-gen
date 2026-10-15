"""
MixoTile tile processor.

Photo of a Taiwanese majolica tile  ->  flattened square  ->  colour regions  ->
watertight multi-body relief (backing pad + one body per colour)  ->  .3MF / .GLB

Geometry strategy ("glaze cushions"):
  * One solid backing pad, z = 0 .. pad (a rounded-corner slab built directly as a mesh).
  * Every colour is ONE body on the pad, and every colour is treated the same — no colour is
    assumed to be the background. Each region swells like a glaze cushion: its height grows
    with the distance to its nearest border (colour seam or tile edge), via a rounded shoulder
    up to a plateau. So the seams between colours are always the lowest points (grooves), and
    narrow features become soft domes.
  * Bodies are meshed from a height field with marching cubes, so the rounding is part of the
    shape itself and can't fail on tight corners the way a B-rep fillet does.
  * Each body's footprint is grown ~0.5 mm into its neighbours at groove-floor height, tucking
    under the neighbouring cushion: hidden overlap, never an air gap down to the pad.
"""

from __future__ import annotations

import functools
import io
import os
from concurrent.futures import ThreadPoolExecutor
import logging
import math
import time
import zipfile
from dataclasses import asdict, dataclass

import cv2
import numpy as np
from sklearn.cluster import KMeans

log = logging.getLogger("mixotile.processor")

MAX_INPUT_SIDE = 2400        # px, longer side of the decoded upload is capped to this
MAX_RASTER_SIDE = 900        # px, working raster of the flattened tile (colour analysis)
MAX_MESH_CELLS = 940         # max grid cells along the tile side: 150 mm / 0.16 mm; finer OOMs a 2 GiB Cloud Run instance
MAX_COLORS = 12
FACES_PER_MM = int(os.environ.get("MIXOTILE_FACES_PER_MM", 120))   # decimation budget per mm of outline
MAX_FACES_PER_BODY = 400_000
Z_STEP_MM = float(os.environ.get("MIXOTILE_Z_STEP_MM", 0.6))       # marching-cubes level spacing above the floor
BODY_WORKERS = int(os.environ.get("MIXOTILE_BODY_WORKERS", 1))     # measured: 2 threads are slower (memory-bound)


# --------------------------------------------------------------------------- config
@dataclass
class TileConfig:
    tile_size_mm: float = 150.0
    pad_thickness_mm: float = 15.0   # solid ceramic-like base slab (owner default); relief sits on top
    relief_height_mm: float = 3.0    # edge depth: how far each colour rolls down from its top to the seam
    fillet_radius_mm: float = 6.0    # edge-roll width: seam -> full height (wider = softer valley)
    dome_height_mm: float = 1.0      # gentle crown on top of each patch (leveler on bigger patches)
    dome_reach_mm: float = 12.0      # crown length scale: crown slope ∝ e^(−d/reach), so big fields are near level
    groove_floor_mm: float = 0.4     # material left under the seams between colours (2 print layers)
    corner_radius_mm: float = 2.0    # plan-view rounding of the tile's four corners
    num_colors: int = 8              # max colours (auto-k picks 3..this; with swatches: ignored)
    px_per_mm: float = 4.0           # colour-analysis raster resolution (fine lines need ≥ 4)
    mesh_resolution_mm: float = 0.16 # 0.12 exceeds Cloud Run 2 GiB on full-tile bodies; grid spacing in X/Y (smaller = smoother, slower)
    smoothing_mm: float = 0.5        # majority-filter radius used to clean colour regions
    min_feature_mm2: float = 2.0     # drop islands / holes smaller than this
    merge_delta_e: float = 12.0      # merge shading bands of one glaze (ΔE76 below this + shared border); 0 = off
    bead_height_mm: float = 1.2      # printable minimum height for thin strokes / outlines (0 = off)
    bead_width_mm: float = 0.8       # ... reached this far from the seam (strokes ≥ 2× this stand ≥ bead height)
    min_band_mm: float = 3.0         # smallest edge-roll width for small patches (band ∝ 0.6 × patch half-width)
    clearance_mm: float = 0.0        # gap between neighbouring colour pieces (0 = flush puzzle-piece fit)
    outline_height_mm: float = 0.8   # raised tube-lining ridge along detected outlines (0 = off)
    outline_width_mm: float = 1.2    # full width of that ridge
    edge_is_seam: bool = False       # False: fields run level to the tile edge with a soft roll-off
    remove_glare: bool = False       # opt-in glare/sticker inpaint; off by default (eats white motifs)
    symmetry: str = "off"            # "off" | "auto" | "c4" | "d4" — opt-in: averaging a slightly misaligned photo smears detail
    output_format: str = "3mf"       # "3mf" | "glb"

    def validate(self) -> "TileConfig":
        def rng(name, lo, hi):
            v = getattr(self, name)
            if not (isinstance(v, (int, float)) and math.isfinite(v) and lo <= v <= hi):
                raise ValueError(f"{name} must be between {lo} and {hi} (got {v!r})")

        rng("tile_size_mm", 20, 400)
        rng("pad_thickness_mm", 0.4, 40)
        rng("relief_height_mm", 0.1, 40)
        rng("fillet_radius_mm", 0.5, 60)
        rng("groove_floor_mm", 0.1, 5)
        rng("dome_height_mm", 0, 20)
        rng("dome_reach_mm", 0.5, 100)
        rng("corner_radius_mm", 0, 20)
        rng("num_colors", 2, MAX_COLORS)
        rng("px_per_mm", 0.5, 8)
        rng("mesh_resolution_mm", 0.05, 1)
        rng("smoothing_mm", 0, 5)
        rng("min_feature_mm2", 0, 100)
        rng("merge_delta_e", 0, 50)
        rng("bead_height_mm", 0, 5)
        rng("bead_width_mm", 0.2, 5)
        rng("min_band_mm", 0.5, 20)
        rng("outline_height_mm", 0, 3)
        rng("clearance_mm", 0, 2)
        rng("outline_width_mm", 0.4, 4)
        if self.symmetry not in ("auto", "off", "c4", "d4"):
            raise ValueError("symmetry must be auto, off, c4 or d4")
        if self.output_format not in ("3mf", "glb"):
            raise ValueError("output_format must be '3mf' or 'glb'")
        self.num_colors = int(self.num_colors)
        self.corner_radius_mm = min(self.corner_radius_mm, self.tile_size_mm / 4)
        # keep rasters bounded so huge tiles don't blow up memory / time
        self.px_per_mm = min(self.px_per_mm, MAX_RASTER_SIDE / self.tile_size_mm)
        self.mesh_resolution_mm = max(self.mesh_resolution_mm, self.tile_size_mm / MAX_MESH_CELLS)
        self.min_feature_mm2 = max(self.min_feature_mm2, 0.64)    # ≥ (2 × 0.4 mm nozzle)²
        return self


# --------------------------------------------------------------------------- image IO
def decode_image(data: bytes) -> tuple[np.ndarray, float]:
    """Decode upload bytes to RGB uint8, longer side capped at MAX_INPUT_SIDE.

    Returns (rgb, scale) where scale maps original-pixel coordinates onto the returned array."""
    if not data:
        raise ValueError("empty image upload")
    arr = np.frombuffer(data, np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("could not decode image (use JPEG / PNG / WebP)")
    h, w = bgr.shape[:2]
    s = min(1.0, MAX_INPUT_SIDE / max(h, w))
    if s < 1:
        bgr = cv2.resize(bgr, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), s


def order_corners(pts) -> np.ndarray:
    """Return 4 points ordered TL, TR, BR, BL (image coords, y down)."""
    p = np.asarray(pts, np.float64).reshape(-1, 2)
    if p.shape != (4, 2) or not np.isfinite(p).all():
        raise ValueError("corners must be exactly 4 [x, y] pairs")
    c = p.mean(0)
    ang = np.arctan2(p[:, 1] - c[1], p[:, 0] - c[0])     # clockwise on screen
    p = p[np.argsort(ang)]
    start = int(np.argmin(p.sum(1)))                      # top-left = min(x + y)
    return np.roll(p, -start, axis=0).astype(np.float32)


def warp_tile(rgb: np.ndarray, corners, out_px: int, corners_scale: float = 1.0,
              inset: float = 0.0) -> np.ndarray:
    """Perspective-flatten the quad given by `corners` into an out_px x out_px square."""
    h, w = rgb.shape[:2]
    if corners is None:
        side = min(h, w)
        x0, y0 = (w - side) / 2, (h - side) / 2
        corners = [[x0, y0], [x0 + side, y0], [x0 + side, y0 + side], [x0, y0 + side]]
        corners_scale = 1.0          # already in decoded-image pixels
    src = order_corners(corners) * np.float32(corners_scale)
    if inset > 0:   # pull corners slightly inward: grout / frame / shadow never gets sampled as a glaze
        c = src.mean(0)
        src = (c + (src - c) * (1 - 2 * inset)).astype(np.float32)
    if abs(cv2.contourArea(src)) < 0.01 * w * h:
        raise ValueError("selected tile area is too small — check the corner points")
    # warp at 2x then area-downsample: anti-aliases fine glaze lines
    big = out_px * 2
    dst = np.float32([[0, 0], [big - 1, 0], [big - 1, big - 1], [0, big - 1]])
    m = cv2.getPerspectiveTransform(src, dst)
    flat = cv2.warpPerspective(rgb, m, (big, big), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return cv2.resize(flat, (out_px, out_px), interpolation=cv2.INTER_AREA)


# --------------------------------------------------------------------------- colour
def _rgb_to_lab(rgb_u8: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb_u8.astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)


def _lab_to_rgb(lab: np.ndarray) -> np.ndarray:
    rgb = cv2.cvtColor(lab.astype(np.float32).reshape(1, -1, 3), cv2.COLOR_LAB2RGB)[0]
    return np.clip(np.round(rgb * 255), 0, 255).astype(np.uint8)


def quantize(rgb: np.ndarray, swatches: list | None, k: int) -> tuple[np.ndarray, np.ndarray]:
    """Map every pixel to the nearest palette colour (CIE76 ΔE in Lab).

    Returns (labels HxW int32, palette Nx3 uint8). Palette = user swatches, or k-means centres.
    """
    # edge-preserving denoise: kills photo grain / glaze crazing / soft shading without blurring motif edges
    smooth = cv2.bilateralFilter(rgb, 9, 45, 9)
    lab = _rgb_to_lab(smooth).reshape(-1, 3)

    if swatches:
        pal = np.asarray(swatches, np.float64).reshape(-1, 3)
        if len(pal) > MAX_COLORS:
            raise ValueError(f"at most {MAX_COLORS} swatches")
        if ((pal < 0) | (pal > 255)).any():
            raise ValueError("swatch channels must be 0..255")
        pal = pal.round().astype(np.uint8)
        pal_lab = _rgb_to_lab(pal[None])[0]
    else:
        rs = np.random.default_rng(0)
        sample = lab[rs.choice(len(lab), size=min(len(lab), 40000), replace=False)]
        km = KMeans(n_clusters=k, n_init=4, random_state=0).fit(sample)
        pal_lab = km.cluster_centers_.astype(np.float32)
        pal = _lab_to_rgb(pal_lab)

    d = ((lab[:, None, :] - pal_lab[None, :, :]) ** 2).sum(-1)
    labels = d.argmin(1).astype(np.int32).reshape(rgb.shape[:2])
    return labels, pal


def merge_shading_bands(labels: np.ndarray, palette: np.ndarray, delta_e: float = 12.0,
                        shared: float = 0.15, max_colors: int | None = None) -> tuple[np.ndarray, np.ndarray, int]:
    """k-means splits one shaded glaze (photo light, painted shading) into 2–3 bands, which would
    become fake grooves and extra bodies. Merge two colours when they are close (ΔE76 < delta_e)
    AND their regions share > `shared` of either one's outline. Distinct glazes that merely look
    alike but don't touch stay separate. Then, if more than `max_colors` remain, keep merging the
    globally closest pair (over-segment-then-merge: k-means is run with extra clusters so a big
    plain ground can't eat the budget and small distinct glazes survive). Returns (labels, palette, merges)."""
    if delta_e <= 0 and not max_colors:
        return labels, palette, 0
    k3 = np.ones((3, 3), np.uint8)
    merges = 0
    while True:
        n = len(palette)
        lab = _rgb_to_lab(palette[None])[0]
        cover = np.bincount(labels.ravel(), minlength=n).astype(np.float64)
        masks = [(labels == i).astype(np.uint8) for i in range(n)]
        perim = [max(1, cv2.countNonZero(cv2.morphologyEx(m, cv2.MORPH_GRADIENT, k3))) for m in masks]
        grown = [cv2.dilate(m, k3) for m in masks]
        best = None
        for i in range(n):
            for j in range(i + 1, n):
                de = float(np.linalg.norm(lab[i] - lab[j]))
                if de >= delta_e or cover[i] == 0 or cover[j] == 0 or delta_e <= 0:
                    continue
                border = cv2.countNonZero(grown[i] & masks[j])
                if border / min(perim[i], perim[j]) > shared and (best is None or de < best[0]):
                    best = (de, i, j)
        if best is None and max_colors and n > max_colors:
            pairs = [(float(np.linalg.norm(lab[i] - lab[j])), i, j) for i in range(n) for j in range(i + 1, n)]
            best = min(pairs)
        if best is None:
            return labels, palette, merges
        _, i, j = best
        w = cover[i] / (cover[i] + cover[j])                     # coverage-weighted Lab mean
        palette = palette.copy()
        palette[i] = _lab_to_rgb((lab[i] * w + lab[j] * (1 - w))[None])[0]
        labels = np.where(labels == j, i, labels)
        labels = np.where(labels > j, labels - 1, labels).astype(np.int32)
        palette = np.delete(palette, j, axis=0)
        merges += 1


def remove_glare(rgb: np.ndarray, mm_per_px: float, max_frac: float = 0.03, min_fat_mm: float = 1.5,
                 disc_mm: float = 10.0) -> tuple[np.ndarray, int]:
    """Specular highlights and paper stickers: very light, almost grey, locally brighter than their
    surroundings, compact (thin white tube-lines are kept) and small compared with the tile.
    Inpaint them from their surroundings before quantising. (Fable photo report, #2.)
    Returns (rgb, inpainted pixel count)."""
    lab = _rgb_to_lab(rgb)
    L, chroma = lab[..., 0], np.hypot(lab[..., 1], lab[..., 2])
    r = max(1, int(round(disc_mm / mm_per_px)))
    disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    local = L.astype(np.float32) - cv2.morphologyEx(L.astype(np.float32), cv2.MORPH_OPEN, disc)
    cand = ((L > 80) & (chroma < 16) & (local > 14)).astype(np.uint8)
    cand = cv2.morphologyEx(cand, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, cc, stats, _ = cv2.connectedComponentsWithStats(cand, connectivity=8)
    dist = cv2.distanceTransform(cand, cv2.DIST_L2, 5) * mm_per_px
    fat = np.zeros(n); np.maximum.at(fat, cc.ravel(), dist.ravel())
    keep = (stats[:, cv2.CC_STAT_AREA] <= max_frac * cand.size) & (fat >= min_fat_mm)
    keep[0] = False
    mask = keep[cc].astype(np.uint8)
    if not mask.any():
        return rgb, 0
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    return cv2.inpaint(rgb, mask, 5, cv2.INPAINT_TELEA), int(mask.sum())


def quantize_auto(rgb: np.ndarray, k_max: int = 12, k_cap: int = 8, l_weight: float = 0.5,
                  min_de: float = 14.0, shade_de: float = 12.0, k_min: int = 3):
    """Auto colour count (Fable photo report, #3). Over-segment with k_max clusters in Lab with L
    down-weighted (hue/chroma dominate, so light/shadow on one glaze doesn't split it), merge
    touching shading bands (ΔE < shade_de), then keep merging the closest pair while it is closer
    than min_de in weighted Lab — and always down to k_cap. Typical result 5–8 colours."""
    smooth = cv2.pyrMeanShiftFiltering(cv2.bilateralFilter(rgb, 9, 45, 9), 7, 22)   # report #1
    lab = _rgb_to_lab(smooth)
    w = np.array([l_weight, 1.0, 1.0], np.float32)
    feat = (lab * w).reshape(-1, 3)
    rs = np.random.default_rng(0)
    sample = feat[rs.choice(len(feat), size=min(len(feat), 30000), replace=False)]
    cen = KMeans(n_clusters=k_max, n_init=3, random_state=0).fit(sample).cluster_centers_
    labels = ((feat[:, None, :] - cen[None]) ** 2).sum(-1).argmin(1).astype(np.int32).reshape(rgb.shape[:2])
    pal = _lab_to_rgb((cen / w).astype(np.float32))
    labels, pal, merged = merge_shading_bands(labels, pal, shade_de)
    while len(pal) > k_min:
        li = _rgb_to_lab(pal[None])[0] * w
        closest = min(np.linalg.norm(li[i] - li[j]) for i in range(len(pal)) for j in range(i + 1, len(pal)))
        if closest >= min_de and len(pal) <= k_cap:
            break
        labels, pal, m = merge_shading_bands(labels, pal, 0.0, max_colors=len(pal) - 1)
        merged += m
    return labels, pal, merged


def symmetrise(rgb: np.ndarray, mode: str = "auto", max_frac: float = 0.05,
               big_de: float = 20.0) -> tuple[np.ndarray, str]:
    """Majolica designs are usually 4- or 8-fold symmetric; glare, chips and wear are not. Average
    the flattened tile over its symmetry group to cancel them. mode: "off" | "auto" | "c4" | "d4".
    "auto" applies the largest group only if fewer than `max_frac` of the pixels differ from the
    symmetric average by more than `big_de` (ΔE) — a mean error would let a mostly-plain tile with
    an asymmetric motif (e.g. a fruit bowl on a dark ground) pass and get its motif mirrored."""
    if mode == "off":
        return rgb, "off"
    lab = _rgb_to_lab(rgb)
    rots = [lab, np.rot90(lab, 1), np.rot90(lab, 2), np.rot90(lab, 3)]
    groups = {"c4": rots, "d4": rots + [r[:, ::-1] for r in rots]}
    order = ["d4", "c4"] if mode == "auto" else [mode]
    for g in order:
        avg = np.mean(groups[g], axis=0)
        frac = float((np.linalg.norm(avg - lab, axis=-1) > big_de).mean())
        if mode != "auto" or frac < max_frac:
            return _lab_to_rgb(avg.reshape(-1, 3)).reshape(rgb.shape), g
    return rgb, "none"


def absorb_glare_islands(labels: np.ndarray, palette: np.ndarray, mm_per_px: float,
                         max_mm2: float = 25.0, d_l: float = 15.0, host_chroma: float = 15.0) -> tuple[np.ndarray, int]:
    """Specular highlights on a glossy coloured glaze (rose leaves, petals) quantise to a light colour
    and show as holes in the relief. Absorb a patch into its surroundings when it is small
    (≤ max_mm2), completely enclosed by ONE other colour, clearly lighter than it (ΔL > d_l), and that
    host glaze is colourful (chroma > host_chroma). Neutral hosts (black/grey/white) are exempt, so
    deliberate light details such as the white eyes on a black bear survive."""
    lab = _rgb_to_lab(palette[None])[0]
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    out = labels.copy(); absorbed = 0; k3 = np.ones((3, 3), np.uint8)
    max_px = max_mm2 / mm_per_px ** 2
    H, W = labels.shape
    for i in range(len(palette)):
        n, cc, st, _ = cv2.connectedComponentsWithStats((labels == i).astype(np.uint8), connectivity=8)
        for c in np.where(st[1:, cv2.CC_STAT_AREA] <= max_px)[0] + 1:
            x, y, w, h = st[c, :4]
            if x == 0 or y == 0 or x + w >= W or y + h >= H:      # touches the tile edge: not enclosed
                continue
            x0, y0, x1, y1 = x - 1, y - 1, x + w + 1, y + h + 1
            comp = cc[y0:y1, x0:x1] == c
            ring = cv2.dilate(comp.astype(np.uint8), k3).astype(bool) & ~comp
            host = np.unique(labels[y0:y1, x0:x1][ring])
            if len(host) != 1:
                continue
            j = int(host[0])
            if chroma[j] > host_chroma and lab[i, 0] - lab[j, 0] > d_l:
                out[y0:y1, x0:x1][comp] = j
                absorbed += 1
    return out, absorbed


def majority_filter(labels: np.ndarray, n: int, radius_px: int) -> np.ndarray:
    """Mode filter with a disk kernel — rounds off jagged region borders."""
    if radius_px < 1:
        return labels
    ksz = 2 * radius_px + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksz, ksz)).astype(np.float32)
    scores = np.stack([cv2.filter2D((labels == i).astype(np.float32), -1, kernel,
                                    borderType=cv2.BORDER_REFLECT) for i in range(n)])
    return scores.argmax(0).astype(np.int32)


def remove_specks(labels: np.ndarray, n: int, min_area_px: int, keep_len_px: float = 0,
                  palette: np.ndarray | None = None, keep_de: float = 25.0, keep_min_px: int = 0) -> np.ndarray:
    """Re-assign connected components smaller than min_area_px to their nearest big neighbour.
    Kept anyway: small but elongated components (bounding-box length ≥ keep_len_px) — thin outline
    strokes / tube-lining — and, when `palette` is given, small high-contrast details (ΔE > keep_de
    to the colour around them and ≥ keep_min_px): eyes, leopard spots, a rose centre."""
    if min_area_px < 2:
        return labels
    lab = _rgb_to_lab(palette[None])[0] if palette is not None else None
    k3 = np.ones((3, 3), np.uint8)
    small = np.zeros(labels.shape, bool)
    for i in range(n):
        cnt, cc, stats, _ = cv2.connectedComponentsWithStats((labels == i).astype(np.uint8), connectivity=8)
        length = np.maximum(stats[1:, cv2.CC_STAT_WIDTH], stats[1:, cv2.CC_STAT_HEIGHT])
        speck = stats[1:, cv2.CC_STAT_AREA] < min_area_px
        if keep_len_px > 0:
            speck &= length < keep_len_px
        if lab is not None:                       # small-detail keeper (Fable photo report, #4)
            for j in np.where(speck & (stats[1:, cv2.CC_STAT_AREA] >= max(keep_min_px, 1)))[0]:
                x, y, w, h = stats[j + 1, :4]
                x0, y0 = max(x - 1, 0), max(y - 1, 0)
                sub_cc = cc[y0:y + h + 1, x0:x + w + 1] == j + 1
                ring = cv2.dilate(sub_cc.astype(np.uint8), k3).astype(bool) & ~sub_cc
                around = labels[y0:y + h + 1, x0:x + w + 1][ring]
                if around.size and np.linalg.norm(lab[i] - lab[np.bincount(around).argmax()]) > keep_de:
                    speck[j] = False
        tiny = np.where(speck)[0] + 1
        if len(tiny):
            small |= np.isin(cc, tiny)
    if not small.any() or small.all():
        return labels
    # nearest kept pixel for every small pixel
    _, nearest = cv2.distanceTransformWithLabels(small.astype(np.uint8), cv2.DIST_L2, 5,
                                                 labelType=cv2.DIST_LABEL_PIXEL)
    lut = np.zeros(nearest.max() + 1, np.int32)
    lut[nearest[~small]] = labels[~small]
    out = labels.copy()
    out[small] = lut[nearest[small]]
    return out


# --------------------------------------------------------------------------- tube-lining outlines
def _prune_skeleton(sk: np.ndarray, n: int) -> np.ndarray:
    """Remove `n` pixels from every free end (kills spurs; shortens real ends by n px)."""
    k = np.ones((3, 3), np.float32); k[1, 1] = 0
    sk = sk.astype(np.uint8)
    for _ in range(n):
        nb = cv2.filter2D(sk, -1, k, borderType=cv2.BORDER_CONSTANT)
        ends = (sk > 0) & (nb <= 1)
        if not ends.any():
            break
        sk[ends] = 0
    return sk


def detect_outlines(rgb: np.ndarray, mm_per_px: float, max_width_mm: float = 2.0, hi: float = 10.0,
                    lo: float = 5.0, min_len_mm: float = 4.0, min_width_mm: float = 0.4,
                    texture_density: float = 0.05, short_len_mm: float = 8.0, short_hi: float = 14.0):
    """Tube-lining / contour lines, independent of colour clustering (Fable, verified on 16 photos).

    Primitive: morphological top-hat (light lines) and black-hat (dark lines) of L with a disc wider
    than any tube-line. It responds only to structures thinner than the disc in every direction, so
    colour step edges, grounds and wide glare blobs give exactly zero (ridge filters such as
    Sato/Frangi fire on every colour boundary). Runs at 2× the raster so 0.5 mm lines are ≥ 2 px.
    Then: hysteresis (keeps faint-but-connected cream-on-white lines), an opening (kills 1-px
    crazing), a closing (bridges ≤ 0.5 mm gaps), skeleton + spur pruning, length ≥ min_len_mm,
    short pieces must be strong (stray arcs), and components that live in a dense tangle of
    skeleton (glossy modelled glaze: lion mane, textured petals) are dropped as texture.

    Returns (ridge_dist, comps): ridge_dist = distance (mm, raster) to the nearest outline centre-
    line, capped at 4 mm; comps = list of (full-width mask, centre-line mask) per outline."""
    up = 2
    big = cv2.resize(rgb, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
    L = _rgb_to_lab(cv2.bilateralFilter(big, 5, 25, 3))[..., 0].astype(np.float32)
    px = mm_per_px / up
    r = max(2, int(round(max_width_mm / 2 / px)))
    disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (max(2, int(round(min_width_mm / px))),) * 2)
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (max(3, int(round(0.5 / px)) | 1),) * 2)
    box = max(3, int(round(6.0 / px)) | 1)
    from skimage.filters import apply_hysteresis_threshold
    from skimage.morphology import skeletonize

    H, W = rgb.shape[:2]
    skel_all = np.zeros((H * up, W * up), bool)
    comps = []
    for resp in (L - cv2.morphologyEx(L, cv2.MORPH_OPEN, disc), cv2.morphologyEx(L, cv2.MORPH_CLOSE, disc) - L):
        resp = cv2.GaussianBlur(resp, (0, 0), 0.7)
        m = apply_hysteresis_threshold(resp, lo, hi).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k_open)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k_close)
        sk = _prune_skeleton(skeletonize(m.astype(bool)), int(round(0.5 / px)))
        density = cv2.blur(sk.astype(np.float32), (box, box))
        n, cc, st, _ = cv2.connectedComponentsWithStats(sk, connectivity=8)
        if n <= 1:
            continue
        length = st[:, cv2.CC_STAT_AREA] * px
        cnt = np.maximum(st[:, cv2.CC_STAT_AREA], 1)
        halfw = cv2.distanceTransform(m, cv2.DIST_L2, 3) * px                  # line half-width at the centre-line
        mean_resp = np.bincount(cc.ravel(), weights=resp.ravel(), minlength=n) / cnt
        mean_dens = np.bincount(cc.ravel(), weights=density.ravel(), minlength=n) / cnt
        mean_hw = np.bincount(cc.ravel(), weights=halfw.ravel(), minlength=n) / cnt
        # crazing (glaze crack network) is hair-thin and faint: require a real line width and contrast
        keep = ((length >= min_len_mm) & (mean_dens < texture_density) & (mean_hw >= 0.5 * min_width_mm)
                & (mean_resp >= hi) & ((length >= short_len_mm) | (mean_resp >= short_hi)))
        keep[0] = False
        sk_keep = keep[cc]
        skel_all |= sk_keep
        # full-width component masks (for colour snapping): mask components that own a kept skeleton
        nm_, mc = cv2.connectedComponents(m, connectivity=8)
        for j in np.unique(mc[sk_keep]):
            if j == 0:
                continue
            full = cv2.resize((mc == j).astype(np.uint8), (W, H), interpolation=cv2.INTER_AREA) > 0.4
            centre = cv2.resize((sk_keep & (mc == j)).astype(np.uint8), (W, H), interpolation=cv2.INTER_AREA) > 0.2
            if centre.any():
                comps.append((full, centre))
    dist = cv2.distanceTransform((~skel_all).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * px
    ridge_dist = cv2.resize(np.minimum(dist, 4.0).astype(np.float32), (W, H), interpolation=cv2.INTER_AREA)
    return ridge_dist, comps


def snap_outline_colours(labels: np.ndarray, palette: np.ndarray, rgb: np.ndarray, comps,
                         de_host: float = 18.0, de_snap: float = 10.0) -> tuple[np.ndarray, int]:
    """An outline whose colour clearly differs from the region it sits in (ΔE > de_host) and matches
    another existing glaze colour (ΔE ≤ de_snap) is relabelled to that colour (e.g. a dark-green stem
    on white). Never invents palette entries (a 2 mm mask mixes line and halo colour). The rest stay
    pure geometry ridges, coloured like the region they sit in."""
    lab_img = _rgb_to_lab(rgb)
    pal_lab = _rgb_to_lab(palette[None])[0]
    src = labels                                   # decide on the original labels, write to a copy
    labels = labels.copy()
    snapped = 0
    for full, centre in comps:
        if not centre.any():
            continue
        col = np.median(lab_img[centre], axis=0)
        host = np.bincount(src[full]).argmax()
        if np.linalg.norm(pal_lab[host] - col) <= de_host:
            continue
        de = np.linalg.norm(pal_lab - col, axis=1); de[host] = np.inf
        j = int(de.argmin())
        if de[j] > de_snap:
            continue
        # The detection mask is fat (line + halo): only recolour a band as wide as the line itself
        # around its centre-line, else the halo eats the fill around it (leaf fill -> lattice).
        half = np.median(cv2.distanceTransform(full.astype(np.uint8), cv2.DIST_L2, 3)[centre])
        r = max(1, int(round(half)))
        band = cv2.dilate(centre.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1,) * 2)).astype(bool) & full
        # Only snap to a glaze that is actually present right next to the line (within a few line widths): a dark rim-shadow
        # inside a red rose must not turn dark green just because dark green is the nearest colour.
        k = 2 * max(r, 3) + 1
        ring = cv2.dilate(full.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))).astype(bool)
        if not (src[ring] == j).any():
            continue
        labels[band] = j
        snapped += 1
    return labels, snapped


# --------------------------------------------------------------------------- mesh helpers
def _signed_volume(v: np.ndarray, f: np.ndarray) -> float:
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


def _orient_outward(v: np.ndarray, f: np.ndarray) -> np.ndarray:
    return f[:, [0, 2, 1]] if _signed_volume(v, f) < 0 else f


def _weld(v: np.ndarray, f: np.ndarray, tol: float = 1e-5):
    """Merge coincident vertices (tessellators duplicate them along face seams)."""
    key = np.round(v / tol).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    f = inv.reshape(-1)[f]
    f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])]
    return v[first], f


def _is_closed_manifold(f: np.ndarray) -> bool:
    """Every edge used by exactly two faces (watertight, no non-manifold edges)."""
    e = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    key = e[:, 0].astype(np.int64) * (int(f.max()) + 1) + e[:, 1]
    _, counts = np.unique(key, return_counts=True)
    return bool((counts == 2).all())


def _decimate(v: np.ndarray, f: np.ndarray, target_faces: int):
    """Quadric decimation: flat glaze areas collapse, the rounded rims keep their triangles.
    Decimation occasionally creates a non-manifold edge (seen on real tiles 02/03), so every result
    is checked; on failure retry at a few other budgets, else keep the dense (watertight) mesh."""
    if len(f) <= target_faces:
        return v, f
    try:
        import fast_simplification
        v32, f32 = np.ascontiguousarray(v, np.float32), np.ascontiguousarray(f, np.int32)
        for t in (target_faces, int(target_faces * 1.15), int(target_faces * 1.35), int(target_faces * 0.85)):
            if t >= len(f):
                continue
            v2, f2 = fast_simplification.simplify(v32, f32,
                                                  target_reduction=1 - t / len(f), agg=5)
            if len(f2) > 0 and _is_closed_manifold(f2):
                return v2.astype(np.float64), f2.astype(np.int64)
        log.warning("decimation produced non-manifold meshes at all budgets; keeping dense mesh")
    except Exception as exc:  # keep the dense (still valid) mesh rather than fail the job
        log.warning("decimation skipped: %s", exc)
    return v, f


def _rounded_square_sdf(x: np.ndarray, y: np.ndarray, size: float, rc: float) -> np.ndarray:
    """2D SDF of the tile outline (square [0,size]² with corner radius rc); negative inside."""
    h = size / 2
    qx, qy = np.abs(x - h) - (h - rc), np.abs(y - h) - (h - rc)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - rc


# --------------------------------------------------------------------------- bodies
def _fine_grid_sdf(mask: np.ndarray, size: float, n: int, margin: int,
                   extend_edge: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Raster mask -> (binary, signed distance in mm, negative inside) on an n×n fine grid padded
    by `margin` cells. The raster staircase is blurred away (≈ 1.2 raster px) before
    re-thresholding, and the distance field is lightly smoothed so walls come out fair."""
    h = size / n
    m = cv2.resize(mask.astype(np.float32), (n, n), interpolation=cv2.INTER_LINEAR)
    m = cv2.GaussianBlur(m, (0, 0), max(1.0, 1.2 * (size / mask.shape[0]) / h))
    core = (m > 0.5).astype(np.uint8)
    # extend_edge: regions touching the tile edge continue past it, so the edge is not a seam
    big = np.pad(core, margin, mode="edge" if extend_edge else "constant")
    d_in = cv2.distanceTransform(big, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    d_out = cv2.distanceTransform(1 - big, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    return big, cv2.GaussianBlur((d_out - d_in) * h, (0, 0), 1.5)


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


def smooth_max(a: np.ndarray, b: np.ndarray, eps: float = 0.2) -> np.ndarray:
    return 0.5 * (a + b + np.sqrt((a - b) ** 2 + eps * eps))


def bead_floor(d: np.ndarray, h_bead: float, r_bead: float) -> np.ndarray:
    """Printable minimum for thin strokes, independent of the band width: any stroke ≥ 2·r_bead
    wide stands ≥ h_bead (rounded quarter-ellipse-ish ease), so 0.5–2 mm outlines don't vanish."""
    return h_bead * (1 - (1 - np.clip(d / r_bead, 0, 1)) ** 2)


def partition_fields(labels: np.ndarray, size: float, n: int, margin: int, edge_is_seam: bool):
    """One shared partition of the fine grid: for every colour i a field
        phi_i = (d_i − min_{j≠i} d_j) / 2          (d = smoothed signed distance to colour j's mask)
    phi_i < 0 exactly where colour i wins, and on a border between i and j phi_i = −phi_j, so both
    neighbours' walls land on the SAME surface — clean puzzle-piece borders, no overlap, no gap.
    Returns {label: phi (padded fine grid, mm)}."""
    labs = [int(l) for l in np.unique(labels)]
    d = np.stack([_fine_grid_sdf(labels == l, size, n, margin, extend_edge=not edge_is_seam)[1]
                  for l in labs]).astype(np.float32)
    if len(labs) == 1:
        return {labs[0]: d[0]}
    part = np.partition(d, 1, axis=0)
    m1, m2 = part[0], part[1]
    out = {}
    for k, l in enumerate(labs):
        other = np.where(d[k] <= m1, m2, m1)          # min over the OTHER colours
        out[l] = 0.5 * (d[k] - other)
    return out


def cushion_body_mesh(phi_full: np.ndarray, size: float, z0: float, floor: float,
                      total: float, corner_r: float, grid_mm: float, psi_raster: np.ndarray,
                      band_w: float | np.ndarray = 10.0, crown_h: float = 1.5, crown_w: float = 12.0,
                      L_mm: float = 1.0, seam_slope: float = 1.5, shoulder: float = 0.8, sweeps: int = 40,
                      bead_h: float = 0.0, bead_r: float = 0.8, edge_is_seam: bool = False,
                      edge_band_w: float = 4.0, edge_drop: float = 0.35,
                      ridge_dist: np.ndarray | None = None, line_h: float = 0.0, line_w: float = 1.2,
                      return_top: bool = False, clearance: float = 0.0):
    """Closed mesh for one colour, "extrude everything to the shared top, then carve the edges down
    into the seams" (profile designed + verified with Fable):

        d  = smooth seam distance from the screened-Poisson field ψ (seam_field), refined on the fine
             grid so the colour raster's staircase doesn't leak into the seams
        T  = z0 + floor + [ (total − C)·f(d/W) + C·(1 − e^(−d/Wc)) ] · pin
        f  = edge_roundover: 0 at the seam (finite slope → soft V valley), C² into the top

    Big patches top out near `total` with a near-level top whose gentle crown flattens as the patch
    grows; patches narrower than ~2W stay in the edge band → round arches (two neighbouring
    rectangles give a lowercase "m" in section); thin strokes stay lower and rounded. Every seam
    is the lowest point; no colour is treated as background.

    Footprint = this colour's cell of the shared partition (partition_fields), shrunk by
    clearance/2: with clearance 0 neighbours meet face to face like puzzle pieces; with clearance c
    there is a c-wide slot down to the pad between every two colours. Field sdf = max(z − T, z0 − z,
    lateral) is linear in z, so marching cubes places the top exactly with coarse Z levels."""
    from skimage.measure import marching_cubes

    n = int(round(size / grid_mm))
    h = size / n
    margin = int(math.ceil(1.0 / h)) + 3
    rows, cols = np.nonzero(phi_full < 0)
    if len(rows) == 0:
        return None
    r0, r1 = max(rows.min() - margin, 0), min(rows.max() + margin + 1, phi_full.shape[0])
    c0, c1 = max(cols.min() - margin, 0), min(cols.max() + margin + 1, phi_full.shape[1])
    d_own = phi_full[r0:r1, c0:c1]

    # cell centres in model mm (image rows run down, model Y runs up)
    xs = (np.arange(c0, c1) - margin + 0.5) * h
    ys_img = (np.arange(r0, r1) - margin + 0.5) * h
    d_tile = _rounded_square_sdf(xs[None, :], ys_img[:, None], size, corner_r)
    lateral = np.maximum(d_own + 0.5 * clearance, d_tile)

    if edge_is_seam:                       # tile edge treated like a colour seam (groove all round)
        inside = (d_own < 0) & (d_tile < 0)
        d_fine = np.maximum(np.minimum(-d_own, -d_tile), 0).astype(np.float32)
    else:                                  # tile edge is an edge: fields run level to it, soft roll-off
        inside = d_own < 0
        d_fine = np.maximum(-d_own, 0).astype(np.float32)
    pin = 1 - (1 - np.clip(d_fine / shoulder, 0, 1)) ** 2          # exact groove floor at each seam

    if isinstance(band_w, np.ndarray):     # per-patch band width (raster) -> fine grid; constant per patch
        band_w = np.pad(cv2.resize(band_w.astype(np.float32), (n, n), interpolation=cv2.INTER_NEAREST),
                        margin, mode="edge")[r0:r1, c0:c1]
    psi = np.pad(cv2.resize(psi_raster, (n, n), interpolation=cv2.INTER_CUBIC), margin,
                 mode="constant" if edge_is_seam else "edge")[r0:r1, c0:c1]
    psi = refine_seam_field(psi, inside, L_mm, h, sweeps) if sweeps > 0 else np.clip(psi, 0, 1) * inside
    d = seam_distance(psi, L_mm)
    prof = cushion_profile(d, total, np.maximum(band_w, 0.5), seam_slope, crown_h, crown_w)
    if bead_h > 0:
        prof = smooth_max(prof, bead_floor(d, min(bead_h, total), bead_r)) * (d > 0)
    if not edge_is_seam:
        te = edge_roundover(np.clip(-d_tile, 0, None) / edge_band_w, 1.5)
        prof = prof * ((1 - edge_drop) + edge_drop * te)
    if ridge_dist is not None and line_h > 0:
        # tube-lining ridge: a smooth cos² bead over the detected centre-line, ADDED on top of the
        # cushion (a real tube-line sits on the glaze), coloured like the body it lies in. Faded out
        # within ~1.6 mm of a seam: there the groove already draws the line, and rim-shadow false
        # positives hug the seams. The distance field is blurred so the centre-line's pixel
        # staircase can't show as a dashed/beaded ridge.
        rd = np.pad(cv2.resize(ridge_dist, (n, n), interpolation=cv2.INTER_LINEAR), margin, mode="edge")[r0:r1, c0:c1]
        rd = cv2.GaussianBlur(rd, (0, 0), max(0.5, 0.15 / h))
        t = np.clip(rd / (0.5 * line_w), 0, 1)
        gate = np.clip((d - 0.8) / 0.8, 0, 1) ** 2
        prof = prof + line_h * np.cos(0.5 * np.pi * t) ** 2 * gate
    top = (z0 + floor + prof * pin).astype(np.float32)
    if return_top:                         # verification sheets: the height field + its crop window
        return top, (r0, r1, c0, c1)

    eps = min(0.02, floor / 4)
    lo = max(z0 + 2 * eps, z0 + floor - 0.1)
    # the field is linear in z, so a coarse step is exact; the last level must clear the real peak
    # the field is linear in z (z − T(x,y)), so vertex heights are exact at any level spacing: coarse
    # levels cost no accuracy but cut the 3D grid (memory + marching-cubes time) several-fold
    band = np.arange(lo, float(top.max()), max(Z_STEP_MM, total / 8))
    zs = np.concatenate([[z0 - eps, z0 + eps], band, [float(top.max()) + 0.1]]).astype(np.float32)

    sdf = np.maximum(zs[None, None, :] - top[:, :, None], (z0 - zs)[None, None, :])
    sdf = np.maximum(sdf, lateral.astype(np.float32)[:, :, None])
    if sdf.min() >= 0:
        return None

    verts, faces, _, _ = marching_cubes(sdf, 0.0, allow_degenerate=False)
    del sdf                                # the 3D grid is the biggest allocation: free it now
    # float32 + int32 for the dense mesh (it can be millions of triangles); orientation is fixed by
    # the caller AFTER decimation, on the small mesh (decimation keeps the winding consistent)
    v = np.empty(verts.shape, np.float32)
    v[:, 0] = (c0 + verts[:, 1] - margin + 0.5) * h
    v[:, 1] = size - (r0 + verts[:, 0] - margin + 0.5) * h
    v[:, 2] = np.interp(verts[:, 2], np.arange(len(zs)), zs)   # non-uniform Z levels -> mm
    return v, faces.astype(np.int32)


@functools.lru_cache(maxsize=16)
def pad_mesh(size: float, thickness: float, corner_r: float, seg: int = 24):
    """Backing pad: a rounded-corner square slab (corners = quarter circles, `seg` segments each),
    built directly as a closed, outward-oriented triangle mesh. The outline is convex, so top and
    bottom are triangle fans around the centre."""
    r = min(max(corner_r, 0.0), size / 2)
    pts = []
    for cx, cy, a0 in ((size - r, r, -90), (size - r, size - r, 0), (r, size - r, 90), (r, r, 180)):
        if r <= 0:
            pts.append((cx, cy)); continue
        for k in range(seg + 1):
            a = np.radians(a0 + 90 * k / seg)
            pts.append((cx + r * np.cos(a), cy + r * np.sin(a)))
    ring = np.array(pts, np.float64)
    ring = ring[np.r_[True, np.linalg.norm(np.diff(ring, axis=0), axis=1) > 1e-9]]   # drop duplicates
    m = len(ring)
    v = np.vstack([np.c_[ring, np.zeros(m)], np.c_[ring, np.full(m, thickness)],
                   [[size / 2, size / 2, 0.0], [size / 2, size / 2, thickness]]])
    cb, ct = 2 * m, 2 * m + 1
    i = np.arange(m); j = (i + 1) % m
    faces = np.vstack([np.c_[np.full(m, cb), j, i],             # bottom (normal -z)
                       np.c_[np.full(m, ct), m + i, m + j],     # top (normal +z)
                       np.c_[i, j, m + j], np.c_[i, m + j, m + i]])   # sides
    return v, _orient_outward(v, faces.astype(np.int64))


def build_relief(labels: np.ndarray, palette: np.ndarray, cfg: TileConfig, ridge_dist: np.ndarray | None = None,
                 progress=None):
    """Return (list of (name, rgb, vertices, faces)), stats dict. ridge_dist = detect_outlines()[0].

    All colours are equal: each is one cushion body on the pad. Colours are listed by
    coverage (largest first); the pad is printed in the largest colour, which is the
    filament it would share anyway — not an assumption that it is a "background"."""
    size, pad = cfg.tile_size_mm, cfg.pad_thickness_mm
    mm_per_px = size / labels.shape[0]
    coverage = np.bincount(labels.ravel(), minlength=len(palette)) / labels.size
    order = np.argsort(-coverage, kind="stable")

    n_fine = int(round(size / cfg.mesh_resolution_mm))
    margin = int(math.ceil(1.0 / (size / n_fine))) + 3
    phis = partition_fields(labels, size, n_fine, margin, cfg.edge_is_seam)   # shared borders
    shoulder = min(cfg.fillet_radius_mm, size / 4)              # edge-roll band width

    psi = seam_field(labels, mm_per_px, 1.0, edge_is_seam=cfg.edge_is_seam)   # one sparse solve

    # adaptive edge-roll width per connected patch: W_p = clip(0.6·half-width_p, min_band, W)
    band = np.full(labels.shape, shoulder, np.float32)
    lo_band = min(cfg.min_band_mm, shoulder)
    for ci in range(len(palette)):
        m = (labels == ci).astype(np.uint8)
        k, cc = cv2.connectedComponents(m, connectivity=8)
        dist = cv2.distanceTransform(np.pad(m, 1, mode="edge" if not cfg.edge_is_seam else "constant"),
                                     cv2.DIST_L2, 5)[1:-1, 1:-1]
        half = np.zeros(k); np.maximum.at(half, cc.ravel(), dist.ravel() * mm_per_px)
        sel = m.astype(bool)
        band[sel] = np.clip(0.6 * half[cc[sel]], lo_band, shoulder)

    parts = []
    pv, pf = pad_mesh(size, pad, cfg.corner_radius_mm)
    parts.append(("backing_pad", palette[order[0]], pv, pf))

    def one_body(ci):
        own = (labels == ci).astype(np.uint8)
        if not own.any():
            return None
        res = cushion_body_mesh(phis[int(ci)], size, pad, cfg.groove_floor_mm,
                                cfg.relief_height_mm + cfg.dome_height_mm, cfg.corner_radius_mm,
                                cfg.mesh_resolution_mm, psi, band_w=band, crown_h=cfg.dome_height_mm,
                                crown_w=cfg.dome_reach_mm, bead_h=cfg.bead_height_mm, bead_r=cfg.bead_width_mm,
                                edge_is_seam=cfg.edge_is_seam,
                                edge_band_w=min(4.0, 0.027 * size), edge_drop=0.35,
                                ridge_dist=ridge_dist, line_h=cfg.outline_height_mm, line_w=cfg.outline_width_mm,
                                clearance=cfg.clearance_mm)
        if res is not None:
            v, f = res
            # budget scales with how much outline the colour has (shoulders need triangles, plateaus don't)
            perimeter_mm = cv2.countNonZero(cv2.morphologyEx(own, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))) * mm_per_px / 2
            v, f = _decimate(v, f, target_faces=int(min(MAX_FACES_PER_BODY, max(15_000, FACES_PER_MM * perimeter_mm))))
            v = v.astype(np.float64)
            res = v, _orient_outward(v, f.astype(np.int64))
        if progress:
            progress("body")
        return res

    # bodies are independent: build them on all CPUs (numpy/OpenCV/marching cubes/decimation release the GIL)
    workers = max(1, min(len(order), os.cpu_count() or 1, BODY_WORKERS))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(one_body, order))

    colours = []
    for k, (ci, res) in enumerate(zip(order, results)):
        if res is None:
            continue
        v, f = res
        rgb = palette[ci]
        hexc = "#%02x%02x%02x" % tuple(int(c) for c in rgb)
        parts.append((f"colour{k + 1}_{hexc}", rgb, v, f))
        colours.append({"colour": k + 1, "rgb": [int(c) for c in rgb], "hex": hexc,
                        "extruder": max(1, len(parts) - 1), "coverage": round(float(coverage[ci]), 4)})

    stats = {
        "bodies": len(parts),
        "triangles": int(sum(len(p[3]) for p in parts)),
        "relief_height_mm": cfg.relief_height_mm,
        "dome_height_mm": cfg.dome_height_mm,
        "total_height_mm": round(pad + cfg.groove_floor_mm + cfg.relief_height_mm + cfg.dome_height_mm, 3),
        "colours": colours,
    }
    return parts, stats


# --------------------------------------------------------------------------- export
_CT = ('<?xml version="1.0" encoding="UTF-8"?>\n'
       '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
       '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
       '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
       '<Default Extension="config" ContentType="application/xml"/>'
       '</Types>')
_RELS = ('<?xml version="1.0" encoding="UTF-8"?>\n'
         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
         'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
_IDENTITY = "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def write_3mf(parts) -> bytes:
    """Single multi-part object, laid out the way PrusaSlicer (and its forks OrcaSlicer /
    Bambu Studio) store one: all parts' triangles in ONE <object> mesh, and
    Metadata/Slic3r_PE_model.config naming each part's triangle range + its extruder.
    (A core-spec <components> object is NOT enough — PrusaSlicer splits it into loose objects.)
    Every triangle also carries its colour (basematerials p1) so generic 3MF viewers show colours.

"""
    obj_id, mat_id = 1, 2
    out = io.StringIO()
    w = out.write
    w('<?xml version="1.0" encoding="UTF-8"?>\n'
      '<model unit="millimeter" xml:lang="en-US" '
      'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
      'xmlns:slic3rpe="http://schemas.slic3r.org/3mf/2017/06">\n'
      '<metadata name="slic3rpe:Version3mf">1</metadata>\n'
      '<metadata name="Title">MixoTile relief</metadata>\n'
      '<metadata name="Application">MixoTile 3D Relief Generator</metadata>\n'
      '<resources>\n'
      f'<basematerials id="{mat_id}">\n')
    for name, rgb, _, _ in parts:
        w('<base name="%s" displaycolor="#%02X%02X%02XFF"/>\n' % (_xml_escape(name), *map(int, rgb)))
    w('</basematerials>\n')
    w(f'<object id="{obj_id}" type="model" name="MixoTile relief" pid="{mat_id}" pindex="0">\n'
      '<mesh>\n<vertices>\n')
    # one big %-format per array is ~10x faster than a per-row generator; 3 decimals = 1 um
    for _, _, v, _ in parts:
        w(('<vertex x="%.3f" y="%.3f" z="%.3f"/>\n' * len(v)) % tuple(v.ravel().tolist()))
    w('</vertices>\n<triangles>\n')
    ranges, v_off, t_off = [], 0, 0
    for i, (_, _, v, f) in enumerate(parts):
        tri = np.column_stack([f + v_off, np.full(len(f), i, np.int64)])
        w(('<triangle v1="%d" v2="%d" v3="%d" p1="%d"/>\n' * len(f)) % tuple(tri.ravel().tolist()))
        ranges.append((t_off, t_off + len(f) - 1))
        v_off += len(v)
        t_off += len(f)
    w('</triangles>\n</mesh>\n</object>\n</resources>\n'
      f'<build>\n<item objectid="{obj_id}" printable="1"/>\n</build>\n</model>\n')

    # PrusaSlicer-family part table. Extruder per colour: the pad shares colour 1's filament.
    cfg = io.StringIO()
    c = cfg.write
    c('<?xml version="1.0" encoding="UTF-8"?>\n<config>\n'
      f' <object id="{obj_id}" instances_count="1">\n'
      '  <metadata type="object" key="name" value="MixoTile relief"/>\n')
    for i, ((name, _, _, _), (lo, hi)) in enumerate(zip(parts, ranges)):
        extruder = max(1, i)                       # parts[0] = pad, parts[1] = colour 1 -> both extruder 1
        c(f'  <volume firstid="{lo}" lastid="{hi}">\n'
          f'   <metadata type="volume" key="name" value="{_xml_escape(name)}"/>\n'
          '   <metadata type="volume" key="volume_type" value="ModelPart"/>\n'
          f'   <metadata type="volume" key="matrix" value="{_IDENTITY}"/>\n'
          f'   <metadata type="volume" key="extruder" value="{extruder}"/>\n'
          '  </volume>\n')
    c(' </object>\n</config>\n')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("[Content_Types].xml", _CT)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("3D/3dmodel.model", out.getvalue())
        z.writestr("Metadata/Slic3r_PE_model.config", cfg.getvalue())
    return buf.getvalue()


def write_glb(parts) -> bytes:
    """glTF is Y-up and in metres: rotate Z-up mm -> Y-up m."""
    import trimesh

    scene = trimesh.Scene()
    for name, rgb, v, f in parts:
        vv = np.column_stack([v[:, 0], v[:, 2], -v[:, 1]]) / 1000.0
        mesh = trimesh.Trimesh(vv, f, process=False)
        mesh.visual = trimesh.visual.ColorVisuals(mesh, face_colors=[*map(int, rgb), 255])
        scene.add_geometry(mesh, geom_name=name, node_name=name)
    return scene.export(file_type="glb")


def preview_mesh(parts, max_tris: int = 300_000) -> tuple[list, bytes]:
    """Light preview of the finished bodies for the browser: each part decimated so the total is
    ≈ max_tris, packed as raw little-endian float32 positions (mm, Z-up) + uint32 indices.
    Returns (layout [{name, hex, nv, nt}], bytes). Parsing a 13 MB 3MF in the browser took ~5 s on a
    desktop (main-thread freeze); this builds in milliseconds."""
    import fast_simplification
    total = sum(len(f) for _, _, _, f in parts) or 1
    ratio = min(1.0, max_tris / total)
    layout, blobs = [], []
    for name, rgb, v, f in parts:
        if ratio < 1.0 and len(f) > 2000:
            try:
                v2, f2 = fast_simplification.simplify(np.ascontiguousarray(v, np.float32), np.ascontiguousarray(f, np.int32),
                                                      target_reduction=1 - ratio, agg=5)
                if len(f2):
                    v, f = v2, f2
            except Exception as exc:  # preview only: keep the full part
                log.warning("preview decimation skipped: %s", exc)
        v = np.ascontiguousarray(v, "<f4"); f = np.ascontiguousarray(f, "<u4")
        layout.append({"name": name, "hex": "#%02x%02x%02x" % tuple(int(c) for c in rgb), "nv": int(len(v)), "nt": int(len(f))})
        blobs += [v.tobytes(), f.tobytes()]
    return layout, b"".join(blobs)


def export_parts(parts, fmt: str) -> bytes:
    return write_3mf(parts) if fmt == "3mf" else write_glb(parts)


# --------------------------------------------------------------------------- pipeline
def process_tile(image_bytes: bytes, corners, swatches, cfg: TileConfig, progress=None, on_parts=None):
    """Full pipeline. Returns (model_bytes, stats).
    progress(fraction 0..1, message) is called at each real stage (UI progress bar); weights are
    the measured share of run time on a 150 mm tile (meshing the colour bodies dominates)."""
    def report(frac, msg):
        if progress:
            progress(round(frac, 3), msg)
    t0 = time.monotonic()
    report(0.01, "Reading photo")
    cfg.validate()
    rgb, corners_scale = decode_image(image_bytes)
    n_px = int(round(cfg.tile_size_mm * cfg.px_per_mm))
    flat = warp_tile(rgb, corners, n_px, corners_scale, inset=0.015)
    flat, sym = symmetrise(flat, cfg.symmetry)
    report(0.04, "Finding the glaze colours")

    mm_per_px = cfg.tile_size_mm / n_px
    glare_px = 0
    if cfg.remove_glare:                 # opt-in: on real photos it also erased legit white glaze (bear chest, flowers)
        flat, glare_px = remove_glare(flat, mm_per_px)
    merged = 0
    if swatches:                         # user-picked swatches are intentional: map to them, never merge
        labels, palette = quantize(flat, swatches, cfg.num_colors)
    else:                                # auto colour count, capped at num_colors
        labels, palette, merged = quantize_auto(flat, k_cap=cfg.num_colors, shade_de=cfg.merge_delta_e or 12.0)
    n = len(palette)
    labels = majority_filter(labels, n, int(round(cfg.smoothing_mm / mm_per_px)))
    labels = remove_specks(labels, n, int(cfg.min_feature_mm2 / mm_per_px ** 2),
                           keep_len_px=4.0 / mm_per_px,           # ≥ 4 mm long = outline stroke, keep
                           palette=palette, keep_de=25.0, keep_min_px=int(1.0 / mm_per_px ** 2))
    labels, glare_islands = absorb_glare_islands(labels, palette, mm_per_px)   # highlight holes on glossy glaze
    report(0.10, "Tracing raised outlines")

    # tube-lining outlines, found on the photo itself (not on the colour clusters): high-contrast ones
    # snap to an existing glaze colour, all of them become a raised ridge in the geometry
    ridge_dist, snapped = None, 0
    if cfg.outline_height_mm > 0:
        ridge_dist, comps = detect_outlines(flat, mm_per_px)
        labels, snapped = snap_outline_colours(labels, palette, flat, comps)

    # drop palette entries nobody uses
    used = np.unique(labels)
    if len(used) < n:
        remap = np.full(n, -1, np.int32)
        remap[used] = np.arange(len(used))
        labels, palette = remap[labels], palette[used]
    t1 = time.monotonic()

    report(0.14, "Shaping the relief")
    n_bodies = len(np.unique(labels))
    done = [0]
    def body_done(_):
        done[0] += 1
        report(0.22 + 0.66 * done[0] / max(n_bodies, 1), f"Carving colour {done[0]} of {n_bodies}")
    parts, stats = build_relief(labels, palette, cfg, ridge_dist, progress=body_done)
    if on_parts:                         # e.g. stream a light preview mesh before the slow file export
        on_parts(parts, stats)
    report(0.90, "Writing the 3D file")
    t2 = time.monotonic()
    data = export_parts(parts, cfg.output_format)
    t3 = time.monotonic()

    stats.update({
        "raster_px": n_px,
        "symmetry": sym,
        "merged_shading_bands": merged,
        "glare_px_inpainted": glare_px,
        "glare_islands_absorbed": glare_islands,
        "outlines_snapped": snapped,
        "config": asdict(cfg),
        "timing_s": {"image": round(t1 - t0, 2), "mesh": round(t2 - t1, 2), "export": round(t3 - t2, 2)},
        "bytes": len(data),
    })
    return data, stats


def warm_up():
    """Import the heavy modules once so the first request doesn't pay for it."""
    import fast_simplification  # noqa: F401
    import skimage.measure  # noqa: F401
    import trimesh  # noqa: F401
    pad_mesh(150.0, 3.0, 2.0)
