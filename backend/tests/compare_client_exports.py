"""Compare the files the BROWSER wrote (frontend/index.html) with the SERVER writers (tile_processor.py).

    python tests/compare_client_exports.py --browser <dir or mixotile_*mm.zip> --server <dir> --req req.json

--req    JSON {"fields": {<the multipart form fields the page sent>}, "image_b64": "<the uploaded photo>"}
         (captured from the page; see the test notes). The server files are made with
         tile_processor.process_tile(output_format="bundle") from exactly that request, unless --server
         already holds a bundle (mixotile_*mm.zip or the extracted files), which is then reused.
Per format it checks the one-model/root contract, material regions, bounding boxes (<= 0.002 mm),
the 3MF extruder table, texture presence, and UV-vs-position error.
Exit code 0 = everything within tolerance.
"""
import argparse, base64, glob, io, json, os, re, struct, sys, zipfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOL = 0.002
RES = []


def check(ok, what, detail=""):
    RES.append(ok)
    print(("  PASS " if ok else "  FAIL ") + what + (f"  [{detail}]" if detail else ""))


def extract(src, dst):
    """src = folder (maybe holding a bundle .zip) or a bundle .zip. Returns the folder with the bundle's files."""
    if os.path.isfile(src) and src.lower().endswith(".zip"):
        zs = [src]
    else:
        zs = glob.glob(os.path.join(src, "mixotile_*mm.zip"))
    if not zs:
        return src
    os.makedirs(dst, exist_ok=True)
    with zipfile.ZipFile(zs[0]) as z:
        z.extractall(dst)
    return dst


def swatches_of(f):
    """["#rrggbb", ...] -> [[r,g,b], ...] like main._parse_swatches"""
    if not f.get("swatches"):
        return None
    return [[int(h[i:i + 2], 16) for i in (1, 3, 5)] if isinstance(h, str) else h for h in json.loads(f["swatches"])]


def find(folder, pattern):
    hits = sorted(glob.glob(os.path.join(folder, pattern)))
    return hits[0] if hits else None


# ------------------------------------------------------------------ readers
def read_3mf(path):
    z = zipfile.ZipFile(path)
    names = z.namelist()
    raw = z.read("3D/3dmodel.model")
    cfg = z.read("Metadata/Slic3r_PE_model.config").decode()
    vols = re.findall(r'<volume firstid="(\d+)" lastid="(\d+)">.*?key="name" value="([^"]*)".*?key="extruder" value="(\d+)"', cfg, re.S)
    vs, ve = raw.index(b"<vertices>") + 10, raw.index(b"</vertices>")
    txt = raw[vs:ve].replace(b'<vertex x="', b"").replace(b'" y="', b" ").replace(b'" z="', b" ").replace(b'"/>', b"")
    V = np.array(txt.split(), dtype=np.float64).reshape(-1, 3)
    ts, te = raw.index(b"<triangles>") + 11, raw.index(b"</triangles>")
    tt = raw[ts:te]
    tex = b'pid="4"' in tt
    lines = tt.split(b"\n")
    lines = [l for l in lines if l.startswith(b"<triangle")]
    F = np.array([[int(m) for m in re.findall(rb'v[123]="(\d+)"', l)] for l in lines], dtype=np.int64)
    pid4 = np.array([b'pid="4"' in l for l in lines])
    P = None
    uv = None
    if tex:
        g0 = raw.index(b'<m:texture2dgroup')
        g1 = raw.index(b"</m:texture2dgroup>")
        seg = raw[g0:g1]
        seg = seg[seg.index(b">") + 1:].replace(b'<m:tex2coord u="', b"").replace(b'" v="', b" ").replace(b'"/>', b"")
        uv = np.array(seg.split(), dtype=np.float64).reshape(-1, 2)
    parts = []
    for lo, hi, nm, ex in vols:
        lo, hi = int(lo), int(hi)
        f = F[lo:hi + 1]
        used = np.unique(f)
        parts.append({"name": nm, "extruder": int(ex), "nt": hi - lo + 1, "nv": len(used),
                      "bbox": np.array([V[used].min(0), V[used].max(0)]), "verts": used})
    return {"parts": parts, "V": V, "F": F, "uv": uv, "texture": "3D/Textures/texture.jpg" in names, "tex_group": tex,
            "one_model": len(re.findall(rb'<object id="\d+" type="model"(?:\s|>)', raw)) == 1,
            "base_count": len(re.findall(rb'<base name="[^"]+" displaycolor="#[0-9A-F]{8}"/>', raw)),
            "materials_required": b'requiredextensions="m"' in raw,
            "texture_rel": "3D/_rels/3dmodel.model.rels" in names,
            "zip_descriptors": any(i.flag_bits & 8 for i in z.infolist()), "nV": len(V), "nT": len(F)}


