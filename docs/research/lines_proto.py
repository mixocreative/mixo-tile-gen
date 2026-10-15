"""Tube-line detection independent of colour clustering: multi-scale Sato ridge filter on L
(bright ridges) and on -L (dark ridges) at 6 px/mm, hysteresis + length filter, crazing/glare rejection."""
import os, sys, json, time, numpy as np, cv2
sys.path.insert(0, "S:/ai/twtile/backend")
import tile_processor as tp
from skimage.filters import sato, apply_hysteresis_threshold
from skimage.morphology import skeletonize, remove_small_objects

USER = "S:/ai/twtile/backend/tests/out/user/"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "")
N_PX = 450; SIZE = 150.0; MMPP = SIZE / N_PX


def load(name, n=N_PX):
    img = cv2.cvtColor(cv2.imread(USER + name + ".jpg"), cv2.COLOR_BGR2RGB)
    c = json.load(open(USER + "corners.json"))[name][1]
    sc = img.shape[1] / 2048
    return tp.warp_tile(img, [[x * sc, y * sc] for x, y in c], n, 1.0, inset=0.015)


def detect_lines(rgb: np.ndarray, mm_per_px: float, max_width_mm=2.0, hi=10.0, lo=5.0,
                 min_len_mm=4.0, min_width_mm=0.4):
    """Returns (bright_mask, dark_mask) at the input raster. Runs at 2x resolution.
    Primitive = morphological top-hat / black-hat of L with a disc wider than any tube-line:
    it responds ONLY to structures thinner than the disc in every direction, so colour step edges
    (which fooled Sato/Frangi) and wide glare blobs give zero. Hysteresis keeps faint but connected
    lines (cream on white), an opening kills 1-px crazing, a skeleton-length filter kills specks."""
    up = 2
    big = cv2.resize(rgb, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
    L = tp._rgb_to_lab(cv2.bilateralFilter(big, 5, 25, 3))[..., 0].astype(np.float32)
    px = mm_per_px / up
    r = int(round(max_width_mm / 2 / px))
    disc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (max(2, int(round(min_width_mm / px))),) * 2)
    out = []
    for resp in (L - cv2.morphologyEx(L, cv2.MORPH_OPEN, disc), cv2.morphologyEx(L, cv2.MORPH_CLOSE, disc) - L):
        resp = cv2.GaussianBlur(resp, (0, 0), 0.7)
        m = apply_hysteresis_threshold(resp, lo, hi)
        m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, k_open).astype(bool)     # crazing is 1 px
        sk = skeletonize(m)
        n, cc, st, _ = cv2.connectedComponentsWithStats(sk.astype(np.uint8), connectivity=8)
        keep = np.zeros(n, bool); keep[1:] = st[1:, cv2.CC_STAT_AREA] * px >= min_len_mm
        nm_, mc = cv2.connectedComponents(m.astype(np.uint8), connectivity=8)
        good = np.zeros(nm_, bool); good[np.unique(mc[keep[cc]])] = True; good[0] = False
        m = good[mc]                                                   # whole components that own a long skeleton
        out.append(cv2.resize(m.astype(np.uint8), (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_AREA) > 0.4)
    return out[0], out[1]


def inject_lines(labels, palette, rgb, bright, dark, de_new=18.0, de_snap=14.0):
    """Per connected line: (a) if its median colour differs from the region it sits in by more than
    de_new (CIE76) it becomes a colour region (snapped to an existing palette colour within de_snap,
    else a new palette entry); (b) otherwise it is a pure geometry ridge (mask returned; build_relief
    raises a bead along it inside whatever colour body it lies in)."""
    lab_img = tp._rgb_to_lab(rgb)
    geom = np.zeros(labels.shape, bool)
    for m in (bright, dark):
        n, cc = cv2.connectedComponents(m.astype(np.uint8), connectivity=8)
        for i in range(1, n):
            sel = cc == i
            pal_lab = tp._rgb_to_lab(palette[None])[0]
            col = np.median(lab_img[sel], axis=0)
            host = np.bincount(labels[sel]).argmax()
            if np.linalg.norm(pal_lab[host] - col) > de_new:
                de = np.linalg.norm(pal_lab - col, axis=1)
                j = int(de.argmin())
                if de[j] <= de_snap and j != host:              # snap to an existing glaze colour only
                    labels = np.where(sel, j, labels).astype(np.int32)
                else:
                    geom |= sel
            else:
                geom |= sel
    return labels, palette, geom


if __name__ == "__main__":
    names = sys.argv[1:] or ["09_single_rose", "16_purple_sunflower", "04_star_75", "02_sunflower", "06_lion_peony"]
    rows = []
    for nm in names:
        flat = load(nm)
        t0 = time.time(); b, d = detect_lines(flat, MMPP); t1 = time.time()
        res = tp.quantize_auto(flat)
        labels, pal = res[0], res[1]
        n = len(pal)
        labels = tp.majority_filter(labels, n, int(round(0.5 / MMPP)))
        labels = tp.remove_specks(labels, n, int(2.0 / MMPP ** 2), keep_len_px=4.0 / MMPP)
        before = pal[labels]
        l2, p2, geom = inject_lines(labels, pal, flat, b, d)
        after = p2[l2].copy()
        after[geom] = (after[geom] * 0.6).astype(np.uint8)          # geometry-only ridges shown darkened
        ov = flat.copy(); ov[b] = (255, 0, 255); ov[d] = (0, 255, 255)
        print(f"{nm}: detect {t1-t0:.2f}s  bright {b.mean()*100:.1f}%  dark {d.mean()*100:.1f}%  "
              f"new colours {len(p2)-len(pal)}  geometry-ridge px {int(geom.sum())}")
        row = np.hstack([cv2.copyMakeBorder(x, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(255, 255, 255))
                         for x in (flat, ov, before, after)])
        cv2.putText(row, f"{nm}: photo | ridges (magenta=bright, cyan=dark) | labels before | after (dark=geometry ridge)",
                    (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        rows.append(row)
    cv2.imwrite(OUT + "lines_before_after.png", cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR))
