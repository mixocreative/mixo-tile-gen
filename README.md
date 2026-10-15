# mixo-tile-gen · 花磚 3D relief generator

Turn a phone photo of a traditional Taiwanese majolica tile (花磚) into a watertight, multi-colour 3D relief (`.3MF`, plus `.GLB`, `.STL` and `.OBJ`, even one wearing your photo as a texture) ready for multi-material 3D printing.

**Live app:** https://mixocreative.github.io/mixo-tile-gen/
**Engine:** Python, running on Google Cloud Run (with a hard spending cap). You can also run the whole app on your own computer with one double-click, phone included; see the [step-by-step guide](#set-it-up-yourself-step-by-step-guide-no-experience-needed).

![Real tiles: photo vs generated relief](docs/results/all_tiles.jpg)

---

## Why you'll love it

**Point your phone at a tile. Get a 3D-printable copy in about 10 seconds.** There's nothing to install, no account, and it's free.

- **📸 Snap it, done.** Take a photo of any tile: in a museum, on an old house, at a flea market. Crooked angles are fine; the app straightens them for you.
- **🤖 It finds the tile for you.** Google's on-device AI outlines the tile in your browser, and your photo never leaves your phone for that step. You can nudge the four corners with your finger if you want it perfect.
- **🎨 It understands colours.** It works out the glaze colours by itself: up to 8 by default, or pick your own with a tap. Shadows and shine on the glaze don't fool it into inventing extra colours.
- **🏺 It looks like real ceramic, not a stack of pancakes.** Every colour swells gently like glaze, and the edges roll softly down into the seams, the way a real pressed tile does. The thin raised outlines that make 花磚 special are found and rebuilt as smooth ridges.
- **🧩 Ready to print in colour.** Each colour is its own piece, cut to fit its neighbours exactly like a jigsaw, so you can print it in several colours in one go. Want a tiny gap so the pieces snap together? Set the **clearance**.
- **👀 See it before you print.** Spin, zoom and inspect a live 3D preview right in the browser while the file finishes. Flip it between **Colours** (one glaze colour per part, as it will print) and **Photo** (your actual photo wrapped onto the relief), then download the `.3MF`, or `.GLB`, `.STL` or `.OBJ`. The **photo-textured `.OBJ`** wraps your actual photo onto the relief, so it looks like the real tile in Blender, games or AR.
- **⏱️ Fast and honest.** A real progress bar shows what's actually happening ("Carving colour 3 of 8…"), with time left. It's usually about 10 seconds.
- **🛠️ Make it yours.** Every setting is a simple number in millimetres. Go big (a 30 cm wall plaque) or tiny (a 5 cm fridge magnet; small tiles automatically get bolder relief so detail survives printing). Change the base thickness, how high the colours rise, how round the edges are, how strong the outlines are, the gaps between pieces, the colour count, the mesh smoothness and more.
- **📱 Works on your phone.** It's designed for phones first: big enough to tap, small enough to stay out of the way.
- **🆓 Free and open.** The website runs on GitHub Pages and the engine on Google Cloud Run's free allowance, or entirely on your own computer for free. Want your own copy? Follow the [step-by-step guide](#set-it-up-yourself-step-by-step-guide-no-experience-needed); no coding needed.

**Fun ideas:** coasters 🍵 · fridge magnets 🧲 · a wall of your neighbourhood's tiles 🏘️ · gifts from a trip to Taiwan 🎁 · restoring a missing tile in an old floor 🔧 · class projects about Taiwanese heritage 🏫

## What it does

1. **Capture.** On a phone: **Take photo** or **Upload** (camera roll / files). On a computer: **Upload**, **drag and drop** the photo onto the page, or **paste** it (Ctrl+V). No photo handy? **Try a sample** loads one of the real test tiles. The photo is never stored.
2. **Outline.** On-device AI (Google AI Edge / MediaPipe Interactive Segmenter) suggests the tile's four corners.
   - Drag the white corner handles to fine-tune; a magnifier appears while you drag. A manual edit always wins over the AI.
   - Or switch to **Square crop** (Cropper.js).
   - The **AI pill** at the top shows *AI: on / loading / off*. If the AI can't load (old phone, blocked network, offline), the app says **AI off · manual** and you simply drag the 4 corners yourself; everything else works the same. The 3D engine itself uses no AI.
3. **Colours.** Tap glaze colours on the flattened tile with the eyedropper, or leave it on **auto**, which picks 3–8 colours.
4. **Proportions.** Set the tile size and relief settings. The defaults are tuned for a realistic 150 mm tile.
5. **Generate.** A real progress bar shows the server's actual stages. The 3D preview opens as soon as the shape is ready, while the printable file finishes.
6. **Download** a `.3MF`. It's one object with one named part per colour, each pre-assigned its own extruder; it opens in PrusaSlicer, OrcaSlicer and Bambu Studio. **Other formats** (menu next to the button; each takes about 10 s more):

   Every format comes in two looks: **glaze colours** (one flat colour per part, exactly what prints) or **photo texture** (your photo projected straight down onto the relief, lined up exactly; the backing pad keeps a plain colour because its sides would show streaks). The 3D preview has the same **Colours | Photo** switch.

   | Format | Glaze colours | Photo texture | Use it for |
   |---|---|---|---|
   | `.3MF` | ✓ (the main download) | ✓ `.textured.3mf`: viewers show the photo, slicers still print it in glaze colours | 3D printing |
   | `.GLB` | ✓ | ✓ `.textured.glb` | Web viewers, AR, quick sharing |
   | `.OBJ` (zip) | ✓ OBJ + MTL, one object per colour | ✓ OBJ + MTL + `texture.jpg` | Blender, CAD, rendering, games |
   | `.STL` (zip) | ✓ one STL per colour, all lined up | (STL can't hold colour or texture) | Any slicer: load them together, one filament each |

   STEP isn't offered: it's a format for exact CAD surfaces, and a relief of about a million triangles turns into a huge STEP that CAD programs choke on. Import the STL or OBJ instead.

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
| Mesh smoothness | 0.16 mm | Finer than this needs much more memory per tile, so the server enforces it. |

A 150 mm tile is about 19 mm tall (15 mm base plus about 4 mm relief) and about 0.9–1.6 M triangles; the `.3MF` is 9–15 MB.

## Performance

Measured on the owner's test photos (3024 × 3024):

| Where the engine runs | Time per tile | Notes |
|---|---|---|
| A recent desktop PC (Option A, local) | about 10–12 s | |
| Google Cloud Run, 4 vCPU / 4 GiB (the live site) | about 17–19 s | Google's virtual CPUs are slower than a desktop's. With 2 vCPU it was about 25 s, and 2 GiB ran out of memory on a second tile in a row. |

- Peak memory is about 1.5–2 GB per tile. After each tile the engine hands freed memory back to the system, so tile after tile stays within the limit.
- The 3D preview appears before the printable file is finished, and the page never freezes for more than about 1 s.
- **Cold start:** the cloud engine sleeps when idle, so the first tile after a quiet spell adds roughly 20–40 s. The app wakes it as soon as a photo is loaded, and the progress bar says so if it's still waking.

## Set it up yourself: step-by-step guide (no experience needed)

> **Just want to use it?** Open https://mixocreative.github.io/mixo-tile-gen/. It's already connected to an engine, so skip this whole section.

The app has two halves:

| Half | What it is | Where it can run |
|---|---|---|
| **Website** (front end) | The page you see in the browser. | GitHub Pages (free), or your own computer |
| **Engine** (back end, Python) | Turns the photo into the 3D file. | **Your own computer** (free), or **Google Cloud Run** (online all the time) |

**Every way works with or without the web page.** With the page you click through the steps; without it you use the `mixo` command (see [Without the web page](#without-the-web-page-command-line)), which is handy for batches. Every way has the same features: all download formats, glaze colours or photo texture, and the AI is only an optional helper for finding the tile's corners (without it, you place them yourself).

| | With the web page | Without the web page |
|---|---|---|
| **Online** (nothing to install) | https://mixocreative.github.io/mixo-tile-gen/ | `mixo photo.jpg --server <engine address>` |
| **On your computer** (pure Python, works offline after setup) | double-click `start-windows.bat` (or `./start-mac-linux.sh`) | `mixo photo.jpg` |

Pick where the engine runs:

| | Cost | Works when your computer is off? | Phone? | Difficulty |
|---|---|---|---|---|
| **[A. Your own computer](#option-a-run-everything-on-your-own-computer-free)** | Free | No | Yes, same Wi-Fi or a free Cloudflare link | Easiest: double-click a file |
| **[B. Google Cloud Run](#option-b-google-cloud-run-online-all-the-time-with-a-hard-spending-cap)** | About $0, card required, hard cap | Yes | Yes | Copy and paste 6 blocks |
| **[C. Docker](#option-c-docker-for-tinkerers)** | Free | No | Yes | Needs Docker |

> **What about Hugging Face?** Since July 2026, Hugging Face only runs this kind of engine (a "Docker Space") for paying PRO accounts. If you have PRO, see [the note at the end](#hugging-face-pro-accounts-only).

---

### Option A: run everything on your own computer (free)

Website and engine both run on your computer. Nothing to sign up for.

**1. Install Python (one time).**
- **Windows:** go to https://www.python.org/downloads/ and click the big yellow **Download Python** button. Run the installer, tick **"Add python.exe to PATH"** at the bottom of the first screen, then click **Install Now**.
- **Mac:** same page; open the downloaded `.pkg` and click through.
- **Linux:** usually already installed. You need version 3.11 or newer (`python3 --version`).

**2. Download the app.** On https://github.com/mixocreative/mixo-tile-gen click the green **Code** button, then **Download ZIP**. Unzip it somewhere easy, like your Desktop.

**3. Start it.**
- **Windows:** open the unzipped folder and double-click **`start-windows.bat`**.
  - If a blue "Windows protected your PC" box appears, click **More info → Run anyway**. It's a plain text script you can open in Notepad to check.
- **Mac / Linux:** open Terminal in the folder (Mac: right-click the folder → **New Terminal at Folder**) and run:
  ```bash
  ./start-mac-linux.sh
  ```

The **first start takes 3–10 minutes** because it downloads the engine's parts (about 400 MB). Later starts take about 10 seconds. When you see

```
[mixo] READY  ->  open http://localhost:8088/?api=self
```

your browser opens the app by itself. **Keep the black window open** while you use the app; closing it (or pressing **Ctrl + C**) stops everything.

**4. Use it on your phone (optional).**
- **Windows:** double-click **`start-windows-phone.bat`** instead.
- **Mac / Linux:** run `./start-mac-linux.sh phone`.

A page with **QR codes** opens. Scan one with your phone's camera:

| QR code | When to use it | Notes |
|---|---|---|
| **Same Wi-Fi** | Phone and computer on the same Wi-Fi | Fastest. If it doesn't load, see the firewall tip below. |
| **Anywhere (Cloudflare link)** | Phone on mobile data, or a friend elsewhere | Free [Cloudflare quick tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/). No account needed. The tool downloads itself the first time. |

> 🔒 The Cloudflare link works for **anyone who has it** while the window is open. It's a long random address that changes every time you start, and it stops working when you close the window. Only share it with people you trust.

**Troubleshooting (Option A)**
- **"Python is not installed"** but you did install it: restart the computer, or re-run the installer and tick "Add python.exe to PATH".
- **Windows asks "Allow Python on networks?"** Tick **Private networks** and click **Allow**. The same-Wi-Fi QR code needs this.
- **"port 8088 is busy"**: the app is already running in another window. Use that one, or close it first.
- **Install failed halfway** (internet dropped): delete the `.venv` folder inside the app folder and start again.

---

### Option B: Google Cloud Run (online all the time, with a hard spending cap)

The engine runs on Google's servers, so the website works even when your computer is off. Google's free allowance covers several thousand tiles a month (each tile uses about 20 CPU-seconds), so **normal use costs $0**. Google still requires a card on file, so this guide adds a **kill switch**: if spending ever reaches the cap you choose, billing switches off automatically and nothing more can be charged.

**1. Turn on billing (one time, in the browser).**
1. Open https://console.cloud.google.com/billing.
   > **Several Google accounts?** Google picks the first one. Add `?authuser=you@gmail.com` to the address (for example `https://console.cloud.google.com/billing?authuser=you@gmail.com`), or open a private window (**Ctrl + Shift + N**) and sign in with only the account you want. Check the avatar at the top right.
2. Click **Create account** (or start the **Free trial** if offered). Choose **Individual**, enter your card, and submit. A small temporary card check may appear; it's refunded.

**2. Open Cloud Shell.** Go to https://console.cloud.google.com (same account), then click the **>_** icon at the top right. A terminal opens at the bottom of the page. Nothing to install.

**3. Paste the blocks below one at a time**, pressing **Enter** after each. Click **Authorize** if asked.

Block 1: settings. **Change the first line** to a name that's yours (lower case, letters, digits and dashes, 6–30 characters, must be unique on Google):
```bash
PROJECT=mixo-tile-gen-yourname
REGION=asia-east1        # Taiwan. Others: us-central1, europe-west1, asia-northeast1 ...
SITE=https://mixocreative.github.io   # the website allowed to use your engine (no path, no trailing /)
gcloud billing accounts list
```
The last command shows a table. Copy the **ACCOUNT_ID** of the account with `OPEN True`, then paste this (with your ID):
```bash
BILLING=000000-000000-000000
```

Block 2: project, billing and services:
```bash
gcloud projects create $PROJECT && gcloud config set project $PROJECT
gcloud billing projects link $PROJECT --billing-account=$BILLING
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  cloudfunctions.googleapis.com eventarc.googleapis.com pubsub.googleapis.com \
  billingbudgets.googleapis.com cloudbilling.googleapis.com
NUM=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
for r in cloudbuild.builds.builder storage.objectViewer artifactregistry.writer logging.logWriter; do
  gcloud projects add-iam-policy-binding $PROJECT --member=serviceAccount:$NUM-compute@developer.gserviceaccount.com \
    --role=roles/$r --condition=None --quiet >/dev/null; done
echo OK
```

Block 3: the engine. Takes 5–10 minutes. If it says *Permission denied … Artifact Registry*, wait one minute and paste it again; new projects need a moment.
```bash
git clone https://github.com/mixocreative/mixo-tile-gen.git && cd mixo-tile-gen
gcloud run deploy mixo-tile-gen --source backend --region $REGION --allow-unauthenticated \
  --cpu 4 --memory 4Gi --concurrency 1 --timeout 300 --min-instances 0 --max-instances 1 \
  --set-env-vars ALLOWED_ORIGINS=$SITE,MIXOTILE_BODY_WORKERS=2 --quiet
```
The last line shows `Service URL: https://mixo-tile-gen-….run.app`. **That's your engine address.** Open it with `/health` added; you should see `{"status":"ok", …}`.

Block 4: the kill switch (a tiny function that switches billing off):
```bash
gcloud pubsub topics create budget-alerts
gcloud iam service-accounts create budget-killswitch --display-name=budget-killswitch
KS=budget-killswitch@$PROJECT.iam.gserviceaccount.com
gcloud projects add-iam-policy-binding $PROJECT --member=serviceAccount:$KS --role=roles/billing.projectManager --condition=None --quiet >/dev/null
gcloud projects add-iam-policy-binding $PROJECT --member=serviceAccount:$KS --role=roles/browser --condition=None --quiet >/dev/null
gcloud functions deploy budget-killswitch --gen2 --runtime python312 --region $REGION \
  --source ops/budget_killswitch --entry-point stop_billing --trigger-topic budget-alerts \
  --service-account $KS --set-env-vars TARGET_PROJECT=$PROJECT --memory 256Mi --max-instances 1 --quiet
gcloud run services add-iam-policy-binding budget-killswitch --region $REGION \
  --member=serviceAccount:$KS --role=roles/run.invoker >/dev/null && echo OK
```

Block 5: the budget (the cap). Use your billing account's currency, shown by `gcloud billing accounts describe $BILLING`: for example `30TWD`, `1USD` or `1EUR`.
```bash
gcloud billing budgets create --billing-account=$BILLING --display-name=mixo-tile-gen-cap \
  --budget-amount=1USD --filter-projects=projects/$PROJECT \
  --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0 \
  --notifications-rule-pubsub-topic=projects/$PROJECT/topics/budget-alerts
```
You also get an **email** at 50 % and 90 % of the cap.

Block 6 (optional, recommended): test the kill switch. This pretends the cap was reached, checks that billing went off, then switches it back on:
```bash
gcloud pubsub topics publish budget-alerts --message='{"costAmount": 2, "budgetAmount": 1, "currencyCode": "USD"}'
sleep 60; gcloud billing projects describe $PROJECT --format='value(billingEnabled)'   # should print False
gcloud billing projects link $PROJECT --billing-account=$BILLING >/dev/null; echo "billing back on"
```

**4. Connect the website** to your engine address. See [Connect the website to your engine](#connect-the-website-to-your-engine).

**Good to know**
- **When nobody uses it,** the engine sleeps and costs nothing. The first tile after a quiet spell takes 20–40 s longer while it wakes up; the progress bar says so.
- **If the cap is ever reached,** the engine stops working (the site shows "Engine: unreachable"). To turn it back on, open Billing → **My projects**, then link the project to your billing account again. Google's cost reports lag a few hours, so the final bill can be a few cents above the cap. Allowing only one engine copy at a time (`--max-instances 1`) keeps that small.
- **To remove everything,** go to https://console.cloud.google.com/cloud-resource-manager, select the project and click **Delete**.

---

### Option C: Docker (for tinkerers)

Install **Docker Desktop** (https://www.docker.com/products/docker-desktop/) and start it. In the unzipped app folder:
```bash
docker build -t mixo-tile-gen backend
docker run --rm -p 8088:8080 -v "$PWD/frontend:/frontend" -e FRONTEND_DIR=/frontend mixo-tile-gen
```
Open **http://localhost:8088/?api=self**. On Windows PowerShell use `${PWD}` instead of `$PWD`. Without the `-v … -e …` part you get the engine only, with no website.

---

### Connect the website to your engine

The website needs to know the engine's address. Choose one:

| How | Steps | Best for |
|---|---|---|
| **The Engine pill** | On the website, click the pill at the **top right** ("Engine: …"). Paste your engine address (no `/health` on the end), then **Save & test**. The dot turns green ("Engine: ready"). Your browser remembers it. | Just you |
| **A link** | Add `?api=` plus the address to the website link, e.g. `https://mixocreative.github.io/mixo-tile-gen/?api=https://mixo-tile-gen-xxxx.asia-east1.run.app` | Sharing with friends |
| **The default** (your own copy) | In `frontend/index.html`, find `const DEFAULT_API = '…';` and put your address between the quotes. Commit; your site updates in about a minute. | Everyone who visits your copy |

`?api=self` means "the engine is at this same address". Option A's links use it, because there the engine also serves the website.

**Self-hosting everything?**
- **Option A or C:** the website comes with the engine; nothing to connect.
- **Your own GitHub Pages site + your own Cloud Run engine:** deploy the engine with `SITE=https://YOUR-GITHUB-NAME.github.io` (Option B, block 1), then set `DEFAULT_API` in your copy.
- **Website already deployed and only the allowed site needs changing:** run `gcloud run services update mixo-tile-gen --region $REGION --update-env-vars ALLOWED_ORIGINS=https://YOUR-GITHUB-NAME.github.io`.

**If the dot is red ("unreachable"):**
- Open the engine address with `/health` on the end. If that fails, the engine is off or asleep (or its spending cap was reached).
- The engine's `ALLOWED_ORIGINS` must exactly match your website's address: `https://NAME.github.io`, with no path and no trailing `/`.
- A sleeping engine takes 20–60 s to wake. Try again.

---

### Option D: your own copy of the website (GitHub Pages)

1. Create a free account at https://github.com/signup.
2. Open https://github.com/mixocreative/mixo-tile-gen and click **Fork**, then **Create fork**.
3. In your fork, go to **Settings → Pages**. Under **Build and deployment → Source**, choose **GitHub Actions**.
4. Go to the **Actions** tab, click **Deploy frontend to GitHub Pages**, then **Run workflow**.
5. After about a minute your website is at `https://YOUR-GITHUB-NAME.github.io/mixo-tile-gen/`.
6. Connect it to your engine (previous section).

---

### Hugging Face (PRO accounts only)

Free accounts get `402 Payment Required` when creating a Docker Space. With **PRO**:
1. Create a Space at https://huggingface.co/new-space: SDK **Docker → Blank**, **Public**.
2. Upload `backend/Dockerfile`, `main.py`, `tile_processor.py` and `requirements.txt`.
3. Add `app_port: 8080` to the front matter of the Space's `README.md`.
4. Add the variable `ALLOWED_ORIGINS` = your website (Settings → Variables and secrets).
5. Your engine address is `https://YOUR-HF-NAME-SPACE-NAME.hf.space`.

### Without the web page (command line)

`mixo` makes the same models from the command line: one photo, or a whole folder at once. The files are the same as the website's.

**1. Install Python** and **download the app** (Option A, steps 1 and 2).

**2. Open a terminal in the app folder.** Windows: open the folder, click the address bar, type `cmd` and press Enter. Mac: right-click the folder → **New Terminal at Folder**.

**3. Find your tile's four corners** (in photo pixels). The easiest way is to open the photo in Paint (Windows) or Preview (Mac) and hover over each glaze corner: the position shows at the bottom of the window. Go top-left, top-right, bottom-right, bottom-left. Without corners, `mixo` uses the centred square of the photo.

**4. Run it.** On Mac/Linux, write `./mixo.sh` instead of `mixo`:
```bash
mixo my-tile.jpg --corners "510,564 2616,534 2514,2508 594,2478"
```
The first run sets itself up (3–10 minutes, same as Option A). After that, a tile takes about 10 s and the file lands next to the photo: `my-tile.3mf`.

**More examples:**
```bash
mixo my-tile.jpg --corners "…" --format 3mftex          # 3MF with the photo as a texture
mixo my-tile.jpg --corners "…" --format objtex --out tile.zip
mixo my-tile.jpg --corners "…" --set tile_size_mm=100 --set pad_thickness_mm=8
mixo a.jpg b.jpg c.jpg --corners-json corners.json --out models   # many photos at once
mixo my-tile.jpg --corners "…" --server https://mixo-tile-gen-616971929665.asia-east1.run.app   # use the online engine
```
- `--format`: `3mf` (default), `3mftex`, `glb`, `glbtex`, `obj`, `objtex`, `stl`.
- `--corners-json`: a file like `{"a": [[x,y],[x,y],[x,y],[x,y]], "b": …}`, keyed by photo name without `.jpg`.
- `--set`: any setting from [Default settings](#default-settings-150-mm-tile), with the names listed under [API](#api).
- `--server`: send the photo to an engine instead of using this computer (your own Cloud Run address, or a local one like `http://localhost:8088`).

**Without `mixo`**, any tool that can send a form works, e.g. `curl`:
```bash
curl -F image=@my-tile.jpg -F 'corners=[[510,564],[2616,534],[2514,2508],[594,2478]]' \
     -F output_format=3mftex -o my-tile.textured.3mf https://YOUR-ENGINE/process-tile
```
(An engine only answers browsers from the websites in its `ALLOWED_ORIGINS`; command-line tools like these aren't affected.)

## API

- `GET /health` returns `{"status":"ok"}`.
- `POST /process-tile` takes `multipart/form-data`:
  - **Required:** `image`.
  - **Optional:** `corners` (JSON `[[x,y]×4]`), `swatches` (JSON hex list), plus any setting above, using the names in `TileConfig`: `tile_size_mm`, `pad_thickness_mm`, `relief_height_mm`, `fillet_radius_mm`, `dome_height_mm`, `groove_floor_mm`, `clearance_mm`, `outline_height_mm`, `outline_width_mm`, `num_colors`, `mesh_resolution_mm`, `symmetry`, `output_format` (`3mf` | `3mftex` = 3MF with the photo as a texture, still prints in glaze colours | `glb` | `glbtex` | `stl` = zip, one STL per colour | `obj` = zip, OBJ+MTL colours | `objtex` = zip, OBJ+MTL+texture.jpg).
- `stream=false` (default) returns the model bytes, plus stats in the `X-MixoTile-Stats` header.
- `stream=true` returns a single streamed response, used by the app:
  - JSON lines: `{"type":"progress","p":0.42,"msg":"Carving colour 3 of 8"}`.
  - Then `{"type":"preview","layout":[…],"bytes":N}` followed by N bytes of preview mesh (float32 positions and uint32 indices per part).
  - Then `{"type":"texture","bytes":T}` followed by T bytes of JPEG: the top-down photo for the preview's Photo view (u = x/size, v = y/size).
  - Then `{"type":"done","bytes":M}` followed by M bytes of model, or `{"type":"error",…}`.

## Tests and verification

Tests use **only the owner's hand-picked photos**: 19 shots in `backend/tests/fixtures/real_tiles/originals/`, with their tile corners in `real_tiles/corners.json` (see the README there). Every pipeline change must pass on all of them:

```bash
cd backend
python tests/run_real.py                       # every photo: each colour body watertight, time per tile
python tests/check_formats.py IMG_9255         # STL closed per colour, OBJ materials, photo texture lined up
python tests/check_borders.py IMG_9255 0       # puzzle-fit between colours (gap / overlap)
python tests/lines_sheet.py                    # visual sheet: photo | outlines | colours | height map
```

`HANDOFF.md` has the full engineering log, the design decisions and the next steps, for whoever picks this up (human, Claude, or Codex). `AGENTS.md` has the rules for coding agents.

## Known limits

- **Auto-outline:** the AI only suggests the corners. On framed tiles it sometimes grabs a sliver of the wooden frame (seen on IMG_9255 and IMG_9343 in the tests). Always check the four corners and drag any that are off.
- **Low-contrast tiles:** a white motif on a pale background (the heron, IMG_9391) can merge into one colour. Picking the colours yourself with the eyedropper (heron white and the pale-blue water) may keep them apart.
- **Glossy, painterly glazes** can still split into small patches. Examples: the shiny rose leaves and the lion's mane.
- **Stickers** on the glaze (e.g. "61", "75") become relief. The glare/sticker inpaint is implemented but off by default, because it also erased real white glaze.

## Credits

- **Tile photos** (tests, results table and the in-app sample): taken and hand-picked by the owner.
- **Built with:** FastAPI, OpenCV, scikit-image, scikit-learn, SciPy, fast-simplification, trimesh; Three.js, MediaPipe Tasks Vision, Cropper.js and Tailwind (via CDN).
