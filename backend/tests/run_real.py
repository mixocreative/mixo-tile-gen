"""Full pipeline (no HTTP) on a few real tiles; checks every body is watertight."""
import json, os, sys, io, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, trimesh, tile_processor as tp
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "real_tiles")   # permanent fixture set
C = json.load(open(os.path.join(D, "corners.json")))
for nm in (sys.argv[1:] or sorted(C)):       # no args = all 16 fixture tiles
    f, c = C[nm]; data = open(os.path.join(D, nm + ".jpg"), "rb").read()
    w = tp.decode_image(data)[0].shape[1] / tp.decode_image(data)[1]
    t = time.time(); glb, st = tp.process_tile(data, (np.float32(c) * w / 2048).tolist(), None, tp.TileConfig(output_format="glb"))
    sc = trimesh.load(io.BytesIO(glb), file_type="glb", process=False)
    bad = [n for n, g in sc.geometry.items() if not g.is_watertight]
    print(f"{nm:22s} {time.time()-t:5.1f}s bodies={st['bodies']} tris={st['triangles']} watertight={'ALL' if not bad else 'BAD ' + str(bad)}")
