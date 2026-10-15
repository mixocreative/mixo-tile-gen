"""Real-photo colour->region improvements, prototype. Produces photo | current labels | new labels sheets."""
import os, sys, json, time, numpy as np, cv2
sys.path.insert(0, "S:/ai/twtile/backend")
import tile_processor as tp
from sklearn.cluster import KMeans

USER = "S:/ai/twtile/backend/tests/out/user/"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "")
N_PX = 450; SIZE = 150.0; MMPP = SIZE / N_PX


# ----------------------------------------------------------------------------- new building blocks
def remove_glare(rgb: np.ndarray, mm_per_px: float, max_frac: float = 0.03, min_fat_mm: float = 1.5) -> tuple[np.ndarray, np.ndarray]:
    """Specular highlights and paper stickers: very light, almost grey, compact (not thin tube-lines),
    small compared with the tile. Inpaint them from their surroundings before quantising."""
    lab = tp._rgb_to_lab(rgb)
    L, chroma = lab[..., 0], np.hypot(lab[..., 1], lab[..., 2])
    r = int(round(6.0 / mm_per_px))
    disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    local = L.astype(np.float32) - cv2.morphologyEx(L.astype(np.float32), cv2.MORPH_OPEN, disc)
    cand = ((L > 80) & (chroma < 16) & (local > 14)).astype(np.uint8)
    cand = cv2.morphologyEx(cand, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, cc, stats, _ = cv2.connectedComponentsWithStats(cand, connectivity=8)
    dist = cv2.distanceTransform(cand, cv2.DIST_L2, 5) * mm_per_px
    mask = np.zeros(rgb.shape[:2], np.uint8)
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        if area > max_frac * cand.size:           # a white ground, not glare
            continue
        sel = cc == i
        if dist[sel].max() < min_fat_mm:          # thin = tube line, keep
            continue
        mask[sel] = 1
    if mask.any():
        mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
        rgb = cv2.inpaint(rgb, mask, 5, cv2.INPAINT_TELEA)
    return rgb, mask


def flatten_shading(rgb: np.ndarray, sp: int = 7, sr: int = 22) -> np.ndarray:
    """Mean-shift: flattens painted shading / photo gradients inside one glaze while keeping edges."""
    return cv2.pyrMeanShiftFiltering(rgb, sp, sr)


def quantize_auto(rgb: np.ndarray, k_max: int = 12, l_weight: float = 0.5, min_de: float = 14.0,
                  shared: float = 0.15, k_min: int = 3):
    """Over-segment in L-down-weighted Lab (hue/chroma dominate so shading doesn't split a glaze),
    then merge: first touching pairs within ΔE 12, then the globally closest pair while the closest
    pair is still < min_de (auto-k). Returns labels, palette."""
    lab = tp._rgb_to_lab(rgb)
    w = np.array([l_weight, 1.0, 1.0], np.float32)
    feat = (lab * w).reshape(-1, 3)
    rs = np.random.default_rng(0)
    sample = feat[rs.choice(len(feat), size=min(len(feat), 30000), replace=False)]
    km = KMeans(n_clusters=k_max, n_init=3, random_state=0).fit(sample)
    cen = km.cluster_centers_
    labels = ((feat[:, None, :] - cen[None]) ** 2).sum(-1).argmin(1).astype(np.int32).reshape(rgb.shape[:2])
    pal = tp._lab_to_rgb((cen / w).astype(np.float32))
    labels, pal, m1 = tp.merge_shading_bands(labels, pal, 12.0, shared, max_colors=None)
    # auto-k: keep merging the closest pair while it is closer than min_de (and k > k_min)
    while len(pal) > k_min:
        labn, paln, m = tp.merge_shading_bands(labels, pal, 0.0, shared, max_colors=len(pal) - 1)
        li = tp._rgb_to_lab(pal[None])[0] * w
        pairs = [np.linalg.norm(li[i] - li[j]) for i in range(len(pal)) for j in range(i + 1, len(pal))]
        if min(pairs) >= min_de:
            break
        labels, pal = labn, paln
    return labels, pal


def extract_lines(rgb: np.ndarray, mm_per_px: float, width_mm: float = 2.5, min_len_mm: float = 5.0,
                  thresh: float = 9.0) -> np.ndarray:
    """Light tube-lining: thin bright ridges in L (white top-hat with a disc wider than the line),
    elongated. Returns a uint8 mask. Thin dark contour lines: black-hat (same way)."""
    L = tp._rgb_to_lab(rgb)[..., 0].astype(np.float32)
    r = max(2, int(round(width_mm / mm_per_px)))
    disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    top = L - cv2.morphologyEx(L, cv2.MORPH_OPEN, disc)
    mask = (top > thresh).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    n, cc, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    keep = np.zeros(n, bool)
    length = np.maximum(stats[:, cv2.CC_STAT_WIDTH], stats[:, cv2.CC_STAT_HEIGHT]) * mm_per_px
    keep[1:] = length[1:] >= min_len_mm
    return keep[cc].astype(np.uint8)


# ----------------------------------------------------------------------------- pipelines
def load(name):
    img = cv2.cvtColor(cv2.imread(USER + name + ".jpg"), cv2.COLOR_BGR2RGB)
    corners = json.load(open(USER + "corners.json"))[name][1]
    sc = img.shape[1] / 2048
    pts = [[x * sc, y * sc] for x, y in corners]
    return tp.warp_tile(img, pts, N_PX, 1.0, inset=0.015)


def finish(labels, pal):
    n = len(pal)
    labels = tp.majority_filter(labels, n, int(round(0.5 / MMPP)))
    labels = tp.remove_specks(labels, n, int(2.0 / MMPP ** 2), keep_len_px=4.0 / MMPP)
    used = np.unique(labels); remap = np.full(n, -1, np.int32); remap[used] = np.arange(len(used))
    return remap[labels], pal[used]


def current(flat):
    flat, _ = tp.symmetrise(flat, "auto")
    labels, pal = tp.quantize(flat, None, 12)
    labels, pal, _ = tp.merge_shading_bands(labels, pal, 12.0, max_colors=6)
    return finish(labels, pal)


def current_ms(flat):
    flat, _ = tp.symmetrise(flat, "auto")
    flat, _ = remove_glare(flat, MMPP)
    labels, pal = tp.quantize(flatten_shading(flat), None, 12)
    labels, pal, _ = tp.merge_shading_bands(labels, pal, 12.0, max_colors=6)
    return finish(labels, pal)


def improved(flat, lines=False):
    t = {}
    t0 = time.time(); flat, _ = tp.symmetrise(flat, "auto")
    flat, glare = remove_glare(flat, MMPP); t["glare"] = time.time() - t0
    t0 = time.time(); fl = flatten_shading(flat); t["meanshift"] = time.time() - t0
    t0 = time.time(); labels, pal = quantize_auto(fl); t["quantize_auto"] = time.time() - t0
    if lines:
        t0 = time.time(); lm = extract_lines(flat, MMPP)
        if lm.sum() > 0.002 * lm.size:
            col = np.median(flat[lm.astype(bool)], axis=0).astype(np.uint8)
            labels = np.where(lm > 0, len(pal), labels).astype(np.int32)
            pal = np.vstack([pal, col[None]])
        t["lines"] = time.time() - t0
    return finish(labels, pal), t, glare


def paint(labels, pal):
    return pal[labels]


if __name__ == "__main__":
    names = sys.argv[1:] or ["02_sunflower", "06_lion_peony", "07_chrysanthemum", "08_rose_octagon",
                             "10_star_61", "13_bear", "14_leopard_cat", "15_green_lattice"]
    rows = []
    for nm in names:
        flat = load(nm)
        lc, pc = current(flat)
        (li, pi), t, glare = improved(flat)
        print(f"{nm}: current k={len(pc)}  new k={len(pi)}  glare px={int(glare.sum())}  "
              + " ".join(f"{k}={v:.2f}s" for k, v in t.items()))
        lm_, pm_ = current_ms(flat)
        tiles = [flat, paint(lc, pc), paint(lm_, pm_), paint(li, pi)]
        row = np.hstack([cv2.copyMakeBorder(x, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for x in tiles])
        cv2.putText(row, f"{nm}  photo | current | current+glare+meanshift k=6 | autok+Lweight k={len(pi)}", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        rows.append(row)
    sheet = np.vstack(rows)
    cv2.imwrite(OUT + "photo_before_after.png", cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
