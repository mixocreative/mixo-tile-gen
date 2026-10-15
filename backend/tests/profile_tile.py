"""Time each stage of the pipeline for one fixture tile. Usage: python tests/profile_tile.py <tile>"""
import json, os, sys, time, cProfile, pstats, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, tile_processor as tp
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "real_tiles")
C = json.load(open(os.path.join(D, "corners.json")))
nm = sys.argv[1]; f, c = C[nm]; data = open(os.path.join(D, nm + ".jpg"), "rb").read()
rgb, s = tp.decode_image(data); w = rgb.shape[1] / s
PROF = bool(os.environ.get("PROF")); pr = cProfile.Profile(); t = time.time()
if PROF: pr.enable()
out, st = tp.process_tile(data, (np.float32(c) * w / 2048).tolist(), None, tp.TileConfig())
if PROF: pr.disable()
import resource
print(nm, f"peakRSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024:.0f}MB", f"total {time.time()-t:.1f}s", st["timing_s"], "MB", round(len(out)/1e6, 1), "tris", st["triangles"])
if PROF:
  print(sio.getvalue()[-6000:])
