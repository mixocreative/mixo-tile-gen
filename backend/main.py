"""MixoTile API — FastAPI wrapper around tile_processor (deploy target: Google Cloud Run)."""

from __future__ import annotations

import asyncio
import ctypes
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

import cv2

import tile_processor as tp

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("mixotile.api")

# One tile at a time per engine (memory: a tile peaks ~1.5–2 GB). Cloud Run is deployed with
# --concurrency > 1 so /health and queued requests are still answered (with CORS headers) while a
# tile is being made; extra tiles wait here instead of being refused by the platform.
_tile_lock: asyncio.Lock | None = None
_waiting = 0


def _lock() -> asyncio.Lock:
    global _tile_lock
    if _tile_lock is None:
        _tile_lock = asyncio.Lock()
    return _tile_lock

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "15")) * 1024 * 1024
MEDIA_TYPES = {fmt: media for fmt, (_ext, media) in tp.EXPORT_FORMATS.items()}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        await run_in_threadpool(tp.warm_up)
        log.info("CAD / meshing modules warmed up")
    except Exception:  # never block startup — /process-tile will report the real error
        log.exception("CAD warm-up failed")
    yield


app = FastAPI(title="MixoTile API", version="1.0.0", lifespan=lifespan)

# Comma-separated list, e.g. "https://yourname.github.io,http://localhost:8000". Default "*".
_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-MixoTile-Stats"],
    max_age=3600,
)


def _parse_json(name: str, raw: str | None):
    if raw is None or raw.strip() in ("", "null"):
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, f"'{name}' must be valid JSON: {exc.msg}") from exc


def _parse_swatches(raw):
    """Accept [[r,g,b], ...] or ["#rrggbb", ...]."""
    if not raw:
        return None
    if not isinstance(raw, list):
        raise HTTPException(422, "'swatches' must be a JSON list")
    out = []
    for s in raw:
        if isinstance(s, str):
            h = s.lstrip("#")
            if len(h) != 6:
                raise HTTPException(422, f"bad hex swatch {s!r}")
            try:
                out.append([int(h[i:i + 2], 16) for i in (0, 2, 4)])
            except ValueError as exc:
                raise HTTPException(422, f"bad hex swatch {s!r}") from exc
        elif isinstance(s, (list, tuple)) and len(s) == 3:
            out.append([float(v) for v in s])
        else:
            raise HTTPException(422, f"bad swatch {s!r}")
    return out


@app.get("/health")
def health():
    return {"status": "ok", "service": "mixotile", "version": app.version}


@app.get("/local-info")
def local_info():
    """Phone links for the home page's QR panel. Only the local PC launcher (scripts/run_local.py)
    sets MIXO_PHONE_FILE, so on Cloud Run / Docker / any other host this is always 404."""
    path = os.getenv("MIXO_PHONE_FILE")
    if not path or not os.path.exists(path):
        raise HTTPException(404, "not running from the local launcher")
    with open(path, encoding="utf-8") as fh:
        return Response(fh.read(), media_type="application/json", headers={"Cache-Control": "no-store"})


