# Single-scene exports design

## Goal

Every download represents one complete MixoTile model while preserving its colour/extruder regions and optional photo texture.

## Decision

"One model" means one top-level model or root object per export. It does **not** mean a boolean union of colour bodies. The backing pad and colour bodies remain internally separate closed volumes so 3MF can keep multicolour extruder assignments and every colour remains printable.

| Format | Structure after change |
|---|---|
| 3MF / textured 3MF | One existing `MixoTile relief` object; contiguous triangle ranges remain named material/extruder volumes. |
| GLB / textured GLB | One root node containing one mesh with one primitive per glaze material; textured GLB retains the photo texture and a white underside primitive. |
| OBJ / textured OBJ | One `o MixoTile relief` declaration; named `g` groups and `usemtl` sections retain material ranges. The archive remains necessary for `.mtl` and optional `texture.jpg`. |
| STL | One binary `mixotile.stl`, containing every closed pad/colour volume. STL has no material or object metadata. |

## Constraints

- Preserve the existing 3MF material palette, Slic3r/Prusa per-triangle volume/extruder table, and 3MF Materials-extension texture path/UV mapping.
- Preserve per-colour watertight source volumes. A combined STL is a single file containing multiple closed shells, not a boolean-unioned one-colour solid.
- Browser and server writers must produce structurally equivalent exports.
- All existing owner-selected fixture photos remain the only pipeline image inputs.
- No MixoTile commit, push, or deployment.

## Verification

- Add red/green format checks that assert one root/object/file per export while confirming internal material ranges remain present.
- `3mf`: one core object, glaze `basematerials`, and extruder ranges.
- `3mftex`: all of the above plus `texture.jpg`, `texture2dgroup`, and UV-to-position correspondence.
- `glb`: one root mesh/node, expected primitives/materials, and texture binding/UVs for textured output.
- `obj`: exactly one object declaration; group/material sections still cover all triangles.
- `stl`: exactly one binary file containing all part triangles; every original component remains closed before concatenation.
- Run the mandatory real-photo, all-format, and visual-sheet checks before completion.
