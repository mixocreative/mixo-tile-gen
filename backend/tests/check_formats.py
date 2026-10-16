"""Export every download format for one fixture tile and check each file.

    python tests/check_formats.py [tile_name]        (default 09_single_rose)

- stl: one binary STL containing the complete tile (all watertight colour shells)
- obj: one root object with material groups for the colour shells
- objtex: UVs are a straight top-down projection; the photo under each colour body must match
  that body's glaze colour (a flipped / shifted texture fails this)
"""
import io, json, os, re, struct, sys, time, zipfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, numpy as np
import tile_processor as tp

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "real_tiles", "originals")
name = sys.argv[1] if len(sys.argv) > 1 else "IMG_9255"
shape = os.environ.get("TILE_SHAPE", "square")
c = json.load(open(os.path.join(D, "..", "corners.json"), encoding="utf-8"))[name]   # corners in photo pixels
img = open(os.path.join(D, name + ".jpg"), "rb").read()
rgb0, scale = tp.decode_image(img)
corners = c


def closed(f):
    e = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), 1)
    return bool((np.unique(e, axis=0, return_counts=True)[1] == 2).all())


ok = True
for fmt in ("stl", "obj", "objtex"):
    t = time.time()
    data, stats = tp.process_tile(img, corners, None, tp.TileConfig(output_format=fmt, tile_shape=shape))
    z = zipfile.ZipFile(io.BytesIO(data)) if fmt != "stl" else None
    names = z.namelist() if z else ["mixotile.stl"]
    line = f"{fmt:7s} {len(data) / 1e6:6.1f} MB  {time.time() - t:5.1f} s  files={names[:3]}{'…' if len(names) > 3 else ''}"
    if fmt == "stl":
        assert data[:80].rstrip().startswith(b"MixoTile relief")
        cnt = int(np.frombuffer(data[80:84], "<u4")[0])
        assert len(data) == 84 + 50 * cnt
        line += f"  one complete tile, triangles={cnt}"
        ok &= cnt == stats["triangles"] > 0
    else:
        obj = z.read("model.obj").decode(); mtl = z.read("model.mtl").decode()
        v = np.array(re.findall(r"^v (\S+) (\S+) (\S+)$", obj, re.M), float)
        assert len(re.findall(r"^o MixoTile relief$", obj, re.M)) == 1
        groups = re.split(r"^g ", obj, flags=re.M)[1:]
        line += f"  root=1 groups={len(groups)} verts={len(v)}"
        if fmt == "objtex":
            tex = cv2.cvtColor(cv2.imdecode(np.frombuffer(z.read("texture.jpg"), np.uint8), 1), cv2.COLOR_BGR2RGB)
            vt = np.array(re.findall(r"^vt (\S+) (\S+)$", obj, re.M), float)
            assert len(vt) == len(v)                 # every body has UVs, the pad's sides included
            ok &= "usemtl underside" in obj           # pad underside is plain white
            # what a viewer does: follow each face corner's v/vt pair; the UV must be the vertex's top-down position
            pairs = np.array(re.findall(r"(\d+)/(\d+)", "\n".join(re.findall(r"^f .*$", obj, re.M))), int) - 1
            uv_err = float(np.abs(vt[pairs[:, 1]] - np.clip(v[pairs[:, 0], :2] / 150.0, 0, 1)).max())
            line += f"  face-UV error {uv_err:.5f}"
            ok &= uv_err < 1e-4
            h, w = tex.shape[:2]
            errs, base = [], 0
            kd = {}
            for blk in groups:
                nm = blk.split("\n", 1)[0].strip(); nv = len(re.findall(r"^v ", blk, re.M))
                hexc = nm.rsplit("_", 1)[1]; rgb = np.array([int(hexc[i:i + 2], 16) for i in (0, 2, 4)])
                uv = vt[base:base + nv]; base += nv
                if "pad" in nm:
                    continue
                px = tex[np.clip(((1 - uv[:, 1]) * (h - 1)).round().astype(int), 0, h - 1),
                         np.clip((uv[:, 0] * (w - 1)).round().astype(int), 0, w - 1)]
                errs.append(float(np.linalg.norm(np.median(px, 0) - rgb)))
            # and the same check with the texture flipped, to show the test can fail
            flip = []
            base = 0
            for blk in groups:
                nm = blk.split("\n", 1)[0].strip(); nv = len(re.findall(r"^v ", blk, re.M))
                hexc = nm.rsplit("_", 1)[1]; rgb = np.array([int(hexc[i:i + 2], 16) for i in (0, 2, 4)])
                uv = vt[base:base + nv]; base += nv
                if "pad" in nm:
                    continue
                px = tex[np.clip((uv[:, 1] * (h - 1)).round().astype(int), 0, h - 1),
                         np.clip((uv[:, 0] * (w - 1)).round().astype(int), 0, w - 1)]
                flip.append(float(np.linalg.norm(np.median(px, 0) - rgb)))
            line += f"  texture {w}x{h}, colour error per body (RGB dist) median {np.median(errs):.0f} max {max(errs):.0f}; flipped: median {np.median(flip):.0f}"
            ok &= np.median(errs) < 40 and np.median(errs) < np.median(flip)
        else:
            ok &= len(re.findall(r"^newmtl ", mtl, re.M)) == len(groups)
    print(line, flush=True)
