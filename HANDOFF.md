# MixoTile — Handoff

> Living handoff for any agent (Claude Code, Codex, human) picking this up mid-stream.
> **Update the "Status log" and "Next steps" sections at every key step.**
> Last updated: 2026-10-15, after the real-photo test round (see Status log).

## 1. What this is

Photo of a Taiwanese majolica tile (花磚) → printable multi-colour 3D relief (`.3MF`, optional `.GLB`).

- `frontend/index.html`: single-file app (Tailwind CDN, MediaPipe Interactive Segmenter for the auto-outline, Cropper.js fallback, 4-corner perspective editor, canvas eyedropper, settings, Three.js preview with 3MFLoader). Hosted on GitHub Pages (`.github/workflows/pages.yml`).
- `backend/`: FastAPI on Cloud Run (`main.py` = API, `tile_processor.py` = all image + geometry work, `Dockerfile`, `requirements.txt`).
- `README.md`: deploy steps for Cloud Run and GitHub Pages, plus the API reference. **Partly stale.** Its geometry section still describes an older version, so trust section 3 below.
- Not deployed yet. Not a git repo yet; ask the owner before running `git init` or committing.

## 2. How to run and verify (Windows; Git Bash or PowerShell)

```bash
# API (local port 8080 is taken on this machine -> use 8088)
cd backend && docker build -t mixotile-api .
docker run -d --name mixotile-test -m 2g -p 8088:8080 -e ALLOWED_ORIGINS="http://localhost:8790" mixotile-api
curl localhost:8088/health

# Frontend
cd frontend && python -m http.server 8790 --bind 127.0.0.1
# open http://localhost:8790/index.html?api=http://localhost:8088&v=<anything>   (v= busts browser cache)

# Pipeline without HTTP (+ watertight check of every body)
MSYS_NO_PATHCONV=1 docker run --rm -m 2g -v "S:/ai/twtile/backend:/app" -w /app mixotile-api python tests/run_local.py
```

- Debug helpers in `backend/tests/`: `make_sample.py` (synthetic photo), `run_local.py` (end-to-end + watertight), `check_watertight.py`, `check_colours.py` (palette per real tile), `check_symmetry.py`.
- Real test photos: `backend/tests/out/user/NN_name.jpg` (16 museum tiles from the owner) and `corners.json` (`{name: [upload_id, [[x,y]×4 TL,TR,BR,BL]]}`, in **2048-px coords**, so scale by `img_width/2048`). `compare.py` / `sheet.py` there build photo-vs-render sheets.
- Renders land in `previews/`. Files starting with `_` are scratch.
- Every generated body must be watertight (`run_local.py` prints this). Cloud Run has 2 GiB, so test with `-m 2g`.
- **Every pipeline change must be verified on all 16 fixture tiles** in `backend/tests/fixtures/real_tiles/` (permanent, git-tracked; never delete or replace): `python tests/run_real.py` (no args = all 16, watertight check, in the `mixotile-api` image) and `python tests/lines_sheet.py` (writes `docs/research/lines_final.jpg`: photo | detected outlines | labels | top surface) — then LOOK at the sheet.

## 3. Current design (decided with the owner; do not regress)

**Geometry, "carve the edges" profile, designed with Fable:**
- One backing pad: build123d box with rounded corners.
- One body per colour. **No colour is treated as background, and there are no height tiers by colour.**
- Each body starts at the shared full height. The surface is then carved down toward every seam between colours, so **seams are always the lowest point**: soft V-valleys, with two neighbouring rectangles giving a lowercase "m" in cross-section.
- Big areas have a near-level top with a gentle crown that flattens as the area grows. Thin strokes stay lower and round.
- Smooth from top to edge: no plateaus with kinks, no terraces.
- The math is in `seam_field` (screened-Poisson ψ → smooth seam distance `d = −L·ln(1−ψ)`), `refine_seam_field`, `cushion_profile` / `edge_roundover`, `bead_floor`, and `cushion_body_mesh` (height field → marching cubes).
- Zero gaps: each body's footprint is dilated about 0.5 mm into its neighbours at groove-floor height (hidden overlap).
- The tile edge is **not** a seam (`edge_is_seam=False`): fields run level to the edge with a soft roll-off.
- **Raised outlines (tube-lining):** `detect_outlines` finds thin light/dark lines on the photo itself (top-hat / black-hat of L at 2× raster, hysteresis, width ≥ 0.4 mm, length ≥ 4 mm, contrast ≥ 10 L, texture/crazing rejection), independent of colour clustering. Every detected line becomes a smooth cos² ridge (`outline_height_mm` × `outline_width_mm`) ADDED on top of the cushion of whichever colour it lies in (`cushion_body_mesh`, `ridge_dist`), faded out within ~1.6 mm of a seam (the groove already draws the line there). Lines whose colour clearly differs from their host (ΔE > 18) and matches another existing palette colour (ΔE ≤ 14) are also relabelled to that colour (`snap_outline_colours`); palette entries are never invented from lines.

