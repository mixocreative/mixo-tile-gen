"""Generate a synthetic 'phone photo' of a majolica-style tile (perspective + noise) for testing."""
import sys
import cv2
import numpy as np

N = 900
tile = np.full((N, N, 3), (236, 228, 208), np.uint8)              # cream glaze ground (RGB)
c = N // 2
cv2.rectangle(tile, (20, 20), (N - 21, N - 21), (40, 70, 150), 28)   # cobalt border
for dx, dy in [(1, 1), (-1, 1), (1, -1), (-1, -1)]:                  # green corner leaves
    cv2.ellipse(tile, (c + dx * 290, c + dy * 290), (110, 45), 45 * dx * dy, 0, 360, (60, 140, 80), -1)
cv2.circle(tile, (c, c), 230, (40, 70, 150), -1)                      # cobalt medallion
for k in range(8):                                                    # peach petals
    a = k * np.pi / 4
    cv2.ellipse(tile, (int(c + 120 * np.cos(a)), int(c + 120 * np.sin(a))), (85, 38),
                np.degrees(a), 0, 360, (230, 140, 120), -1)
cv2.circle(tile, (c, c), 55, (245, 205, 70), -1)                      # yellow centre
cv2.circle(tile, (c, c), 22, (180, 40, 50), -1)                       # red dot

W, H = 1600, 1200
photo = np.full((H, W, 3), (90, 80, 70), np.uint8)
dst = np.float32([[380, 160], [1260, 210], [1220, 1080], [330, 1010]])
src = np.float32([[0, 0], [N - 1, 0], [N - 1, N - 1], [0, N - 1]])
M = cv2.getPerspectiveTransform(src, dst)
photo = cv2.warpPerspective(tile, M, (W, H), dst=photo, borderMode=cv2.BORDER_TRANSPARENT)
rng = np.random.default_rng(1)
photo = np.clip(photo.astype(np.int16) + rng.normal(0, 7, photo.shape).astype(np.int16), 0, 255).astype(np.uint8)
cv2.imwrite(sys.argv[1] if len(sys.argv) > 1 else "sample_tile.jpg", cv2.cvtColor(photo, cv2.COLOR_RGB2BGR),
            [cv2.IMWRITE_JPEG_QUALITY, 88])
print("corners:", dst.tolist())