# plain 3MF: one model object retains a base material for every displayed glaze colour
t = time.time()
data, _ = tp.process_tile(img, corners, None, tp.TileConfig(output_format="3mf", tile_shape=shape))
z = zipfile.ZipFile(io.BytesIO(data)); plain = z.read("3D/3dmodel.model").decode()
plain_bases = re.findall(r'<base name="[^"]+" displaycolor="#[0-9A-F]{8}"/>', plain)
plain_p1 = np.array(re.findall(r'<triangle [^>]* p1="(\d+)"', plain), int)
plain_one_model = len(re.findall(r'<object id="\d+" type="model"(?:\s|>)', plain)) == 1
print(f"3mf     {len(data) / 1e6:6.1f} MB  {time.time() - t:5.1f} s  one-model={plain_one_model} base-materials={len(plain_bases)}", flush=True)
ok &= plain_one_model and len(plain_bases) > 1 and len(plain_p1) > 0 and plain_p1.max() < len(plain_bases)

# textured 3MF: per-corner tex2coord must be the vertex's top-down position; the slicer part
# table (extruders) must still be there, so it prints in glaze colours
t = time.time()
data, _ = tp.process_tile(img, corners, None, tp.TileConfig(output_format="3mftex", tile_shape=shape))
z = zipfile.ZipFile(io.BytesIO(data)); x = z.read("3D/3dmodel.model").decode()
v = np.array(re.findall(r'<vertex x="([^"]+)" y="([^"]+)" z="([^"]+)"', x), float)
uv = np.array(re.findall(r'<m:tex2coord u="([^"]+)" v="([^"]+)"', x), float)
tt = np.array(re.findall(r'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)" pid="\d+" p1="(\d+)" p2="(\d+)" p3="(\d+)"', x), int)
err = max(float(np.abs(uv[tt[:, 3 + k]] - np.clip(v[tt[:, k], :2] / 150.0, 0, 1)).max()) for k in range(3))
white = '<base name="underside" displaycolor="#FFFFFFFF"/>' in x
has_tex = white and "3D/Textures/texture.jpg" in z.namelist() and "3D/_rels/3dmodel.model.rels" in z.namelist()
has_cfg = "extruder" in z.read("Metadata/Slic3r_PE_model.config").decode()
one_model = len(re.findall(r'<object id="\d+" type="model"(?:\s|>)', x)) == 1
valid_object_attrs = 'name="MixoTile relief"' not in x
material_extension = 'requiredextensions="m"' in x
print(f"3mftex  {len(data) / 1e6:6.1f} MB  {time.time() - t:5.1f} s  textured tris={len(tt)}  corner-UV error {err:.5f}  texture={has_tex} extruders={has_cfg}", flush=True)
ok &= err < 2e-3 and has_tex and has_cfg and one_model and valid_object_attrs and material_extension and len(tt) > 0

# GLB: one root node/mesh; primitives preserve the glaze materials, or the photo plus white underside
def glb_json(data):
    magic, version, length = struct.unpack_from("<4sII", data)
    assert magic == b"glTF" and version == 2 and length == len(data)
    n, kind = struct.unpack_from("<I4s", data, 12)
    assert kind == b"JSON"
    return json.loads(data[20:20 + n])

t = time.time()
data, _ = tp.process_tile(img, corners, None, tp.TileConfig(output_format="glbtex", tile_shape=shape))
doc = glb_json(data); prim = doc["meshes"][0]["primitives"]
tex_prim = [p for p in prim if "TEXCOORD_0" in p["attributes"] and p["material"] == 0]
under_prim = [p for p in prim if p["material"] == 1]
print(f"glbtex  {len(data) / 1e6:6.1f} MB  {time.time() - t:5.1f} s  root-meshes={len(doc['meshes'])} primitives={len(prim)} textured={len(tex_prim)} underside={len(under_prim)}", flush=True)
ok &= len(doc["nodes"]) == len(doc["meshes"]) == 1 and len(tex_prim) > 0 and len(under_prim) == 1 and doc["images"][0]["mimeType"] == "image/jpeg"

# bundle: every format from one run, one zip
t = time.time()
data, st = tp.process_tile(img, corners, None, tp.TileConfig(output_format="bundle", tile_shape=shape))
names = zipfile.ZipFile(io.BytesIO(data)).namelist()
want = [".3mf", ".textured.3mf", ".glb", ".textured.glb", "_obj/model.obj", "_obj_textured/texture.jpg", ".stl"]
miss = [w for w in want if not any(w in n for n in names)]
print(f"bundle  {len(data) / 1e6:6.1f} MB  {time.time() - t:5.1f} s  {len(names)} files  missing={miss}", flush=True)
ok &= not miss

print("ALL OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
