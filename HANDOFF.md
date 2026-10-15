# MixoTile — Handoff

> Living handoff for any agent (Claude Code, Codex, human) picking this up mid-stream.
> **Update the "Status log" and "Next steps" sections at every key step.**
> Last updated: 2026-10-15, after the docs audit pass (see Status log).

## 1. What this is

Photo of a Taiwanese majolica tile (花磚) → printable multi-colour 3D relief (`.3MF`, optional `.GLB`).

- `frontend/index.html`: single-file app (Tailwind CDN, MediaPipe Interactive Segmenter for the auto-outline, Cropper.js fallback, 4-corner perspective editor, canvas eyedropper, settings, Three.js preview with 3MFLoader). Hosted on GitHub Pages (`.github/workflows/pages.yml`).
- `backend/`: FastAPI on Cloud Run (`main.py` = API, `tile_processor.py` = all image + geometry work, `Dockerfile`, `requirements.txt`).
- `README.md` (繁體中文, shown first on GitHub) and `README.en.md` (English, same content): the user guide (what it does, the step-by-step setup guide for every way to run it, the command line, the API, tests, known limits). Section 3 below is the source of truth for the geometry.
- `scripts/`: `mixo.py` (command line, wrapped by `mixo.bat` / `mixo.sh`) and `run_local.py` (the launcher behind `start-windows.bat`, `start-windows-phone.bat`, `start-mac-linux.sh`).
- **Status: live.** Engine on Google Cloud Run (https://mixo-tile-gen-616971929665.asia-east1.run.app, asia-east1, 4 vCPU, 4 GiB, `MIXOTILE_BODY_WORKERS=2`, max 1 instance, NT$30 budget kill switch tested). Site on GitHub Pages (https://mixocreative.github.io/mixo-tile-gen/). The folder is a git repo with `origin` = github.com/mixocreative/mixo-tile-gen. Don't commit, push or deploy unless the owner asks.

## 2. How to run and verify (Windows; Git Bash or PowerShell)

```bash
# Whole app on this PC (engine + website on one port): double-click start-windows.bat, or
python scripts/run_local.py            # opens http://localhost:8088/?api=self ; creates .venv on first run

# Engine only, in Docker (the same image Cloud Run builds)
cd backend && docker build -t mixotile-api .
docker run -d --name mixotile-test -m 4g -p 8088:8080 -e ALLOWED_ORIGINS="http://localhost:8790" mixotile-api
curl localhost:8088/health

# Frontend only
cd frontend && python -m http.server 8790 --bind 127.0.0.1
# open http://localhost:8790/index.html?api=http://localhost:8088&v=<anything>   (v= busts browser cache)
```

- **Test photos: only the owner's 18 photos** in `backend/tests/fixtures/real_tiles/originals/IMG_*.jpg` (3024 px), with corners in `real_tiles/corners.json` (`{"IMG_xxxx": [[x,y] TL,TR,BR,BL]}`, in photo pixels). Never add, delete or replace fixtures; if the folder changes, the owner is curating, so ask first. There are no synthetic test images.
- Scripts in `backend/tests/` (run from `backend/`, with the app's Python: `..\.venv\Scripts\python` on Windows, `../.venv/bin/python` on Mac/Linux, or inside the `mixotile-api` image):
  - `run_real.py [IMG_...]`: every colour body watertight, time per tile (no args = all 18; run one tile per process on low-memory machines).
  - `check_formats.py IMG_9255`: STL closed per colour, OBJ materials, photo texture lined up.
  - `check_borders.py IMG_9255 [clearance]`: puzzle-fit gap/overlap between colours.
  - `lines_sheet.py`: visual sheet (photo | outlines | colours | height map) to `docs/research/`. LOOK at it.
  - `make_table.py <renders_dir> <out.jpg>`: photo-vs-render table from app screenshots `user_<name>.png`.
  - `check_labels.py`, `mem_trace.py`, `profile_tile.py`: colour-label sheet, memory trace, profiler.
- Command line: `scripts/mixo.py` (`mixo.bat` / `mixo.sh`), local or `--server URL`.
- Renders land in `previews/`. Files starting with `_` are scratch.
- Every generated body must be watertight. Cloud Run has 4 GiB; test memory-sensitive changes with `-m 4g` (peak is about 1.5-2 GB per tile).
- **Every pipeline change must be verified on all 18 fixture tiles**: `python tests/run_real.py` and `python tests/lines_sheet.py`, then look at the sheet.

## 3. Current design (decided with the owner; do not regress)

**Geometry, "carve the edges" profile, designed with Fable:**
- One backing pad: build123d box with rounded corners.
- One body per colour. **No colour is treated as background, and there are no height tiers by colour.**
- Each body starts at the shared full height. The surface is then carved down toward every seam between colours, so **seams are always the lowest point**: soft V-valleys, with two neighbouring rectangles giving a lowercase "m" in cross-section.
- Big areas have a near-level top with a gentle crown that flattens as the area grows. Thin strokes stay lower and round.
- Smooth from top to edge: no plateaus with kinks, no terraces.
- The math is in `seam_field` (screened-Poisson ψ → smooth seam distance `d = −L·ln(1−ψ)`), `refine_seam_field`, `cushion_profile` / `edge_roundover`, `bead_floor`, and `cushion_body_mesh` (height field → marching cubes).
- Zero gaps: all colours are cut from one shared partition (`partition_fields`), so neighbours meet exactly; `clearance_mm` opens a slot. (The old 0.5 mm hidden overlap is gone.)
- The tile edge is **not** a seam (`edge_is_seam=False`): fields run level to the edge with a soft roll-off.
- **Raised outlines (tube-lining):** `detect_outlines` finds thin light/dark lines on the photo itself (top-hat / black-hat of L at 2× raster, hysteresis, width ≥ 0.4 mm, length ≥ 4 mm, contrast ≥ 10 L, texture/crazing rejection), independent of colour clustering. Every detected line becomes a smooth cos² ridge (`outline_height_mm` × `outline_width_mm`) ADDED on top of the cushion of whichever colour it lies in (`cushion_body_mesh`, `ridge_dist`), faded out within ~1.6 mm of a seam (the groove already draws the line there). Lines whose colour clearly differs from their host (ΔE > 18) and matches another existing palette colour (ΔE ≤ 14) are also relabelled to that colour (`snap_outline_colours`); palette entries are never invented from lines.

**Defaults** (`TileConfig` in `backend/tile_processor.py`, mirrored in `main.py` Form defaults and the `frontend` inputs; keep all three in sync):

| Setting | Default |
|---|---|
| Tile size (`tile_size_mm`) | 150 mm |
| Base / pad (`pad_thickness_mm`) | 15 mm |
| Edge depth (`relief_height_mm`) | 3.0 mm |
| Edge roll width (`fillet_radius_mm`) | 6.0 mm |
| Crown (`dome_height_mm`) | 1.0 mm |
| Crown reach (`dome_reach_mm`) | 12 mm |
| Groove floor (`groove_floor_mm`) | 0.4 mm |
| Tile corner radius (`corner_radius_mm`) | 2.0 mm |
| Raised outlines (`outline_height_mm`, 0 = off) | 0.8 mm |
| Outline width (`outline_width_mm`) | 1.2 mm |
| Max colours (`num_colors`) | up to 8 (auto picks 3 up to this) |
| Raster (`px_per_mm`) | 4 px/mm |
| Mesh grid (`mesh_resolution_mm`) | 0.16 mm |
| Smoothing (`smoothing_mm`) | 1.2 mm |
| Min feature (`min_feature_mm2`) | 2 mm² |
| `merge_delta_e` | 12 |
| Thin-stroke bead (`bead_height_mm`, `bead_width_mm`) | 1.2 mm high / 0.8 mm |
| `min_band_mm` | 3 |
| Clearance (`clearance_mm`) | 0 (flush) |
| `symmetry` | `off` (opt-in) |

Total height is about 19-20 mm at 150 mm (15 mm base plus about 4-5 mm relief). The frontend re-derives relief from tile size: depth 2 %, roll width 4 %, crown 0.7 % of the width, capped at **max relief = width ÷ 10 above the base**, which is a cap, not a target.

**Colour pipeline** (`process_tile`), in order:
1. Warp with a 1.5 % inward inset.
2. Optional symmetrise.
3. Bilateral filter (9/45/9).
4. Mean-shift flattening, then k-means with k = 12 in L-weighted Lab (auto-k; `num_colors` is the maximum).
5. `merge_shading_bands` (ΔE < 12 and a shared border), then merge the closest pairs until ΔE ≥ 14 or k ≤ `num_colors`. User-picked swatches are never merged.
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

- **2026-10-15, cloud offload:** engine `output_format=mesh` = mesh.zip (parts.json incl. extruders + params, mesh.bin raw float32/uint32, texture.jpg 2048, heights.bin per-vertex t,A,B,R,resid); ~23 MB, 0.5 s export instead of ~90 s for all 7 formats. Browser writes every format (JS ports of write_3mf/3mftex/glb/glbtex/obj/objtex/stl incl. pinch split) on demand: phone = one button per format, computer = checklist + streamed zip (fflate). `tests/compare_client_exports.py`: browser vs server files 60/60 checks equal (bbox 1e-5 mm, extruders identical, STL closed). Slider "Apply" rewrites z of the full mesh in the browser (z' = z + F(new) - F(params); pad z' = t*pad'): per-part max height within 0.001 mm of a real rebuild, p95 0.13 mm; "Exact rebuild (cloud)" kept. Colour step: Glaze colours / Photo skin modes (pick, custom colour, remove, max colours, Restore suggested); preview look and download pre-selection follow the mode. Engine queue: one tile at a time, others wait with a message (concurrency 4).

- **2026-10-15, live sliders + persistence:** engine streams `{"type":"heights"}` = per preview vertex t, A, B, R, resid (cushion_body_mesh coef_out; body z = pad + t*(floor + relief*A + crown*B + outline*R + resid), pad z = t*pad). `tests/check_live_heights.py`: same settings 95% within 0.06 mm; big changes vs real rebuild 95% within 0.31 mm. Preview "Fine-tune (live)" panel: base / edge depth / crown / groove floor / outline sliders (per-setting % ranges, true mm shown, ↺, Reset all, Confirm = exact rebuild), two-way synced with step 04; all settings persisted in localStorage with per-setting ↺ and Reset all; home-page English | 繁體中文 choice (explicit choice beats auto-detect); "Try a sample" link in logo blue. AI-blocked regression re-run on the new UI (desktop + zh phone): manual mode, no page errors, generate + sliders OK.

- **2026-10-15, UI batch 2:** zh-Hant auto (navigator.languages zh*) + 中/EN toggle; phone "Take or choose photo" (no capture attr); colour step: big Suggest / Photo / Mapped buttons, auto-suggest on load + after corner changes (deterministic k-means; manual picks set S.manualPalette and are never overwritten); 3D preview: big Colours/Photo pill overlay; pad textured on its sides + white underside (exports and preview); download = checklist of 7 formats (all on) -> one zip via output_format=bundle&formats=...; step 04 live SVG cross-section (height x3) highlighting the focused setting; photo-loading overlay; upload stage with estimated bar (app already sends a 2000 px JPEG, ~1.1 MB). Launcher: random-port retry, `/local-info` (MIXO_PHONE_FILE) feeds a QR panel shown only on localhost, Cloudflare watchdog replaces a dead tunnel (tested by killing it). Cloud bundle of all 7 formats: 151 MB, ~114 s end to end.

- **2026-10-15, docs audit pass:** README rewritten for complete beginners (which-way table, terminals, Python per OS, Cloud Shell re-paste safety, update/delete, troubleshooting, command-line examples with the bundled photo, settings table with app labels and `--set` names). HANDOFF sections 1, 2, 3 and 5 refreshed. Removed the synthetic test files (`tests/run_local.py`, `make_sample.py`, `sample_tile.jpg`, `check_watertight.py`), since the owner's rule is to test only on the owner's photos. Dockerfile comments reworded. No code behaviour changed.

- **2026-10-15, owner decisions:** corners for the fixture set confirmed by the owner; IMG_9391 (heron) removed from the set at the owner's request (now 18 photos); old empty GCP project `tw-tile-gen` (mixoadrian) deleted (DELETE_REQUESTED, recoverable 30 days).

- **2026-10-15, textured exports + command line:** new formats `3mftex` (3MF Materials-extension texture2dgroup per corner; slicer part table unchanged so it prints in glaze colours) and `glbtex` (trimesh PBR baseColorTexture); pad stays plain. `tests/check_formats.py` checks all (IMG_9255: corner-UV error 0.00001; three.js 3MFLoader renders the textured 3MF). App menu groups formats by Glaze colours / Photo texture. **`scripts/mixo.py`** (+ `mixo.bat`, `mixo.sh`): command line without the web page, local (re-runs itself in `.venv`) or `--server URL`, `--corners`, `--corners-json` batch, `--set name=value`; tested local single + batch. README: "Without the web page" guide + with/without-UI × online/local table. Live site verified after the memory fix: 2 tiles in a row OK on cloud.

- **2026-10-15, new fixture set + Photo preview + cloud memory/speed:**
  - **Fixtures replaced by the owner:** they deleted the 16-tile set, the `originals/` duplicates and the museum crops, and left 19 hand-picked photos in `backend/tests/fixtures/real_tiles/originals/IMG_*.jpg` (3024 px). New `corners.json` = `{"IMG_xxxx": [[x,y] TL,TR,BR,BL]}` in photo pixels (10 auto-proposed from the wooden-frame opening, 9 read by eye; all checked by flattening). All test scripts read them (no more /2048 scaling). `check_colours.py` / `check_symmetry.py` removed (museum images). Rule: test only on these; if the folder changes, the owner is curating, so ask before restoring.
  - **3D preview Colours | Photo switch:** the stream now sends `{"type":"texture","bytes":N}` + a 1024 px JPEG (same warp as the geometry) after the preview mesh; the browser adds top-down UVs (u = x/size, v = y/size) and swaps materials. Pad stays plain in Photo view. Header wraps on phones (tested 360/390/1280).
  - **AI wording:** after auto-detect: "AI suggestion: check that the 4 corners sit on the glaze edges…". The AI only suggests; the person confirms (owner's rule).
  - "Try a sample" = owner's IMG_9255 (roses), 1600 px, corners pre-placed, no auto-detect.
  - **Cloud Run memory bug found and fixed:** a 2nd tile in a row on 3024 px photos hit "Memory limit of 2048 MiB exceeded" (503). Now 4 GiB, and `main.py` calls `malloc_trim(0)` after each tile. **Speed:** desktop 10–12 s/tile; Cloud Run 2 vCPU ≈ 25 s (thread caps didn't help); 4 vCPU + `MIXOTILE_BODY_WORKERS=2` ≈ 17–19 s. Deploy flags now `--cpu 4 --memory 4Gi`, env `MIXOTILE_BODY_WORKERS=2` (README Option B updated).

- **2026-10-15, engine on Google Cloud Run + hard spending cap + local self-hosting (IN PROGRESS):**
  - (Superseded: the engine is on Cloud Run, see above.) Hugging Face is out: as of 2026 free accounts get `402 Payment Required` for Docker/Gradio Spaces on cpu-basic (PRO only). Owner chose Google Cloud Run with a card on file and a cap.
  - Repo renamed `tw-tile-gen` -> **`mixo-tile-gen`** (github.com/mixocreative/mixo-tile-gen, Pages https://mixocreative.github.io/mixo-tile-gen/). Product name changed everywhere (commit 003a33e).
  - GCP (account mixocreative@gmail.com, gcloud at `%LOCALAPPDATA%\Google\Cloud SDK\google-cloud-sdkin\gcloud.cmd`, not on PATH; use PowerShell for JSON args):
    - Project `mixo-tile-gen`, billing account `018205-9A5C87-68D277` (TWD). Old project `tw-tile-gen` under mixoadrian: empty, owner not asked to delete yet.
    - **Engine live:** https://mixo-tile-gen-616971929665.asia-east1.run.app (was 2 vCPU, 2 GiB, now 4 vCPU, 4 GiB with `MIXOTILE_BODY_WORKERS=2`; concurrency 1, **max-instances 1**, min 0, timeout 300, `ALLOWED_ORIGINS=https://mixocreative.github.io`). `/health` OK, CORS verified (other origins rejected).
    - Fresh-project gotchas hit: Artifact Registry 403 right after enabling the API (wait/retry), and the compute default SA needed `cloudbuild.builds.builder`, `storage.objectViewer`, `artifactregistry.writer`, `logging.logWriter`.
    - **Spending cap:** budget `mixo-tile-gen-cap` = NT$30 (50/90/100 % thresholds) -> Pub/Sub topic `budget-alerts` -> Cloud Run function `budget-killswitch` (`ops/budget_killswitch/`, SA `budget-killswitch@` with `billing.projectManager` + `browser` on the project, `run.invoker` on the function). At cost >= budget it unlinks billing (engine stops; nothing more can be charged). **Verified end to end:** below-budget alert = no action; fake over-budget alert = billing disabled; then relinked by hand (`gcloud billing projects link mixo-tile-gen --billing-account=018205-9A5C87-68D277`). Budget data lags a few hours, so a small overshoot is possible; max-instances 1 bounds it.
  - **Local self-hosting (verified):** `scripts/run_local.py` (+ `start-windows.bat`, `start-windows-phone.bat`, `start-mac-linux.sh`): makes `.venv`, installs `backend/requirements.txt` (pins relaxed to `>=` on Python 3.14+, since numpy 2.2.6 has no 3.14 wheel; wrappers prefer 3.13/3.12/3.11), runs uvicorn with `FRONTEND_DIR` so the engine also serves the website (new mount at the end of `main.py`), opens `http://localhost:8088/?api=self` (new `?api=self` = same origin in `apiBase()`). `--phone`: same-Wi-Fi link + free Cloudflare quick tunnel (`cloudflared` auto-downloaded to `tools/`), writes `tools/phone.html` with QR codes.
  - Local launcher verified end to end: fresh `.venv` install on Python 3.13, `--phone` gave a same-Wi-Fi link + `https://*.trycloudflare.com` link; a tile generated through the tunnel at 390 px width in 13 s, `.3MF` downloaded, all 9 parts closed (edge check by index). Note: trimesh with `process=True` reports them open because 3-decimal rounding makes distinct vertices coincide; slicers don't merge, so it's harmless.
  - **New download formats** (`output_format`): `stl` (zip, one binary STL per colour; pinch vertices nudged 0.002 mm so STL welding stays manifold), `obj` (zip, OBJ+MTL, one object per colour), `objtex` (zip, OBJ+MTL+`texture.jpg` 2048 px: the same warp as the geometry, projected top-down, u = x/size, v = y/size; the pad keeps a plain colour because its sides would streak; OBJ numbers v and vt separately, so faces carry their own vt index). STEP deliberately not offered (faceted STEP of ~1 M triangles is impractical). `backend/tests/check_formats.py <tile>` verifies all three (STL closed per colour, materials, face-followed UV error < 1e-4, photo-under-body colour vs glaze colour, with a flipped-texture control). UI: "Other formats" select in the preview footer (re-runs the engine, ~10 s).
  - **UI:** header **AI pill** (loading / on / off · manual); when the AI can't load the app stays in 4-corner manual mode and hides Tap-to-detect / Detect-again (tested by blocking the MediaPipe URLs). Desktop: drag-and-drop anywhere + Ctrl+V paste, "Take photo" only on touch devices (`pointer: coarse`). "Try a sample" now loads the owner's 09 rose photo (`frontend/samples/rose.jpg` at the time; now `roses.jpg` = IMG_9255, 1600 px) with measured corners, no auto-detect.
  - **Found: `corners.json` is inaccurate.** Drawing the stored corners on the 16 fixtures shows most fall 5–9 % short on the right/bottom (e.g. 09: stored BR (1590,1610), measured (1689,1717) in 2048 units). Photo-vs-render sheets so far were consistent (same corners for both) but trimmed the outer strip. Next: re-measure all 16 from zoomed corner crops and update `corners.json` (values only; the photos stay untouched).
  - Owner rule (2026-10-15): test **only** with the owner's photos in `real_tiles/` (16 then, 18 now), never the museum crops or synthetic images.

- **2026-10-15, ship round (published):**
  - Repo https://github.com/mixocreative/mixo-tile-gen (public), Pages live at https://mixocreative.github.io/mixo-tile-gen/.
  - **UI redesign** via Stitch (project 11051604963556458741, `.stitch/DESIGN.md`): warm monochrome palette (ink #1c1a17 → paper #faf8f5), Geist + Geist Mono, compact 32 px controls (38/44 px on touch), hairline numbered sections, phone bottom step nav. Owner rule: everything monochrome **except the original coloured tile logo/favicon**. All original element IDs kept.
  - Defaults changed: backing pad **15 mm** (max-relief cap = width/10 applies above the base only), smoothing **1.2** (app and backend in sync).
  - Streaming `/process-tile?stream=true`: NDJSON progress → binary preview mesh → 3MF bytes; preview opens before the file is ready.
  - Dockerfile runs as uid 1000 (non-root), port 8080.
  - (Superseded by the Cloud Run entry above; nothing to deploy to Hugging Face.) Hosting: owner won't pay → **Hugging Face Space** (Docker, free) on a *different* HF account than `mixoadrian`. Not deployed yet: owner must log in on this PC (`python -c "from huggingface_hub import login; login()"`, Write token). Then create Space `mixo-tile-gen` (README front matter `sdk: docker`, `app_port: 8080`), set variable `ALLOWED_ORIGINS=https://mixocreative.github.io`, test `/health`, set `DEFAULT_API` in `frontend/index.html`, push. Until then the live site shows "Engine: not set".
  - Empty GCP project `tw-tile-gen` exists under mixoadrian (no billing); owner hasn't said whether to delete it.
  - Final 16-tile run through the new UI: all OK, corner drift 0.0, 150 × 150 × 19.4–19.9 mm, 6.6–12.3 s per tile. One-off: tile 15's first screenshot showed the camera zoomed in (not reproduced on re-run; watch for it).
  - Results table: `docs/results/all_tiles.jpg` (built by `backend/tests/make_table.py <renders_dir> <out.jpg>` from Playwright renders `previews/user_*.png`).

- **2026-10-15, raised outlines (Fable, owner-delegated):** tube-lining detection + geometry ridge shipped (`detect_outlines`, `snap_outline_colours`, `ridge_dist` in `cushion_body_mesh`/`build_relief`/`process_tile`; new settings `outline_height_mm`/`outline_width_mm` in TileConfig, main.py Form, frontend). Verified: all 7 bodies watertight (the old synthetic-photo script is gone); `run_real.py` on 02/04/06/09/16 all bodies watertight (16–24 s each, 2 GiB); 16-tile sheet `docs/research/lines_final.jpg` (detection 0.3–0.6 s/tile). Recovered ≈ 85–90 % of visible tube-lines on 09/02/04/10/11/14; crazing (16) and the museum-card tangle (05) are rejected; residual false positives: glossy mane highlights on 06 and specular ridges on 07 petals. `tests/run_real.py` and `tests/lines_sheet.py` now read `tests/fixtures/real_tiles` by default.

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

## 5. Next steps

1. **Re-render the photo-vs-render table** `docs/results/all_tiles.jpg` from the 18 current photos (Playwright: load each photo, drag corners from `corners.json`, generate, screenshot `#viewer` to `previews/user_<name>.png`, then `python backend/tests/make_table.py previews docs/results/all_tiles.jpg`).
2. **Outlines, known limits to improve:** (a) glossy modelled glaze still yields highlight streaks (candidates: both-flank symmetry test, structure-tensor orientation coherence); (b) a tube-line that coincides with a colour seam is drawn only by the groove (ridge faded within 1.6 mm of seams), so a dedicated line body would be needed to raise it; (c) 0.3-0.5 mm hair lines are below the 0.4 mm width gate by design.
3. **A better framed-tile auto-outline:** detect the inner glaze rectangle with OpenCV, or tap-to-detect with a larger mask target (the AI sometimes grabs a sliver of the frame on IMG_9255 and IMG_9343).
4. **Pale glaze inside a shiny motif** can still quantise to cream and split a colour; the highlight-absorb step doesn't cover it.

## 6. Gotchas

- Cloud Run rejects non-streamed responses over 32 MiB (textured .glb is ~41 MB): `main.py` sends files chunked (StreamingResponse) in both the plain and the streamed path. Verified: online `mixo --format glbtex` 41 MB OK.
- In Git Bash, a heredoc that writes Python containing `'\\n'` gets mangled. Write files with an editor tool or `<<'EOF'` plus plain `\n` inside a Python script, and run `python -c "import ast; ast.parse(...)"` after editing.
- Windows Python can't see Git-Bash `/tmp`. Use the project dir or the scratchpad.
- The browser caches `index.html`, so add `&v=<n>` to the URL.
- Wikimedia rate-limits fast API calls (HTTP 429). Sleep about 6 s between calls and send a User-Agent.
- PrusaSlicer CLI with `--wipe-tower` needs `--use-relative-e-distances`, and it segfaulted once with ad-hoc CLI settings. That's not the model's fault.
