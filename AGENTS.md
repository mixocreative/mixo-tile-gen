# Agent instructions (Codex / Claude / others)

Read `HANDOFF.md` first. It has the current state, how to run and verify, the owner's design decisions, and the next steps.
Keep `HANDOFF.md` up to date at every key step: add to the Status log and refresh Next steps.

Rules:
- Don't regress the design decisions in HANDOFF section 3. The owner arrived at them over many iterations.
- After any geometry change, run `backend/tests/run_local.py` in Docker. Every body must be watertight.
- Keep the defaults in `TileConfig`, the `main.py` Form defaults and the `frontend/index.html` inputs in sync.
- Don't deploy, commit, push or `git init` unless the owner asks.

- Every pipeline change must be verified on all 16 fixture tiles in `backend/tests/fixtures/real_tiles/` (`python tests/run_real.py` for watertightness, `python tests/lines_sheet.py` for the visual sheet) before reporting. Never delete or replace fixture files.
