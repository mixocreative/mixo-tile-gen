# Agent instructions (Codex / Claude / others)

Read `HANDOFF.md` first. It has the current state, how to run and verify, the owner's design decisions, and the next steps.
Keep `HANDOFF.md` up to date at every key step: add to the Status log and refresh Next steps.

Rules:
- Don't regress the design decisions in HANDOFF section 3. The owner arrived at them over many iterations.
- **Test images: only the owner's hand-picked photos** in `backend/tests/fixtures/real_tiles/originals/` (19 `IMG_*.jpg`, corners in `real_tiles/corners.json`, photo pixels). Never use or add other images (no synthetic samples, no museum crops). Never delete, move or edit those files; if they change, the owner is curating them, so ask before restoring anything.
- Every pipeline change must pass on all of those photos before reporting: `python tests/run_real.py` (every body watertight) and `python tests/check_formats.py IMG_9255` (all download formats). Look at a photo-vs-result sheet too (`tests/lines_sheet.py`, or `tests/make_table.py` from app screenshots).
- The AI (MediaPipe auto-outline) only **suggests** corners: the person always confirms or adjusts them, and the app must keep working without the AI.
- Keep the defaults in `TileConfig`, the `main.py` Form defaults and the `frontend/index.html` inputs in sync.
- Don't deploy, commit, push or `git init` unless the owner asks.