def read_obj(folder):
    obj = open(os.path.join(folder, "model.obj"), encoding="ascii").read().split("\n")
    parts, cur = [], None
    allv, allvt = [], []
    for ln in obj:
        if ln.startswith("g "):
            cur = {"name": ln[2:], "v0": len(allv), "vt0": len(allvt), "nf": 0}
            parts.append(cur)
        elif ln.startswith("v "):
            allv.append(ln[2:])
        elif ln.startswith("vt "):
            allvt.append(ln[3:])
        elif ln.startswith("f "):
            cur["nf"] += 1
    V = np.array(" ".join(allv).split(), dtype=np.float64).reshape(-1, 3)
    VT = np.array(" ".join(allvt).split(), dtype=np.float64).reshape(-1, 2) if allvt else None
    for i, p in enumerate(parts):
        v1 = parts[i + 1]["v0"] if i + 1 < len(parts) else len(V)
        sl = V[p["v0"]:v1]
        p.update(nv=len(sl), nt=p["nf"], bbox=np.array([sl.min(0), sl.max(0)]))
    return {"parts": parts, "V": V, "VT": VT, "root_count": sum(ln == "o MixoTile relief" for ln in obj), "mtl": os.path.exists(os.path.join(folder, "model.mtl")),
            "texture": os.path.exists(os.path.join(folder, "texture.jpg"))}


def read_stl(path):
    b = open(path, "rb").read()
    n = int(np.frombuffer(b[80:84], "<u4")[0])
    rec = np.frombuffer(b[84:84 + 50 * n], np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))
    tri = rec["v"].reshape(-1, 3)
    return {"nt": n, "nv": len(np.unique(tri, axis=0)), "bbox": np.array([tri.min(0), tri.max(0)]).astype(np.float64)}


def read_glb(path):
    raw = open(path, "rb").read()
    n, kind = struct.unpack_from("<I4s", raw, 12); assert kind == b"JSON"
    doc = json.loads(raw[20:20 + n])
    return {"nodes": len(doc["nodes"]), "meshes": len(doc["meshes"]), "primitives": len(doc["meshes"][0]["primitives"]),
            "materials": [m["name"] for m in doc["materials"]], "texture": "images" in doc,
            "has_uv": all("TEXCOORD_0" in p["attributes"] for p in doc["meshes"][0]["primitives"] if p["material"] == 0)}


# ------------------------------------------------------------------ comparisons
def cmp_part_lists(label, A, B, key="name"):
    """A, B: lists of dicts with name, nv, nt, bbox"""
    check(len(A) == len(B), f"{label}: part count", f"browser {len(A)} / server {len(B)}")
    check([p["name"] for p in A] == [p["name"] for p in B], f"{label}: part names equal",
          "" if [p["name"] for p in A] == [p["name"] for p in B] else f"{[p['name'] for p in A]} vs {[p['name'] for p in B]}")
    nvbad = [(a["name"], a["nv"], b["nv"]) for a, b in zip(A, B) if a["nv"] != b["nv"]]
    ntbad = [(a["name"], a["nt"], b["nt"]) for a, b in zip(A, B) if a["nt"] != b["nt"]]
    check(not nvbad, f"{label}: per-part vertex counts equal", str(nvbad[:3]))
    check(not ntbad, f"{label}: per-part triangle counts equal", str(ntbad[:3]))
    d = max((float(np.abs(a["bbox"] - b["bbox"]).max()) for a, b in zip(A, B)), default=0)
    check(d <= TOL, f"{label}: bounding boxes within {TOL} mm", f"max diff {d:.5f} mm")


def uv_err_3mf(m, size):
    # tex2coord per vertex (parts concatenated in vertex order) vs clip(xy/size)
    exp = np.clip(m["V"][:, :2] / size, 0, 1)
    return float(np.abs(m["uv"] - exp).max())


ADJ = {"pad_thickness_mm": "10", "relief_height_mm": "4.5", "dome_height_mm": "2.5", "outline_height_mm": "1.6"}


