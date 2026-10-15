"""Debug: build bodies with and without decimation and report watertightness."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, trimesh
import tile_processor as tp

img = open(os.path.join(os.path.dirname(__file__), "sample_tile.jpg"), "rb").read()
corners = [[380, 160], [1260, 210], [1220, 1080], [330, 1010]]
sw = [[236, 228, 208], [40, 70, 150], [60, 140, 80], [230, 140, 120], [245, 205, 70], [180, 40, 50]]
orig = tp._decimate
for label, dec in (("no-decimate", lambda v, f, target_faces: (v, f)), ("decimate", orig)):
    tp._decimate = dec
    captured = []
    real = tp.export_parts
    tp.export_parts = lambda parts, fmt: captured.extend(parts) or b""
    tp.process_tile(img, corners, sw, tp.TileConfig())
    tp.export_parts = real
    for name, _, v, f in captured:
        m = trimesh.Trimesh(v, f, process=False)
        if not m.is_watertight:
            edges = trimesh.grouping.group_rows(m.edges_sorted, require_count=1)
            print(f"{label:12s} {name:18s} NOT watertight  tris={len(f)} open_edges={len(edges)}")
    print(label, "checked", len(captured), "parts")
