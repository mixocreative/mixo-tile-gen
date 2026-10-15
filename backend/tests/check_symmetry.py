"""Which tiles does auto-symmetry accept? Sample tile must pass; asymmetric real tiles must not."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, tile_processor as tp
here = os.path.dirname(os.path.abspath(__file__))
cases = {
    "sample_tile.jpg": [[380, 160], [1260, 210], [1220, 1080], [330, 1010]],
    "out/real/C_fruit_darkblue.jpg": [[64, 198], [586, 181], [591, 720], [67, 718]],
    "out/real/D_camellia.jpg": [[86, 161], [549, 158], [556, 623], [83, 631]],
}
for f, c in cases.items():
    rgb, s = tp.decode_image(open(os.path.join(here, f), "rb").read())
    flat = tp.warp_tile(rgb, c, 600, s)
    lab = tp._rgb_to_lab(flat)
    for g in ("d4", "c4"):
        r = [lab, np.rot90(lab, 1), np.rot90(lab, 2), np.rot90(lab, 3)]
        grp = r if g == "c4" else r + [x[:, ::-1] for x in r]
        e = np.linalg.norm(np.mean(grp, 0) - lab, axis=-1)
        print(f"{f:32s} {g}: mean dE {e.mean():5.1f}  frac>20 {(e > 20).mean():.3f}")
    print("   -> auto picks:", tp.symmetrise(flat, "auto")[1])