def adjusted_check(a, req, srv):
    """Browser-side Apply (heights.bin) vs a real server rebuild with the same slider values. The rebuild's vertex
    layout differs (other marching-cubes levels), so compare per-part max height and a nearest-(x,y) height sample."""
    import tile_processor as tp
    from scipy.spatial import cKDTree
    print("\n== Fine-tune Apply in the browser vs a server rebuild (pad 10, relief 4.5, crown 2.5, outline 1.6)")
    f = dict(req["fields"]); f.update(ADJ)
    kw = {}
    for k, fld in tp.TileConfig.__dataclass_fields__.items():
        if k in f:
            d = fld.default
            kw[k] = (f[k] in ("true", "True")) if isinstance(d, bool) else type(d)(f[k]) if not isinstance(d, str) else f[k]
    cfg = tp.TileConfig(**kw); cfg.output_format = "3mf"
    sw = swatches_of(f)
    path = os.path.join(a.server, "rebuild_adjusted.3mf")
    if not os.path.exists(path):
        data, _ = tp.process_tile(base64.b64decode(req["image_b64"]), json.loads(f["corners"]), sw, cfg)
        open(path, "wb").write(data)
    B, S = read_3mf(a.adjusted), read_3mf(path)
    check(len(B["parts"]) == len(S["parts"]), "adjusted: part count", f"{len(B['parts'])} vs {len(S['parts'])}")
    allz = []
    rng = np.random.default_rng(1)
    for pb, ps in zip(B["parts"], S["parts"]):
        vb, vs = B["V"][pb["verts"]], S["V"][ps["verts"]]
        dmax = abs(vb[:, 2].max() - vs[:, 2].max())
        tree = cKDTree(vs[:, :2])
        sel = rng.choice(len(vb), min(20000, len(vb)), replace=False)
        dist, j = tree.query(vb[sel, :2], k=8)               # walls / the pad have several vertices on one (x,y): take the best z match
        dzs = np.abs(vb[sel, 2][:, None] - vs[j, 2])
        dzs[dist > 0.15] = np.inf                            # only rebuilt vertices within 0.15 mm in x,y count
        dzm = dzs.min(1); near = np.isfinite(dzm)
        dz = dzm[near]
        allz.append(dz)
        print(f"  {pb['name']:24s} max z browser {vb[:,2].max():7.3f}  rebuild {vs[:,2].max():7.3f}  |d|={dmax:.3f}   sample n={near.sum()} "
              f"max|dz|={dz.max() if len(dz) else float('nan'):.3f} p95={np.percentile(dz,95) if len(dz) else float('nan'):.3f} median={np.median(dz) if len(dz) else float('nan'):.3f}")
        check(dmax <= 0.3, f"adjusted: {pb['name']} max height within 0.3 mm of the rebuild", f"{dmax:.3f} mm")
    z = np.concatenate(allz)
    print(f"  ALL parts: n={len(z)} max|dz|={z.max():.3f} p95={np.percentile(z,95):.3f} median={np.median(z):.4f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser", required=True)
    ap.add_argument("--server", required=True)
    ap.add_argument("--req", required=True)
    ap.add_argument("--adjusted", help="3MF the browser wrote after Apply (pad 10, relief 4.5, crown 2.5, outline 1.6); compared with a server rebuild at those settings")
    a = ap.parse_args()
    req = json.load(open(a.req))
    size = float(req["fields"].get("tile_size_mm", 150))
    stem = f"mixotile_{int(round(size))}mm"

    bro = extract(a.browser, os.path.join(a.server, "_browser_x"))
    srv = a.server
    if not (glob.glob(os.path.join(srv, stem + ".3mf")) or glob.glob(os.path.join(srv, stem + ".zip"))):
        import tile_processor as tp
        f = req["fields"]
        kw = {}
        for k, fld in tp.TileConfig.__dataclass_fields__.items():
            if k in f:
                d = fld.default
                kw[k] = (f[k] in ("true", "True")) if isinstance(d, bool) else type(d)(f[k]) if not isinstance(d, str) else f[k]
        cfg = tp.TileConfig(**kw)
        cfg.output_format = "bundle"
        cfg.formats = ",".join(tp.BUNDLE_DEFAULT_NAMES)
        sw = swatches_of(f)
        data, st = tp.process_tile(base64.b64decode(req["image_b64"]), json.loads(f["corners"]), sw, cfg)
        os.makedirs(srv, exist_ok=True)
        open(os.path.join(srv, stem + ".zip"), "wb").write(data)
        print(f"server bundle written: {len(data)/1e6:.1f} MB, timing {st['timing_s']}")
    srv = extract(srv, os.path.join(a.server, "_server_x"))

    print(f"browser files: {sorted(os.listdir(bro))}\nserver files:  {sorted(os.listdir(srv))}")
    for tex in (False, True):
        ext = ".textured.3mf" if tex else ".3mf"
        pb, ps = os.path.join(bro, stem + ext), os.path.join(srv, stem + ext)
        print(f"\n== 3MF{' + photo' if tex else ''}")
        if not (os.path.exists(pb) and os.path.exists(ps)):
            check(False, "file present in both", f"{os.path.exists(pb)}/{os.path.exists(ps)}"); continue
        B, S = read_3mf(pb), read_3mf(ps)
        cmp_part_lists("3mf", B["parts"], S["parts"])
        check(B["nV"] == S["nV"] and B["nT"] == S["nT"], "3mf: total vertices/triangles", f"{B['nV']}/{B['nT']} vs {S['nV']}/{S['nT']}")
        check(B["one_model"] and S["one_model"] and B["base_count"] == S["base_count"], "3mf: one root with equal base materials", str(B["base_count"]))
        check(not B["zip_descriptors"] and not S["zip_descriptors"], "3mf: no ZIP data descriptors")
        check([p["extruder"] for p in B["parts"]] == [p["extruder"] for p in S["parts"]], "3mf: extruder table equal", str([p["extruder"] for p in B["parts"]]))
        if tex:
            check(B["texture"] and B["tex_group"], "3mf: texture + texture2dgroup present", f"server has {S['texture']}")
            check(B["materials_required"] and S["materials_required"] and B["texture_rel"] and S["texture_rel"], "3mf: material extension + texture relationship present")
            e = uv_err_3mf(B, size)
            check(e <= 1e-4, "3mf: UV-vs-position error", f"browser max {e:.6f}, server max {uv_err_3mf(S, size):.6f}")
            nw = int((~np.array([True] * 0)).sum()) if False else 0
        else:
            check(not B["texture"], "3mf: no texture in the plain file")

    for tex in (False, True):
        fn = f"{stem}.textured.glb" if tex else f"{stem}.glb"
        print(f"\n== GLB{' + photo' if tex else ''}")
        pb, ps = os.path.join(bro, fn), os.path.join(srv, fn)
        if not (os.path.exists(pb) and os.path.exists(ps)):
            check(False, "file present in both"); continue
        B, S = read_glb(pb), read_glb(ps)
        check(B["nodes"] == S["nodes"] == 1 and B["meshes"] == S["meshes"] == 1, "glb: one root node and mesh")
        check(B["primitives"] == S["primitives"], "glb: material primitive count", f"{B['primitives']} vs {S['primitives']}")
        check(B["materials"] == S["materials"], "glb: material names equal", str(B["materials"]))
        if tex:
            check(B["texture"] and S["texture"] and B["has_uv"] and S["has_uv"], "glb: photo texture and UVs present")

    for tex in (False, True):
        d = f"{stem}_obj_textured" if tex else f"{stem}_obj"
        print(f"\n== OBJ{' + photo' if tex else ''}")
        pb, ps = os.path.join(bro, d), os.path.join(srv, d)
        if not (os.path.isdir(pb) and os.path.isdir(ps)):
            check(False, "folder present in both"); continue
        B, S = read_obj(pb), read_obj(ps)
        cmp_part_lists("obj", B["parts"], S["parts"])
        check(B["root_count"] == S["root_count"] == 1, "obj: one root object")
        check(sorted(os.listdir(pb)) == sorted(os.listdir(ps)), "obj: same files in the folder", str(sorted(os.listdir(pb))))
        if tex:
            check(B["texture"] and B["VT"] is not None, "obj: texture.jpg + vt present")
            exp = np.clip(B["V"][:, :2] / size, 0, 1)
            e = float(np.abs(B["VT"] - exp).max()) if B["VT"] is not None and len(B["VT"]) == len(exp) else 9
            check(e <= 1e-4, "obj: UV-vs-position error", f"max {e:.6f}")

    print("\n== STL")
    B, S = read_stl(os.path.join(bro, stem + ".stl")), read_stl(os.path.join(srv, stem + ".stl"))
    check(B["nt"] == S["nt"] and B["nv"] == S["nv"], "stl: one complete model counts", f"{B['nt']}/{B['nv']} vs {S['nt']}/{S['nv']}")
    check(float(np.abs(B["bbox"] - S["bbox"]).max()) <= TOL, "stl: complete-model bounds", str(B["bbox"]))

    if a.adjusted:
        adjusted_check(a, req, srv)

    ok = all(RES)
    print(f"\n{sum(RES)}/{len(RES)} checks passed -> {'ALL EQUAL within tolerance' if ok else 'DIFFERENCES FOUND'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
