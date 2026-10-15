"""One-image results table: for each fixture tile, its source photo (cropped to the glaze corners) next to
the 3D render from the app. Usage: python tests/make_table.py <renders_dir> <out.jpg>"""
import json, os, sys
import cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "fixtures", "real_tiles")
C = json.load(open(os.path.join(D, "corners.json"), encoding="utf-8"))
R, OUT = sys.argv[1], sys.argv[2]
S = 300                                    # cell size (px)
INK, MUTE, LINE, PAPER = (23, 26, 28), (106, 112, 119), (218, 225, 230), (245, 248, 250)

def photo(nm):
    f, c = C[nm]; im = cv2.imread(os.path.join(D, nm + ".jpg")); p = np.float32(c) * im.shape[1] / 2048
    return cv2.warpPerspective(im, cv2.getPerspectiveTransform(p, np.float32([[0, 0], [S - 1, 0], [S - 1, S - 1], [0, S - 1]])), (S, S))

def render(nm):
    im = cv2.imread(os.path.join(R, f"user_{nm}.png")); h, w = im.shape[:2]
    bg = np.median(np.concatenate([im[:, :20], im[:, -20:]], 1), axis=1)       # per-row backdrop (gradient)
    m = (np.abs(im.astype(int) - bg[:, None].astype(int)).sum(2) > 45).astype(np.uint8)
    m[:int(h * .08)] = 0; m[int(h * .9):] = 0                                  # header / stats text
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    k = 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])                                   # the model
    ys, xs = np.nonzero(lab == k)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    side = max(y1 - y0, x1 - x0) + 20; cy, cx = (y0 + y1) // 2, (x0 + x1) // 2
    pad = cv2.copyMakeBorder(im, side, side, side, side, cv2.BORDER_REPLICATE)
    crop = pad[cy - side // 2 + side: cy + side // 2 + side, cx - side // 2 + side: cx + side // 2 + side]
    return cv2.resize(crop, (S, S), interpolation=cv2.INTER_AREA)

def text(img, s, org, scale, col, th=1):
    cv2.putText(img, s, org, cv2.FONT_HERSHEY_SIMPLEX, scale, col, th, cv2.LINE_AA)

names = list(C)
pairs_per_row, gap = 2, 14
cell_w = 2 * S + 6
row_h = S + 34
W = pairs_per_row * cell_w + (pairs_per_row + 1) * gap
rows = (len(names) + pairs_per_row - 1) // pairs_per_row
H = 70 + rows * (row_h + gap) + gap
img = np.full((H, W, 3), PAPER[::-1], np.uint8)
text(img, "tw-tile-gen  -  16 real tiles: source photo | generated 3D relief (150 mm, 15 mm base)", (gap, 34), 0.75, INK[::-1], 2)
text(img, "left: owner's photo, cropped to the chosen corners  |  right: the app's 3D preview of the generated .3MF", (gap, 58), 0.5, MUTE[::-1])
for i, nm in enumerate(names):
    r, c = divmod(i, pairs_per_row)
    x = gap + c * (cell_w + gap); y = 70 + gap + r * (row_h + gap)
    cv2.rectangle(img, (x - 1, y - 1), (x + cell_w, y + row_h), LINE[::-1], 1)
    text(img, nm.replace("_", " ", 1).replace("_", " "), (x + 8, y + 22), 0.55, INK[::-1], 1)
    text(img, "photo", (x + S - 52, y + 22), 0.42, MUTE[::-1]); text(img, "3D relief", (x + 2 * S - 70, y + 22), 0.42, MUTE[::-1])
    img[y + 32:y + 32 + S, x:x + S] = photo(nm)
    img[y + 32:y + 32 + S, x + S + 6:x + 2 * S + 6] = render(nm)
cv2.imwrite(OUT, img, [cv2.IMWRITE_JPEG_QUALITY, 88])
print(OUT, img.shape)
