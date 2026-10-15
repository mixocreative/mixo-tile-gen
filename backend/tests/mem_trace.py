"""Peak-memory trace per pipeline stage (Linux /proc). Usage: python tests/mem_trace.py <tile>"""
import json, os, sys, time, functools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, tile_processor as tp
def mem():
    d = dict(l.split(":", 1) for l in open("/proc/self/status") if l.startswith(("VmRSS", "VmHWM")))
    return {k: int(v.split()[0]) // 1024 for k, v in d.items()}
def wrap(name):
    fn = getattr(tp, name)
    @functools.wraps(fn)
    def w(*a, **k):
        r = fn(*a, **k); m = mem(); print(f"after {name:22s} RSS {m['VmRSS']:5d} MB  peak {m['VmHWM']:5d} MB", flush=True); return r
    setattr(tp, name, w)
for n in ["quantize_auto", "detect_outlines", "seam_field", "partition_fields", "cushion_body_mesh", "_decimate", "pad_mesh", "export_parts"]:
    wrap(n)
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "real_tiles", "originals")
C = json.load(open(os.path.join(D, "..", "corners.json"))); nm = sys.argv[1]; c = C[nm]
data = open(os.path.join(D, nm + ".jpg"), "rb").read(); rgb, s = tp.decode_image(data); w = rgb.shape[1] / s
print("start", mem())
res = float(os.environ.get("RES", 0.12))
tp.process_tile(data, c, None, tp.TileConfig(mesh_resolution_mm=res)); print("end", mem())
