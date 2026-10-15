"""Print the final palette for the real test tiles (quick colour-step check, no meshing)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, tile_processor as tp
here = os.path.dirname(os.path.abspath(__file__))
cases = {"out/real/C_fruit_darkblue.jpg": [[64, 198], [586, 181], [591, 720], [67, 718]],
         "out/real/D_camellia.jpg": [[86, 161], [549, 158], [556, 623], [83, 631]],
         "out/real/B_peony.jpg": [[194, 215], [689, 212], [695, 690], [198, 695]]}
cfg = tp.TileConfig().validate()
for f, c in cases.items():
    rgb, s = tp.decode_image(open(os.path.join(here, f), "rb").read())
    flat = tp.warp_tile(rgb, c, 600, s, inset=0.015)
    labels, pal = tp.quantize(flat, None, 12)
    labels, pal, m = tp.merge_shading_bands(labels, pal, 12, max_colors=6)
    cov = np.bincount(labels.ravel(), minlength=len(pal)) / labels.size
    print(f, "merged", m, " ".join("#%02x%02x%02x:%.0f%%" % (*p, 100 * cv) for p, cv in zip(pal, cov)))