**Defaults** (`TileConfig`, mirrored in `main.py` Form defaults and the `frontend` inputs; keep all three in sync):

| Setting | Default |
|---|---|
| Tile size | 150 mm |
| Pad | 3.0 mm |
| Edge depth (`relief_height_mm`) | 3.0 mm |
| Roll width (`fillet_radius_mm`) | 6.0 mm |
| Crown (`dome_height_mm`) | 1.0 mm |
| Crown reach | 12 mm |
| Groove floor | 0.4 mm |
| Tile corner radius | 2.0 mm |
| Raised outlines (`outline_height_mm`, 0 = off) | 0.8 mm |
| Outline width (`outline_width_mm`) | 1.2 mm |
| k | 6 |
| Raster | 4 px/mm |
| Mesh grid | 0.12 mm |
| Smoothing | 0.5 mm |
| Min feature | 2 mm² |
| `merge_delta_e` | 12 |
| Bead for thin strokes | 1.2 mm high / 0.8 mm |
| `min_band_mm` | 3 |
| `symmetry` | `off` (opt-in) |

Total height is about 7.1–7.4 mm at 150 mm. The frontend re-derives relief from tile size: depth 2 %, roll width 4 %, crown 0.7 % of the width, capped at **max height = width ÷ 10**, which is a cap, not a target.

**Colour pipeline** (`process_tile`), in order:
1. Warp with a 1.5 % inward inset.
2. Optional symmetrise.
3. Bilateral filter (9/45/9).
4. k-means with **2k** clusters.
5. `merge_shading_bands` (ΔE < 12 and a shared border), then merge the closest pairs down to k. User-picked swatches are never merged.
6. Majority filter.
7. `remove_specks`, which keeps strokes ≥ 4 mm long as outlines.

**.3MF layout:** one object, all parts' triangles in one mesh, plus `Metadata/Slic3r_PE_model.config` with per-part triangle ranges and extruders (PrusaSlicer, Orca and Bambu read it). Per-triangle `basematerials` colours are included too. Verified in PrusaSlicer 2.9.3: one object, manifold, slices with 6 tools.

**Owner's aesthetic feedback, in order:**
1. Edges must be rounded, never hard.
2. Earlier tier/terrace versions looked wrong.
3. Every colour inflates on its own, and seams are the lowest points ("you cannot assume a background colour").
4. Big areas are near-level, more so the bigger they are.
5. Smooth from top to edge.
6. The 10 mm-deep valleys looked "extreme"; the 3 mm version was "way closer".

The owner doesn't care about slicer testing. Visual realism is the goal.

## 4. Status log (newest first)

