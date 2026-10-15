"""Run the pipeline directly (no HTTP) on tests/sample_tile.jpg, write tests/out/, check every body is watertight."""
import io, json, os, sys, time, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import tile_processor as tp

here = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(here, "out"), exist_ok=True)
img = open(os.path.join(here, "sample_tile.jpg"), "rb").read()
corners = [[380, 160], [1260, 210], [1220, 1080], [330, 1010]]
swatches = None if "--kmeans" in sys.argv else [[236, 228, 208], [40, 70, 150], [60, 140, 80], [230, 140, 120], [245, 205, 70], [180, 40, 50]]
radius = tp.TileConfig.fillet_radius_mm
for fmt in ("3mf", "glb"):
    t = time.time()
    cfg = tp.TileConfig(output_format=fmt, num_colors=6, fillet_radius_mm=radius)
    data, stats = tp.process_tile(img, corners, swatches, cfg)
    open(os.path.join(here, "out", f"sample.{fmt}"), "wb").write(data)
    stats.pop("config"); stats.pop("colours")
    print(fmt, f"{time.time()-t:.1f}s", json.dumps(stats))

import trimesh
scene = trimesh.load(os.path.join(here, "out", "sample.glb"), process=False)
for name, g in scene.geometry.items():
    print(f"  {name:22s} tris={len(g.faces):7d} watertight={g.is_watertight} winding_ok={g.is_winding_consistent} vol_cm3={g.volume*1e6:8.2f}")
