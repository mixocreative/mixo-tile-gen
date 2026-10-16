# Single-scene exports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export every MixoTile download as one complete model/root object without losing multicolour material, extruder, or photo-texture information.

**Architecture:** Keep `parts` as the internal, watertight colour-volume representation. Change only the writers: concatenate STL triangle records into one file, use one OBJ object with material groups, and emit one GLB mesh/node containing material primitives. Preserve the existing one-object 3MF writer and add structural regression checks for both server and browser writers.

**Tech Stack:** Python 3, NumPy, trimesh/glTF 2.0, JavaScript, fflate, 3MF XML, binary STL, OBJ/MTL.

---

### Task 1: Capture single-scene export contracts in tests

**Files:**
- Modify: `backend/tests/check_formats.py`
- Modify: `backend/tests/compare_client_exports.py`
- Modify: `HANDOFF.md`

- [ ] **Step 1: Write failing assertions for the server formats**

Add checks to `check_formats.py` that require exactly one STL member named `mixotile.stl`, exactly one OBJ `o MixoTile relief` line, one GLB root mesh/node, and one 3MF object. For `3mftex`, require `basematerials`, `Metadata/Slic3r_PE_model.config` extruder volumes, `3D/Textures/texture.jpg`, and `m:texture2dgroup`.

```python
assert names == ["mixotile.stl"]
assert len(re.findall(r"^o MixoTile relief$", obj, re.M)) == 1
assert len(re.findall(r'<object id="\\d+" type="model"(?:\\s|>)', x)) == 1
assert 'name="MixoTile relief"' not in x
assert '<basematerials id="2">' in x and 'key="extruder"' in cfg
assert "3D/Textures/texture.jpg" in z.namelist() and '<m:texture2dgroup' in x
```

- [ ] **Step 2: Run the focused format test and observe the expected red failure**

Run: `..\.venv\Scripts\python tests\check_formats.py IMG_9255`

Expected: FAIL because STL is currently a per-part ZIP and OBJ/GLB currently declare one object/mesh per part.

- [ ] **Step 3: Extend browser/server parity readers**

Change `compare_client_exports.py` readers so STL reads the one file, OBJ records one root object plus `g` material groups, and GLB records a single mesh/node plus primitive metadata. Compare total triangle counts, total bounding box, material/texture presence, and per-part group ranges rather than a list of exported objects.

- [ ] **Step 4: Record the red-test result in the handoff**

Add a dated `Status log` entry stating that the single-scene export contract is in progress and that the focused test was intentionally red. Keep `Next steps` pointed at Tasks 2–5. Do not commit.

### Task 2: Combine STL into one complete tile file

**Files:**
- Modify: `backend/tile_processor.py:1207-1220,1268-1337`
- Modify: `frontend/index.html:2002-2062,2131-2137`
- Test: `backend/tests/check_formats.py`

- [ ] **Step 1: Write the minimal server writer**

Replace `write_stl_zip(parts)` with `write_stl(parts)`. Build one triangle array by applying the existing `_split_pinches` to each part before concatenating. Write one binary STL header and record count.

```python
def write_stl(parts) -> bytes:
    triangles = [
        _split_pinches(v, np.asarray(f))[np.asarray(f)]
        for _, _, v, f in parts
    ]
    tri = np.concatenate(triangles, axis=0)
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    rec = np.zeros(len(tri), np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))
    rec["n"], rec["v"] = nrm, tri
    return b"MixoTile relief".ljust(80, b" ") + np.uint32(len(tri)).tobytes() + rec.tobytes()
```

Change `EXPORT_FORMATS["stl"]` to `("stl", "model/stl")`, remove STL from `_BUNDLE_DIR`, and dispatch `export_parts(..., "stl")` to `write_stl`.

- [ ] **Step 2: Write the equivalent browser writer**

Replace the loop in `writeStl(ctx, files)` with one streamed `mixotile.stl` member. First sum `p.nt`, write one 84-byte header/count, then stream the existing normal calculation/records for every part into that member.

```javascript
const h = files.begin('mixotile.stl', 4);
const total = ctx.parts.reduce((n, p) => n + p.nt, 0);
// write one header and then append records for every p in ctx.parts
```

Change `FMT.stl` to `{ ext: 'stl', kind: 'file', run: ... }` and remove its bundle directory mapping.

- [ ] **Step 3: Run the focused check green**

Run: `..\.venv\Scripts\python tests\check_formats.py IMG_9255`

Expected: one `mixotile.stl`, correct total triangle count, and every original source part still closed.

### Task 3: Make OBJ one root object with grouped materials

**Files:**
- Modify: `backend/tile_processor.py:1223-1265`
- Modify: `frontend/index.html:2064-2118`
- Test: `backend/tests/check_formats.py`