@app.post("/process-tile")
async def process_tile(
    image: UploadFile = File(..., description="Tile photo (JPEG/PNG/WebP)"),
    corners: str | None = Form(None, description="JSON [[x,y]x4] in image pixels (TL,TR,BR,BL; any order accepted)"),
    swatches: str | None = Form(None, description='JSON [[r,g,b],...] or ["#rrggbb",...]; empty → k-means'),
    paint: str | None = Form(None, description='JSON, one entry per swatch: replacement colour "#rrggbb" or null (= keep). '
                                               'The area still comes from the swatch; only its colour changes'),
    tile_shape: str = Form("square", description="square | circle (a circular tile inscribed after rectification)"),
    tile_size_mm: float = Form(150.0),
    pad_thickness_mm: float = Form(15.0),
    relief_height_mm: float = Form(3.0, description="edge depth: top of each colour down to its seams"),
    fillet_radius_mm: float = Form(6.0, description="edge-roll width (wider = softer valley)"),
    dome_height_mm: float = Form(1.0, description="gentle crown on top (leveler on bigger patches)"),
    dome_reach_mm: float = Form(12.0, description="crown length scale (bigger = more level tops)"),
    groove_floor_mm: float = Form(0.4, description="material under the seams between colours"),
    corner_radius_mm: float = Form(2.0),
    mesh_resolution_mm: float = Form(0.16),
    num_colors: int = Form(8, description="max colours; auto-k picks 3..this"),
    px_per_mm: float = Form(4.0),
    smoothing_mm: float = Form(1.2),
    min_feature_mm2: float = Form(2.0),
    merge_delta_e: float = Form(12.0, description="merge shading bands of one glaze (0 = off)"),
    bead_height_mm: float = Form(1.2, description="printable minimum height for thin strokes"),
    clearance_mm: float = Form(0.0, description="gap between neighbouring colour pieces (0 = flush puzzle fit)"),
    outline_height_mm: float = Form(0.8, description="raised tube-lining ridge along detected outlines (0 = off)"),
    outline_width_mm: float = Form(1.2, description="width of that ridge"),
    edge_is_seam: bool = Form(False, description="true = groove along the tile edge too"),
    symmetry: str = Form("off", description="off | auto | c4 | d4 (opt-in)"),
    formats: str = Form(",".join(tp.BUNDLE_DEFAULT_NAMES), description="output_format=bundle: comma list of formats to put in the zip"),
    output_format: str = Form("3mf", description="3mf | 3mftex | glb | glbtex | stl (one complete model, no colours) | obj (zip, material groups) | objtex (zip, photo texture). *tex = the photo as a texture; 3mftex still prints in glaze colours | bundle = zip of the `formats` list from one run"),
    stream: bool = Form(False, description="true = progress lines + binary payloads (see _stream)"),
    preview: bool = Form(True, description="stream: also send a light preview mesh before the file"),
):
    data = await image.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"image larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")

    fmt = output_format.lower().lstrip(".")
    cfg = tp.TileConfig(
        tile_shape=tile_shape.lower(), tile_size_mm=tile_size_mm, pad_thickness_mm=pad_thickness_mm, relief_height_mm=relief_height_mm,
        fillet_radius_mm=fillet_radius_mm, groove_floor_mm=groove_floor_mm, corner_radius_mm=corner_radius_mm,
        dome_height_mm=dome_height_mm, dome_reach_mm=dome_reach_mm,
        mesh_resolution_mm=mesh_resolution_mm, num_colors=num_colors, px_per_mm=px_per_mm,
        smoothing_mm=smoothing_mm, min_feature_mm2=min_feature_mm2, merge_delta_e=merge_delta_e,
        bead_height_mm=bead_height_mm, clearance_mm=clearance_mm, outline_height_mm=outline_height_mm, outline_width_mm=outline_width_mm,
        edge_is_seam=edge_is_seam, symmetry=symmetry.lower(),
        output_format=fmt, formats=formats,
    )
    corner_pts = _parse_json("corners", corners)
    swatch_list = _parse_swatches(_parse_json("swatches", swatches))
    paint_raw = _parse_json("paint", paint)
    paint_list = None
    if paint_raw:
        if not isinstance(paint_raw, list):
            raise HTTPException(422, "'paint' must be a JSON list")
        paint_list = [None if c is None else _parse_swatches([c])[0] for c in paint_raw]

    if fmt not in tp.EXPORT_FORMATS:
        raise HTTPException(422, "output_format must be one of " + ", ".join(tp.EXPORT_FORMATS))
    fname = f"mixotile_{int(round(tile_size_mm))}mm.{tp.EXPORT_FORMATS[fmt][0]}"
    if stream:
        return StreamingResponse(_stream(data, corner_pts, swatch_list, cfg, fmt, fname, preview, paint_list),
                                 media_type="application/x-ndjson",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    try:
        async with _lock():
            model, stats = await run_in_threadpool(tp.process_tile, data, corner_pts, swatch_list, cfg, None, None, paint_list)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        log.exception("process-tile failed")
        raise HTTPException(500, f"model generation failed: {type(exc).__name__}") from exc

    log.info("generated %s: %d bytes, bodies=%d, timing=%s", fmt, len(model), stats["bodies"], stats["timing_s"])
    _trim_memory()
    # sent chunked: Cloud Run rejects a plain (Content-Length) response over 32 MiB, and a
    # textured .glb is ~40 MB; chunked transfer has no such limit
    return StreamingResponse(
        (model[i:i + (1 << 20)] for i in range(0, len(model), 1 << 20)),
        media_type=MEDIA_TYPES[fmt],
        headers={
            "Content-Disposition": f'attachment; filename="{fname}"',
            "X-MixoTile-Stats": json.dumps(_summary(stats), separators=(",", ":")),
            "Cache-Control": "no-store",
        },
    )


def _trim_memory() -> None:
    """glibc keeps freed heap pages; after a tile that's ~1 GB the next tile can hit the memory limit."""
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError):    # not glibc (Windows / macOS dev machines)
        pass


def _summary(stats):
    # .get: the preview event is sent before timing/raster stats exist
    return {k: stats.get(k) for k in ("bodies", "triangles", "relief_height_mm", "dome_height_mm", "total_height_mm",
                                      "colours", "timing_s", "raster_px", "symmetry", "merged_shading_bands")}


