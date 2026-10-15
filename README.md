# tw-tile-gen · 花磚 3D relief generator

Turn a phone photo of a traditional Taiwanese majolica tile (花磚) into a watertight, multi-colour 3D relief (`.3MF`, optional `.GLB`) ready for multi-material 3D printing.

**Live app:** https://mixocreative.github.io/mixo-tile-gen/
**Backend:** Python engine on Hugging Face Spaces (free, no card). It's Google Cloud Run-ready too; see the [step-by-step guide](#set-it-up-yourself-step-by-step-guide-no-experience-needed).

![16 real tiles: photo vs generated relief](docs/results/all_tiles.jpg)

---

## Why you'll love it

**Point your phone at a tile. Get a 3D-printable copy in about 10 seconds.** There's nothing to install, no account, and it's free.

- **📸 Snap it, done.** Take a photo of any tile: in a museum, on an old house, at a flea market. Crooked angles are fine; the app straightens them for you.
- **🤖 It finds the tile for you.** Google's on-device AI outlines the tile in your browser, and your photo never leaves your phone for that step. You can nudge the four corners with your finger if you want it perfect.
- **🎨 It understands colours.** It works out the glaze colours by itself: up to 8 by default, or pick your own with a tap. Shadows and shine on the glaze don't fool it into inventing extra colours.
- **🏺 It looks like real ceramic, not a stack of pancakes.** Every colour swells gently like glaze, and the edges roll softly down into the seams, the way a real pressed tile does. The thin raised outlines that make 花磚 special are found and rebuilt as smooth ridges.
- **🧩 Ready to print in colour.** Each colour is its own piece, cut to fit its neighbours exactly like a jigsaw, so you can print it in several colours in one go. Want a tiny gap so the pieces snap together? Set the **clearance**.
- **👀 See it before you print.** Spin, zoom and inspect a live 3D preview right in the browser while the file finishes, then download the `.3MF` (or `.GLB`).
- **⏱️ Fast and honest.** A real progress bar shows what's actually happening ("Carving colour 3 of 8…"), with time left. It's usually about 10 seconds.
- **🛠️ Make it yours.** Every setting is a simple number in millimetres. Go big (a 30 cm wall plaque) or tiny (a 5 cm fridge magnet; small tiles automatically get bolder relief so detail survives printing). Change the base thickness, how high the colours rise, how round the edges are, how strong the outlines are, the gaps between pieces, the colour count, the mesh smoothness and more.
- **📱 Works on your phone.** It's designed for phones first: big enough to tap, small enough to stay out of the way.
- **🆓 Free and open.** The website runs on GitHub Pages and the engine on a free Hugging Face Space. Want your own copy? Follow the [step-by-step guide](#set-it-up-yourself-step-by-step-guide-no-experience-needed); no coding needed.

**Fun ideas:** coasters 🍵 · fridge magnets 🧲 · a wall of your neighbourhood's tiles 🏘️ · gifts from a trip to Taiwan 🎁 · restoring a missing tile in an old floor 🔧 · class projects about Taiwanese heritage 🏫

## What it does

1. **Capture.** Snap or upload a photo of a tile. The photo is never stored.
2. **Outline.** On-device AI (Google AI Edge / MediaPipe Interactive Segmenter) suggests the tile's four corners.
   - Drag the yellow handles to fine-tune; a magnifier appears while you drag. A manual edit always wins over the AI.
   - Or switch to **Square crop** (Cropper.js). This is also the automatic fallback if the AI model can't load.
3. **Colours.** Tap glaze colours on the flattened tile with the eyedropper, or leave it on **auto**, which picks 3–8 colours.
4. **Proportions.** Set the tile size and relief settings. The defaults are tuned for a realistic 150 mm tile.
5. **Generate.** A real progress bar shows the server's actual stages. The 3D preview opens as soon as the shape is ready, while the printable file finishes.
6. **Download** a `.3MF`. It's one object with one named part per colour, each pre-assigned its own extruder; it opens in PrusaSlicer, OrcaSlicer and Bambu Studio. `.GLB` is optional.

## How the relief is built (design decisions)

These rules came out of many review rounds with the owner. Keep them unless the owner changes them.

| Rule | Why |
|---|---|
| **Every colour is equal.** There is no "background" colour and no height tiers by colour. | A photo doesn't tell you which colour is the ground. |
| **Carve the edges.** Every colour starts at the shared full height; the surface then rolls down smoothly into a soft V-valley at each seam. | On a real tile, glaze fields sit level and only the edges round off. Two neighbouring rectangles give a lowercase **"m"** in cross-section. |
| **Big areas are near-level**, with a gentle crown that flattens as the area grows. Thin strokes stay lower and round. | Looks like pressed, glazed ceramic. |
| **Raised outlines (tube-lining).** Thin light or dark lines are found on the photo itself and become a smooth 0.8 mm ridge. | They are the signature of majolica tiles and are often almost the same colour as their neighbour. |
| **Puzzle-piece borders.** All colours are cut from one shared partition, so neighbours meet exactly with no gap and no overlap. An optional **clearance** leaves a slot between pieces. | Clean multi-material prints; print pieces separately if you like. |
| **Watertight bodies.** Every part is a closed, manifold mesh, checked on every change. | Slicers need it. |

Pipeline (`backend/tile_processor.py`):

```
photo ─► perspective warp (4 corners, 1.5 % inset) ─► colours: bilateral + mean-shift,
k-means (12) in L-weighted Lab, merge shading bands, auto-k (≤ 8) ─► clean-up: majority filter,
speck removal (keeps long thin strokes and high-contrast details), highlight absorb
─► outline detection (morphological top/black-hat on L, skeleton, ridge distance)
─► shared partition φᵢ = (dᵢ − min over other colours dⱼ)/2 ─► per colour: screened-Poisson seam distance →
"carve the edges" height field + outline ridge ─► marching cubes ─► manifold-checked decimation
─► backing pad (rounded slab) ─► .3MF (PrusaSlicer-family part table) / .GLB
```

### Default settings (150 mm tile)

| Setting | Default | Meaning |
|---|---|---|
| Tile width | 150 mm | Historic 6-inch majolica size. Changing it re-tunes the relief settings below in proportion. |
| Max relief height | width ÷ 10 | The relief above the base never exceeds this. |
| Backing pad | 15 mm | Solid base slab. |
| Edge depth | 3.0 mm | How far each colour rolls down into its seams. |
| Edge roll width | 6.0 mm | Seam to full height. Wider gives a softer valley. |
| Top crown | 1.0 mm | Gentle dome; leveler on bigger areas. |
| Groove floor | 0.4 mm | Material under the seams (2 print layers). |
| Raised outlines | 0.8 mm high, 1.2 mm wide | 0 turns it off. |
| Clearance between colours | 0 mm | 0 is a flush fit; e.g. 0.3 leaves slots. |
| Max colours | 8 | Auto picks 3 up to this. |
| Mesh smoothness | 0.16 mm | Finer than this runs out of memory on a 2 GiB Cloud Run instance, so the server enforces it. |

A 150 mm tile is about 19 mm tall (15 mm base plus about 4 mm relief) and about 0.9–1.6 M triangles; the `.3MF` is 9–15 MB.

## Performance

All numbers were measured under exact Cloud Run limits (2 vCPU, 2 GiB, no swap) on the 16 real test tiles.

- **Server:** 5–9 s per tile. Peak memory is about 1.5 GB.
- **In the app, warm server:** the 3D preview is on screen in about 7 s and the download is ready in about 8.5 s. The page never freezes for more than about 1 s.
- **Cold start:** the free tier sleeps when idle, so the first request after a quiet spell adds roughly 20–40 s. To hide this, the app wakes the server as soon as a photo is loaded, and the progress bar says so if it's still waking.

## Set it up yourself: step-by-step guide (no experience needed)

The app has two halves:

| Half | What it is | Where it runs | Cost |
|---|---|---|---|
| **Website** (front end) | The page you open in a browser. | GitHub Pages (`github.io`) | Free |
| **Engine** (back end, Python) | Turns the photo into the 3D file. | **Hugging Face** *or* **Google Cloud** *or* **your own computer** | Free (Google needs a card on file) |

The website only *talks to* an engine. You set up one engine, then **connect** the website to it.

> **Just want to use it?** Open https://mixocreative.github.io/mixo-tile-gen/ and skip this whole section.

---

### Option A: Hugging Face (free, no credit card, recommended)

You only need a web browser.

1. **Create a free account** at https://huggingface.co/join and confirm your email.
2. **Get the engine files.** On https://github.com/mixocreative/mixo-tile-gen click the green **Code** button, then **Download ZIP**. Unzip it. You need 4 files from the `backend` folder:
   - `Dockerfile`
   - `main.py`
   - `tile_processor.py`
   - `requirements.txt`
3. **Create the Space.** Go to https://huggingface.co/new-space:
   - **Space name:** `tw-tile-gen`
   - **License:** your choice
   - **Select the Space SDK:** **Docker**, then **Blank**
   - **Hardware:** *CPU basic · free*
   - **Visibility:** **Public**. The website needs to reach it.
   - Click **Create Space**.
4. **Upload the files.** In your new Space, open **Files**, then **+ Add file → Upload files**. Drag in the 4 files from step 2 and click **Commit changes to main**.
5. **Tell it which port to use.** Still in **Files**, click `README.md`, then **Edit**. In the block between the two `---` lines at the top, add this line, then click **Commit changes**:
   ```
   app_port: 8080
   ```
6. **Allow your website to talk to it.** Go to **Settings → Variables and secrets → New variable**:
   - **Name:** `ALLOWED_ORIGINS`
   - **Value:** `https://mixocreative.github.io`. If you made your own website copy (Option D), use `https://YOUR-GITHUB-NAME.github.io`.
   - Save. The Space rebuilds by itself.
7. **Wait for "Running".** The status badge next to the name goes *Building → Running*. The first build takes about 5–10 minutes.
8. **Find your engine address.** It's `https://YOUR-HF-NAME-tw-tile-gen.hf.space`, in lower case. To test it, open `https://YOUR-HF-NAME-tw-tile-gen.hf.space/health`. You should see `{"status":"ok", …}`.
9. **Connect the website.** See [Connect the website to your engine](#connect-the-website-to-your-engine) below.

> **Note:** a free Space goes to sleep after about 2 days with no visitors. The next visitor wakes it up, which takes about 1 minute; the progress bar says "Waking up the server".

---

### Option B: Google Cloud Run

You need a Google account, and Google requires a credit card on file even for its free tier. Normal use of this app stays within the free tier, but check your billing page now and then.

1. **Create a project.** Open https://console.cloud.google.com, click the project picker at the top, choose **New Project**, name it `tw-tile-gen`, and click **Create**.
2. **Turn on billing.** Go to **☰ Menu → Billing** and link a billing account (card) to the project. Optionally, under **Budgets & alerts**, set a budget of US$1 so Google emails you if anything is ever charged.
3. **Open Cloud Shell.** Click the **>_** icon at the top right of the console. A terminal opens in your browser, so nothing needs installing.
4. **Paste these lines** into Cloud Shell, one block at a time. Press **Enter** after each, and click **Authorize** if asked.
   ```bash
   git clone https://github.com/mixocreative/mixo-tile-gen.git
   cd mixo-tile-gen
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
   ```
   ```bash
   gcloud run deploy tw-tile-gen --source backend --region asia-east1 \
     --allow-unauthenticated --cpu 2 --memory 2Gi --concurrency 1 --timeout 300 \
     --min-instances 0 --max-instances 3 \
     --set-env-vars ALLOWED_ORIGINS=https://mixocreative.github.io
   ```
   If it asks *"Allow unauthenticated invocations?"*, answer **y**. If it asks to create an Artifact Registry repository, answer **y**.
5. **Copy the address.** After 5–10 minutes the last line shows `Service URL: https://tw-tile-gen-xxxxx.asia-east1.run.app`. Open it with `/health` added on the end; you should see `{"status":"ok", …}`.
6. **Connect the website.** See the next section.

`asia-east1` is Taiwan. Pick a region near your users. `--memory 2Gi` is required; the engine needs it.

---

### Option C: on your own computer

**The easy way, with Docker:**
1. Install **Docker Desktop** (https://www.docker.com/products/docker-desktop/) and start it.
2. Download the project ZIP (Option A, step 2) and unzip it.
3. Open a terminal *inside the unzipped folder*. On Windows: open the folder, then right-click → **Open in Terminal**. On macOS: right-click the folder → **New Terminal at Folder**. Then run:
   ```bash
   docker build -t tw-tile-gen backend
   docker run --rm -p 8088:8080 tw-tile-gen
   ```
   Leave that window open; it is the engine.
4. In a **second** terminal, in the same folder, start the website:
   ```bash
   python -m http.server 8790 --directory frontend
   ```
5. Open **http://localhost:8790/?api=http://localhost:8088**. The engine is connected automatically.

**Without Docker (Python only):** install Python 3.11 or newer from https://www.python.org/downloads/ and tick **"Add Python to PATH"**. Then:
```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --port 8088
```
Then do steps 4 and 5 above.

---

### Connect the website to your engine

**Way 1, for yourself (no coding):**
1. Open the website (https://mixocreative.github.io/mixo-tile-gen/, or your own copy).
2. Click the pill at the **top right** that says *Backend: …*.
3. Paste your engine address, e.g. `https://YOUR-HF-NAME-tw-tile-gen.hf.space`, with no `/health` on the end.
4. Click **Save & test**. The dot turns green and says *Backend: ready*. Your browser remembers the address.

**Way 2, a link to share:** add `?api=` and your engine address to the website link, e.g.
`https://mixocreative.github.io/mixo-tile-gen/?api=https://YOUR-HF-NAME-tw-tile-gen.hf.space`

**Way 3, make it the default for everyone (your own copy):** in `frontend/index.html`, find `const DEFAULT_API = '…';` and put your engine address between the quotes. Then commit; your website updates in about a minute.

**If the dot is red ("unreachable"):**
- Check the address works on its own with `/health` added.
- Check the engine's `ALLOWED_ORIGINS` exactly matches your website's address: `https://NAME.github.io`, with no path and no trailing `/`.
- A sleeping Hugging Face Space takes about a minute to wake. Try again.

---

### Option D: your own copy of the website (GitHub Pages)

1. Create a free account at https://github.com/signup.
2. Open https://github.com/mixocreative/mixo-tile-gen and click **Fork**, then **Create fork**.
3. In your fork, go to **Settings → Pages**. Under **Build and deployment → Source**, choose **GitHub Actions**.
4. Go to the **Actions** tab, click **Deploy frontend to GitHub Pages**, then **Run workflow**.
5. After about a minute your website is at `https://YOUR-GITHUB-NAME.github.io/mixo-tile-gen/`.
6. Connect it to your engine (previous section). Remember the engine's `ALLOWED_ORIGINS` must be `https://YOUR-GITHUB-NAME.github.io`.

## API

- `GET /health` returns `{"status":"ok"}`.
- `POST /process-tile` takes `multipart/form-data`:
  - **Required:** `image`.
  - **Optional:** `corners` (JSON `[[x,y]×4]`), `swatches` (JSON hex list), plus any setting above, using the names in `TileConfig`: `tile_size_mm`, `pad_thickness_mm`, `relief_height_mm`, `fillet_radius_mm`, `dome_height_mm`, `groove_floor_mm`, `clearance_mm`, `outline_height_mm`, `outline_width_mm`, `num_colors`, `mesh_resolution_mm`, `symmetry`, `output_format` (`3mf`|`glb`).
- `stream=false` (default) returns the model bytes, plus stats in the `X-MixoTile-Stats` header.
- `stream=true` returns a single streamed response, used by the app:
  - JSON lines: `{"type":"progress","p":0.42,"msg":"Carving colour 3 of 8"}`.
  - Then `{"type":"preview","layout":[…],"bytes":N}` followed by N bytes of preview mesh (float32 positions and uint32 indices per part).
  - Then `{"type":"done","bytes":M}` followed by M bytes of model, or `{"type":"error",…}`.

## Tests and verification

The owner's **16 real tile photos are a permanent regression set**: `backend/tests/fixtures/real_tiles/` (see its README). Every pipeline change must pass on all 16:

```bash
# in the image, with Cloud Run limits (one tile per process)
docker run --rm -m 2g --memory-swap 2g --cpus 2 -v "$PWD:/repo" -w /repo/backend tw-tile-gen \
  python tests/check_borders.py 09_single_rose 0     # watertight + puzzle-fit (gap/overlap) + time
python tests/run_local.py        # synthetic sample, end to end
python tests/lines_sheet.py      # visual sheet: photo | outlines | colours | height map
```

`HANDOFF.md` has the full engineering log, the design decisions and the next steps, for whoever picks this up (human, Claude, or Codex). `AGENTS.md` has the rules for coding agents.

## Known limits

- **Auto-outline:** the AI can lock onto the wooden frame or the motif on framed museum tiles. Drag the corners, or use Square crop.
- **Glossy, painterly glazes** can still split into small patches. Examples: the shiny rose leaves and the lion's mane.
- **Stickers** on the glaze (e.g. "61", "75") become relief. The glare/sticker inpaint is implemented but off by default, because it also erased real white glaze.

## Credits

- **Owner's tile photos:** taken at the Museum of Old Taiwan Tiles (台灣花磚博物館), Chiayi.
- **`backend/tests/fixtures/museum_wikimedia/`:** crops of "Interior of the Museum of Old Taiwan Tiles-03" by 阿道, CC BY-SA 4.0, via Wikimedia Commons.
- **Built with:** FastAPI, OpenCV, scikit-image, scikit-learn, SciPy, fast-simplification, trimesh; Three.js, MediaPipe Tasks Vision, Cropper.js and Tailwind (via CDN).