- [ ] **Step 1: Change the server OBJ structure**

Write the root object once before the loop. Replace repeated `o` declarations with a group per internal part; keep the existing `usemtl`, vertices, UVs, and faces.

```python
obj = ["mtllib model.mtl\n", "o MixoTile relief\n"]
for nm, (name, rgb, v, f) in zip(names, parts):
    obj.append(f"g {nm}\nusemtl {'photo' if textured else nm}\n")
```

- [ ] **Step 2: Mirror the root/group layout in the browser writer**

Write `o MixoTile relief` once after `mtllib model.mtl`. Replace `w.s(\`o ${nm}...\`)` with `w.s(\`g ${nm}...\`)`, retaining material transitions for the white textured underside.

- [ ] **Step 3: Run the OBJ checks green**

Run: `..\.venv\Scripts\python tests\check_formats.py IMG_9255`

Expected: one OBJ root, all material groups present, textured OBJ retains `texture.jpg`, UVs, and white underside faces.

### Task 4: Emit GLB as one root mesh with material primitives

**Files:**
- Modify: `backend/tile_processor.py:1081-1109`
- Modify: `frontend/index.html:1913-2000`
- Test: `backend/tests/check_formats.py`

- [ ] **Step 1: Write a failing GLB topology assertion**

Require the GLB JSON/loaded scene to have one root node and one mesh. Require one primitive per glaze material plus, for textured GLB, a white underside primitive. Require `baseColorTexture` and UV data for every non-underside textured primitive.

- [ ] **Step 2: Implement the browser GLB as one mesh with primitives**

Keep one `meshes` entry and add each part’s geometry as a primitive with its own `POSITION`, `NORMAL`, optional `TEXCOORD_0`, index accessor, and material. Write one node referencing that mesh.

```javascript
const primitives = parts.map((p, i) => ({
  attributes: { POSITION: positionAccessor[i], NORMAL: normalAccessor[i], ...(T ? { TEXCOORD_0: uvAccessor[i] } : {}) },
  indices: indexAccessor[i], material: materialIndex[i], mode: 4,
}));
meshes.push({ name: 'MixoTile relief', primitives });
nodes.push({ name: 'MixoTile relief', mesh: 0 });
```

- [ ] **Step 3: Implement the matching server GLB primitive layout**

Use a narrow direct GLB writer (not `trimesh.Scene`): append aligned buffer views for each part's rotated metre-space `POSITION`, smooth `NORMAL`, optional top-down `TEXCOORD_0`, and index array; emit those as primitives of one `meshes[0]`; emit only `nodes[0] -> mesh 0`; embed the JPEG in one image buffer view. Flat primitives use linearized PBR base colours. Textured primitives use the shared photo material, and the pad underside is a distinct white primitive. Preserve the current metres/Y-up conversion.

- [ ] **Step 4: Run the GLB checks green**

Run: `..\.venv\Scripts\python tests\check_formats.py IMG_9255`

Expected: one GLB root mesh/node; flat GLB retains per-colour materials; textured GLB retains photo texture, UVs, and white underside.

### Task 5: Verify browser/server parity and full pipeline regressions

**Files:**
- Modify: `backend/tests/compare_client_exports.py`
- Modify: `README.md:format descriptions`
- Modify: `README.en.md:format descriptions`
- Modify: `HANDOFF.md`

- [ ] **Step 1: Update user-facing format wording**

Replace “one file per colour” for STL with “one complete tile file; STL does not contain colour assignments.” State that OBJ/GLB contain one model with material regions, while 3MF retains slicer extruder assignments and textured 3MF retains a viewing texture.

- [ ] **Step 2: Capture a browser export and run parity**

Run: `..\.venv\Scripts\python tests\compare_client_exports.py --browser <captured-browser-zip> --server <output-dir> --req <captured-request.json>`

Expected: server and browser match in root structure, total geometry, material regions, texture presence, UVs, and STL triangle/bounds data.

- [ ] **Step 3: Run mandatory pipeline verification**

Run from `backend/`:

```powershell
..\.venv\Scripts\python tests\run_real.py
..\.venv\Scripts\python tests\check_formats.py IMG_9255
..\.venv\Scripts\python tests\lines_sheet.py
```

Inspect the generated photo-versus-result sheet. Confirm every colour body is watertight, every format’s one-model contract holds, 3MF/3MFtex materials remain present, and the textured files retain aligned photo UVs.

- [ ] **Step 4: Update the handoff after verified results**

Add the exact commands, outcomes, and any browser parity limitations to the `Status log`; refresh `Next steps`. The owner explicitly authorized committing and pushing this completed MixoTile work, so do that only after every required verification is green. Do not deploy.