- **2026-10-15, ship round (published):**
  - Repo https://github.com/mixocreative/tw-tile-gen (public), Pages live at https://mixocreative.github.io/tw-tile-gen/.
  - **UI redesign** via Stitch (project 11051604963556458741, `.stitch/DESIGN.md`): warm monochrome palette (ink #1c1a17 → paper #faf8f5), Geist + Geist Mono, compact 32 px controls (38/44 px on touch), hairline numbered sections, phone bottom step nav. Owner rule: everything monochrome **except the original coloured tile logo/favicon**. All original element IDs kept.
  - Defaults changed: backing pad **15 mm** (max-relief cap = width/10 applies above the base only), smoothing **1.2** (app and backend in sync).
  - Streaming `/process-tile?stream=true`: NDJSON progress → binary preview mesh → 3MF bytes; preview opens before the file is ready.
  - Dockerfile runs as uid 1000 (Hugging Face Spaces requirement), port 8080.
  - Hosting: owner won't pay → **Hugging Face Space** (Docker, free) on a *different* HF account than `mixoadrian`. Not deployed yet: owner must log in on this PC (`python -c "from huggingface_hub import login; login()"`, Write token). Then create Space `tw-tile-gen` (README front matter `sdk: docker`, `app_port: 8080`), set variable `ALLOWED_ORIGINS=https://mixocreative.github.io`, test `/health`, set `DEFAULT_API` in `frontend/index.html`, push. Until then the live site shows "Engine: not set".
  - Empty GCP project `tw-tile-gen` exists under mixoadrian (no billing); owner hasn't said whether to delete it.
  - Final 16-tile run through the new UI: all OK, corner drift 0.0, 150 × 150 × 19.4–19.9 mm, 6.6–12.3 s per tile. One-off: tile 15's first screenshot showed the camera zoomed in (not reproduced on re-run; watch for it).
  - Results table: `docs/results/all_tiles.jpg` (built by `backend/tests/make_table.py <renders_dir> <out.jpg>` from Playwright renders `previews/user_*.png`).

- **2026-10-15, raised outlines (Fable, owner-delegated):** tube-lining detection + geometry ridge shipped (`detect_outlines`, `snap_outline_colours`, `ridge_dist` in `cushion_body_mesh`/`build_relief`/`process_tile`; new settings `outline_height_mm`/`outline_width_mm` in TileConfig, main.py Form, frontend). Verified: `run_local.py` all 7 bodies watertight; `run_real.py` on 02/04/06/09/16 all bodies watertight (16–24 s each, 2 GiB); 16-tile sheet `docs/research/lines_final.jpg` (detection 0.3–0.6 s/tile). Recovered ≈ 85–90 % of visible tube-lines on 09/02/04/10/11/14; crazing (16) and the museum-card tangle (05) are rejected; residual false positives: glossy mane highlights on 06 and specular ridges on 07 petals. `tests/run_real.py` and `tests/lines_sheet.py` now read `tests/fixtures/real_tiles` by default.

- **2026-10-15, real-photo round:**
  - Ran 16 owner photos plus 4 Wikimedia museum crops.
  - Implemented all 5 of Fable's earlier suggestions: shading-band merge, printable bead, per-patch band width, tile edge not a seam, symmetry (later made opt-in, because averaging a misaligned photo smeared detail).
  - Added over-segment-then-merge and the warp inset.
  - **Found and fixed a frontend race:** a slow MediaPipe auto-detect overwrote corners the user had just dragged. A `S.cornerEdits` generation counter now makes manual edits win, and the status line says "Kept your manual corners".
  - A full 16-tile re-render that drags corners deliberately early (to test the race fix, logging corner drift) was **in flight** when this was written. Results go to `previews/user_*.png`.
- **Known weak points** (Fable is working on them, see section 5):
  - Painterly/shaded tiles break into blotchy patches.
  - Thin light tube-lining vanishes.
  - Small details are lost (rose centre, faces, leopard spots).
  - Glare, stickers and chips become colours.
  - Fixed k=6 doesn't suit every tile.
- **Auto-outline (MediaPipe)** is unreliable on framed tiles: it locks onto the frame or the motif. Manual corners work. A better framed-tile detector is still TODO.

- **2026-10-15, Fable fixes applied** (`tile_processor.py`):
  - `quantize_auto`: bilateral filter + mean-shift (sp 7, sr 22), k-means with k=12 in L-weighted Lab, `merge_shading_bands`, then closest pairs merged until ΔE ≥ 14 and k ≤ `num_colors`. `num_colors` is now a **max** with default 8; `main.py` and the frontend are synced.
  - `remove_specks` keeps small high-contrast details: ΔE > 25 against the colour around them and ≥ 1 mm².
  - `remove_glare` is implemented but **opt-in** (`TileConfig.remove_glare=False`). On real photos it erased legitimate white glaze: the bear's chest and face, the teal octagon flower, the purple sunflower. Its stickers check is also not solved.
  - Verified with `tests/check_labels.py` → `tests/out/user/labels_all.jpg` (photo vs label map for all 16): auto-k picks 5–8 colours, and faces, spots and the rose centre are kept. Still weak: the yellow chrysanthemum (07) blends into the green, and the purple sunflower's petals (16) are close to the grey ground.
  - Meshing re-checked with `tests/run_real.py 13_bear 07_chrysanthemum 14_leopard_cat`: all bodies watertight. There are now 9 bodies, up to 2.2 M triangles, 13–23 s per tile. The file got bigger; the decimation budget could be tightened later.
- **2026-10-15, corner race, second fix** (`frontend/index.html`): the first fix still let corners jump on 9 of 16 tiles. Cause: when the page has just loaded, the MediaPipe model finishes loading *after* the user drags, and `initSegmenter` then starts a fresh auto-detect. Now `autoDetect(points, auto)` uses `auto=true` for app-started runs (photo load, model ready), which never touch corners once `S.cornerEdits > 0`, and `loadFile` resets `S.cornerEdits = 0`. The explicit "Auto-detect again" and tap-to-detect still apply. Verification: the 16-tile UI re-render logs `drift` per tile and should be about 0 px. Renders go to `previews/user_*.png`; the previous run is in `previews/old_run/`.
  - Correction: the remaining drift (9 tiles, identical numbers across runs) was a **test-harness** issue, not the app. The AI had put a corner at the photo's bottom edge, below the browser viewport. Playwright's `page.mouse` doesn't auto-scroll, so the drag hit nothing. Scroll each handle into view (`scrollIntoView`) before dragging in UI tests. The 9 tiles (01, 02, 04, 08, 09, 12, 13, 14, 16) are being re-rendered with that.
  - Correction 2: scrolling wasn't enough. **Real app bug:** `.stage` had `overflow:hidden` plus `border-radius`, so a handle sitting exactly on a photo corner was clipped by the rounded corner and couldn't be grabbed. MediaPipe often returns photo-corner points. Fixed in CSS: `.stage` is `overflow: visible`, the rounding moved to `canvas.src`, the SVG is `overflow: visible; z-index: 1`, and `#loupe` has `z-index: 2`. Verified on 13_bear: all 4 handles grabbed, drift 0.0 px.

- **2026-10-15, final 16-tile render** (correct corners, drift 0.0 px on all): `backend/tests/out/user/compare_01.jpg` and `compare_09.jpg`, sent to the owner.
  - **Good:** 01, 02, 03, 08, 11, 12, 13, 14, 15.
  - **Remaining issues:**
    - Stickers become relief ("75", "61", the side label on 05).
    - Thin dark lines are lost: the rose stem on 09, some leaf outlines.
    - Fine inner detail is lost: the lion's face (06), the inner petals of 04's blue flower, the 16 sunflower's petal lines.
    - My hand-set corners leave a thin frame or neighbour strip on one edge of 07, 10, 13 and 16. That's corner precision, not the pipeline.

- **Fable line-detection report (done, not yet integrated).** Prototype: `docs/research/lines_proto.py`. Sheet: `docs/research/lines_before_after.jpg` (photo | detected lines | labels before | after).
  - **Method:** morphological top-hat (light lines) and black-hat (dark lines) on L with a 2 mm disc, at 2× raster (6 px/mm). Hysteresis 5/10 L-units, 0.4 mm opening, skeleton length ≥ 4 mm. It only fires on structures thinner than 2 mm in every direction, so colour edges, grounds, glare blobs and stickers give nothing. Sato/Frangi was tried and rejected (fires on every colour edge and on crazing).
  - **Recovery:** about 90 % of lines on 09, 85 % on 16, 80 % on 04, 85 % on 02, 70 % on 06. 0.07–0.14 s per tile.
  - **Integration (recommended):** (b) a geometric ridge. Pass `ridge_mask` to `build_relief` and, inside each body, apply `smooth_max` of `bead_floor(dist_to_ridge_centre)` with h ≈ 0.8–1.0 mm and r ≈ 0.6 mm. This works even for same-colour lines and adds no bodies. Optionally (a): snap a line to an existing palette colour when ΔE to its host is > 18 and it is within ΔE 14 of a palette entry. **Never create new palette colours from lines.**
  - **Detection must run on the un-smoothed `flat`, before mean-shift.**
  - **Limits:** the mask is fat, so use the skeleton plus distance. False positives on glossy, heavily modelled glaze and textured surfaces (lion mane, textured bridge on 06) were checked visually. An untested idea: a both-flanks symmetry test.
- **(superseded) In flight:** the owner reports that small lines and low-contrast lines (similar colour to their neighbour) are still lost. Fable is researching line detection that doesn't depend on colour clustering:
  - ridge filters (Sato/Frangi) or DoG, plus light/dark gradient pairs for raised tube-lining;
  - lines entering the model as their own colour and/or as a pure geometric raised bead;
  - false positives from glare and crazing must be avoided.
  - If the report isn't available, that's the plan to implement. Test on 09, 16, 04, 02 and 06.

- **2026-10-15, main thread after the Fable outline integration:**
  - Changed `snap_outline_colours`: decisions are made on the original labels, and only a line-width band around the centre-line is recoloured (the mask is fat). A line only snaps to a glaze that is present within a few line widths. `de_snap` is now 10.
  - Verified on the label maps: the rose's red is no longer meshed with dark green.
  - **Known issue still visible in 3D** (09 rose leaves, `previews/lines_09_single_rose_close.png`): shiny highlights on the leaf glaze are quantised to cream, so leaves read as a green lattice with cream holes. Cause: colour quantisation, not outline snapping. Candidate fix: absorb small, enclosed, high-L islands into the host colour, without eating real white details such as the bear's eyes.

- **2026-10-15, watertight regression found and fixed:**
  - The full 16-tile check showed non-watertight bodies on 02 and 03: one edge shared by 4 faces. The raw marching-cubes mesh was fine; `fast_simplification` created the non-manifold edge.
  - `_decimate` now checks `_is_closed_manifold` on every result and retries at other budgets (×1.15, ×1.35, ×0.85), else keeps the dense mesh. 02 and 03 now pass.
  - `tests/run_real.py` with all 16 tiles in one process died silently after 6 tiles (probably OOM at 2 GB), so **run one tile per `docker run`**.

- **2026-10-15, puzzle-piece borders + clearance** (owner: "border should be clean bordering each other like puzzle pieces, allow setting clearance"):
  - Replaced the 0.5 mm hidden tuck-under overlap with **one shared partition**. `partition_fields()` computes, for every colour, φᵢ = (dᵢ − min over the other colours dⱼ)/2 on the fine grid. On a shared border φᵢ = −φⱼ, so both neighbours' walls land on the same surface.
  - `cushion_body_mesh(phi_full, ..., clearance)` uses lateral = max(φᵢ + clearance/2, tile SDF).
  - New setting `clearance_mm` (default 0 = flush), synced in `TileConfig`, `main.py` and the frontend.
  - Check: `tests/check_borders.py <tile> [clearance]` rasterises each body's cross-section at 0.15 mm above the pad, at 0.05 mm resolution, and counts gap and overlap pixels.
  - 09_single_rose results: clearance 0 → gap 0.7 mm², "overlap" 127 mm², which is the rasteriser double-counting shared border pixels (about 0.01 mm × 10.8 m of walls). Clearance 0.3 → 1209 mm² of slots, 0 overlap. Watertight at both settings.
- **Highlight absorb:** `absorb_glare_islands()` runs after `remove_specks`. A patch ≤ 25 mm², enclosed by ONE colour, with ΔL > 15 against a host whose chroma is > 15, is absorbed into the host. Small cleanups on 02, 12 and 13, and the bear's eyes are kept. **Rose leaves (09) are NOT fixed:** their pale fill quantises to cream and is bounded by two greens. Still open.
- `_decimate` manifold check verified: all 16 tiles watertight (one process each).

- **2026-10-15, speed / memory / UX** (owner: "do what is best for UX"):
  - **Memory: the old code got OOM-killed on Cloud Run.** Peak was 2.24–2.5 GB on a full-tile body; Docker had hidden this with swap. Always test with `-m 2g --memory-swap 2g --cpus 2`.
  - Memory fixes:
    - marching-cubes output kept as float32/int32, the 3D grid freed right away, orientation fixed only after decimation;
    - coarser z levels (`Z_STEP_MM` 0.6; exact, because the field is linear in z);
    - the pad is now built in numpy (no build123d at runtime, -230 MB);
    - default `mesh_resolution_mm` 0.12 → **0.16**, with `MAX_MESH_CELLS` = 940 enforced.
  - Result: peak about 1.5 GB, and **all 16 fixture tiles pass at 2 GiB with no swap: 5–9 s each**, watertight, flush borders. Previously 15–20 s.
  - Export: one big %-format string, 3 decimals. 7.9 s → about 2 s.
  - Parallel bodies measured **slower**, so `BODY_WORKERS` = 1.
  - **Real progress plus preview-first** (`stream=true` form field). Wire format, all in one response, so it suits Cloud Run's CPU allocation:
    1. JSON progress lines;
    2. a `{"type":"preview","layout":[…],"bytes":N}` header, then the N-byte binary preview (about 300 k triangles; float32 positions and uint32 indices);
    3. a `{"type":"done","bytes":M}` header, then the raw 3MF bytes.
  - The frontend parses this incrementally, opens the 3D view from the preview, and shows "⏳ Preparing .3MF…" until the file arrives. It also pre-warms `/health` when a photo is loaded.
  - Measured (09 rose): preview at 7.1 s and download ready at 8.5 s, against 16.2 s before. Longest UI freeze 1.0 s, was about 10 s. The cause before was 3MFLoader taking 5 s plus crease normals 1.5 s on the main thread.
  - The non-stream API, GLB output and the stream error path are verified.
  - `tests/check_borders.py` now ignores 1-px fill-rounding hairlines (3×3 erosion). At clearance 0 every tile has 0–1 px of real gap or overlap.

## 5. In-flight / next steps

0. **Outlines, known limits to improve:** (a) glossy modelled glaze still yields highlight streaks (06 lion mane, 07 petal ridges) — candidates: both-flank symmetry test, structure-tensor orientation coherence; (b) a tube-line that coincides with a colour seam is drawn only by the groove (ridge faded within 1.6 mm of seams) — a dedicated line body would be needed to raise it; (c) 0.3–0.5 mm hair lines are below the 0.4 mm width gate by design; (d) `compare.py`/`check_labels.py` in `tests/out/user` still read their own folder.
1. **Apply the Fable photo report.** Prototype: `docs/research/photo_proto.py`. Before/after sheet: `docs/research/photo_before_after.jpg`, with columns photo | current | glare+meanshift k=6 | auto-k + L-weight. Ranked:
   1. **Mean-shift pre-flattening** in `quantize`, after the bilateral filter: `cv2.pyrMeanShiftFiltering(rgb, sp=7, sr=22)`. This gives fewer, larger patches on shaded glazes. Keep `sr` ≤ 22; higher eats tube-lines.
   2. **Glare/sticker inpaint** (`remove_glare` in the prototype), called in `process_tile` right after `symmetrise`. Candidate pixels: L > 80, chroma < 16, and (L − open(L, disc)) > 14. Each component must be < 3 % of the tile and have distance-transform max ≥ 1.5 mm, so thin white tube-lines are untouched. Then `cv2.inpaint` TELEA r=5. **Use a 10 mm disc**, not 6 mm, otherwise the "61"/"75" stickers survive.
   3. **Auto-k:** k-means with k=12 in Lab with L weighted 0.5, then `merge_shading_bands`, then merge the closest pair in weighted Lab while its distance is < 14. Stop at 3 colours minimum, with `num_colors` as the maximum. Gives k ≈ 5–11 and keeps faces and the rose centre.
   4. **Small-detail keeper** (untested): in `remove_specks`, keep a speck if its ΔE to the colour it would merge into is > 25 and its area is ≥ 1 mm².
   5. **Line layer** (top-hat): picks up glare ridges. Opt-in only, not default.
   - Fable's honest verdict: moderate gains, not transformative. Added runtime is about 0.4 s per tile.
2. Re-render all 16 real tiles and make photo-vs-render sheets (`backend/tests/out/user/compare.py`). Send them to the owner.
3. A better framed-tile auto-outline: detect the inner glaze rectangle with OpenCV, or tap-to-detect with a larger mask target.
4. Update the README geometry section to match section 3.
5. Deploy the engine to Hugging Face (see the ship-round entry in section 4); then test the live github.io site end to end on a phone.

## 6. Gotchas

- In Git Bash, a heredoc that writes Python containing `'\\n'` gets mangled. Write files with an editor tool or `<<'EOF'` plus plain `\n` inside a Python script, and run `python -c "import ast; ast.parse(...)"` after editing.
- Windows Python can't see Git-Bash `/tmp`. Use the project dir or the scratchpad.
- The browser caches `index.html`, so add `&v=<n>` to the URL.
- Wikimedia rate-limits fast API calls (HTTP 429). Sleep about 6 s between calls and send a User-Agent.
- PrusaSlicer CLI with `--wipe-tower` needs `--use-relative-e-distances`, and it segfaulted once with ad-hoc CLI settings. That's not the model's fault.