async def _stream(data, corner_pts, swatch_list, cfg, fmt, fname, want_preview=True, paint_list=None):
    """Progress over the SAME request (Cloud Run only gives CPU while a request is open, and a
    follow-up poll could land on another instance). Wire format (bytes):
      one JSON object per line:  {"type":"progress","p":0.42,"msg":"Carving colour 3 of 8"}  ...
      optional     {"type":"preview","layout":[{name,hex,nv,nt}..],"stats":{..},"bytes":N}\n + N bytes
                   (per part: nv*3 float32 xyz mm, then nt*3 uint32 indices; little-endian)
      optional     {"type":"texture","bytes":N}\n + N bytes of JPEG: the top-down photo (u = x/size, v = y/size)
      optional     {"type":"heights","params":{pad,floor,relief,crown,outline,size},"bytes":N}\n + N bytes:
                   per preview vertex (same parts/order) 5 float32 t, A, B, R, resid. Body vertex height
                   = pad + t*(floor + relief*A + crown*B + outline*R + resid); pad vertex = t*pad
      then either  {"type":"error","status":..,"detail":..}\n
      or           {"type":"done","filename":..,"stats":{..},"bytes":N}\n  followed by N raw model bytes
    (raw bytes, not base64: 25 % smaller, and the browser never has to parse a 20 MB JSON line)."""
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    def progress(p, msg):
        loop.call_soon_threadsafe(q.put_nowait, ("progress", {"type": "progress", "p": p, "msg": msg}))

    def on_parts(parts, stats, texture=None):
        if want_preview:
            H = stats.get("_heights")
            res = tp.preview_mesh(parts, heights=H)
            layout, blob = res[0], res[1]
            loop.call_soon_threadsafe(q.put_nowait, ("preview", ({"type": "preview", "layout": layout,
                                                                  "stats": _summary(stats), "bytes": len(blob)}, blob)))
            if H is not None:            # live sliders: per vertex t, A, B, R, resid (float32 x5), same part order
                hb = res[2]
                params = {"pad": cfg.pad_thickness_mm, "floor": cfg.groove_floor_mm, "relief": cfg.relief_height_mm,
                          "crown": min(cfg.dome_height_mm, cfg.relief_height_mm + cfg.dome_height_mm),
                          "outline": cfg.outline_height_mm, "size": cfg.tile_size_mm}
                loop.call_soon_threadsafe(q.put_nowait, ("preview", ({"type": "heights", "params": params,
                                                                      "bytes": len(hb)}, hb)))
            if texture is not None:      # top-down photo for the preview's "Photo" view (u = x/size, v = y/size)
                ok, jpg = cv2.imencode(".jpg", cv2.cvtColor(texture, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ok:
                    jb = jpg.tobytes()
                    loop.call_soon_threadsafe(q.put_nowait, ("preview", ({"type": "texture", "bytes": len(jb)}, jb)))

    def work():
        try:
            model, stats = tp.process_tile(data, corner_pts, swatch_list, cfg, progress=progress, on_parts=on_parts, paint=paint_list)
            log.info("generated %s: %d bytes, bodies=%d, timing=%s", fmt, len(model), stats["bodies"], stats["timing_s"])
            loop.call_soon_threadsafe(q.put_nowait, ("done", (stats, model)))
        except ValueError as exc:
            loop.call_soon_threadsafe(q.put_nowait, ("error", {"type": "error", "status": 422, "detail": str(exc)}))
        except Exception as exc:  # noqa: BLE001
            log.exception("process-tile (stream) failed")
            loop.call_soon_threadsafe(q.put_nowait, ("error", {"type": "error", "status": 500,
                                                               "detail": f"model generation failed: {type(exc).__name__}"}))

    def line(obj):
        return (json.dumps(obj, separators=(",", ":")) + "\n").encode()

    global _waiting
    lock = _lock()
    if lock.locked():                            # someone else's tile is being made: wait in line
        _waiting += 1
        try:
            acq = asyncio.ensure_future(lock.acquire())
            while not acq.done():
                yield line({"type": "progress", "p": 0.0,
                            "msg": f"Waiting for the engine: another tile is being made ({_waiting} waiting)"})
                await asyncio.wait([acq], timeout=5)
        finally:
            _waiting -= 1
    else:
        await lock.acquire()
    try:
        async for chunk in _run_stream(loop, q, work, line, fname):
            yield chunk
    finally:
        lock.release()


async def _run_stream(loop, q, work, line, fname):
    task = loop.run_in_executor(None, work)
    yield line({"type": "progress", "p": 0.0, "msg": "Starting"})
    while True:
        try:
            kind, payload = await asyncio.wait_for(q.get(), timeout=10)
        except asyncio.TimeoutError:               # keep proxies from closing an idle stream
            yield line({"type": "ping"})
            continue
        if kind == "progress":
            yield line(payload)
        elif kind == "preview":
            head, blob = payload
            yield line(head)
            for i in range(0, len(blob), 1 << 20):
                yield blob[i:i + (1 << 20)]
        elif kind == "error":
            yield line(payload)
            break
        else:
            stats, model = payload
            yield line({"type": "done", "filename": fname, "stats": _summary(stats), "bytes": len(model)})
            for i in range(0, len(model), 1 << 20):
                yield model[i:i + (1 << 20)]
            break
    await task
    _trim_memory()


# Self-hosting: serve the website from the engine too (one address for the PC, phone and tunnel).
# Mounted last so the API routes above take precedence.
_frontend = os.getenv("FRONTEND_DIR")
if _frontend and os.path.isdir(_frontend):
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")
