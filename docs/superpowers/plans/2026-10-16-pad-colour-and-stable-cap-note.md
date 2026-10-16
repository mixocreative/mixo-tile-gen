# Pad Colour and Stable Cap Note Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a person choose the backing-pad colour before or after generation, preserving that colour in every browser export, and prevent the fine-tune cap message from moving controls.

**Architecture:** Keep `S.padColour` as browser-owned presentation/export state. The mesh remains one model: the backing-pad part is recoloured locally for Colour view and non-textured exports; photo-textured exports retain the photo on visible faces but use this colour for the downward pad faces. Keep the cap note in the DOM with reserved space and toggle its visibility rather than display.

**Tech Stack:** Single-file browser application (`frontend/index.html`), native colour input, Three.js, browser 3MF/GLB/OBJ writers, Playwright smoke test.

---

### Task 1: Add a failing browser regression test

**Files:**
- Create: `backend/tests/check_frontend_pad_ui.py`

- [x] **Step 1: Assert the requested controls and layout contract**

```python
assert page.locator('#padColour').count() == 1
assert page.locator('#padColour').input_value() == '#ffffff'
assert page.locator('.ft-note').evaluate_all("nodes => nodes.every(n => n.classList.contains('invisible'))")
```

- [x] **Step 2: Run the test against a local static frontend and confirm it fails before the controls exist**

```powershell
python C:\Users\DCT\.codex\skills\webapp-testing\scripts\with_server.py --server "python -m http.server 8790 --bind 127.0.0.1" --port 8790 -- python backend/tests/check_frontend_pad_ui.py http://127.0.0.1:8790/frontend/
```

Expected: failure because `#padColour` does not exist.

### Task 2: Carry pad colour through preview and every client export

**Files:**
- Modify: `frontend/index.html:350-440, 730-770, 1900-2229, 2540-2640`

- [x] **Step 1: Add a Pad colour native input and local persistence**

Store a `#rrggbb` colour in `S.padColour`, render it in Step 03 in both look modes, and update immediately on input.

- [x] **Step 2: Override only the backing-pad material locally**

Apply the selected RGB to the pad material in Colour view. In Photo view, keep the top-down texture on non-downward faces and create its underside material from the selected RGB.

- [x] **Step 3: Pass the selected RGB into 3MF, GLB, and OBJ**

Use it for the backing-pad base material in non-textured files and textured-file `underside` material. Keep the existing single root/object and triangle ranges.

- [x] **Step 4: Run the browser regression test and confirm it passes**

Run the Task 1 command. Expected: `frontend pad UI checks passed`.

### Task 3: Stabilise the cap warning and verify exports

**Files:**
- Modify: `frontend/index.html:2690-2760`
- Modify: `HANDOFF.md:Status log, Next steps`

- [x] **Step 1: Reserve a fixed status area for every cap note**

Create each fine-tune note with `invisible` rather than `hidden`, and toggle `invisible` when the cap is reached so its row height never changes.

- [x] **Step 2: Verify browser/export and pipeline contracts**

Run the browser check, `python backend/tests/check_formats.py IMG_9255`, `python backend/tests/run_real.py`, and `python backend/tests/lines_sheet.py`; inspect the rendered sheet.

- [x] **Step 3: Record the result and ship only after all checks pass**

Update `HANDOFF.md`, commit the feature and test, push `origin/main`, and let the existing GitHub Pages workflow publish the static frontend. Do not deploy Cloud Run because this change is browser-only.
