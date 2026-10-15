# Test fixtures: the owner's photos (the only test images)

**Use only these photos for testing.** The owner picked them by hand (2026-10-15) and removed everything else (the earlier 16-tile set and the Wikimedia museum crops). Don't add other images, and don't delete, move or edit these.

## `real_tiles/originals/`: 18 photos, `IMG_9245.jpg` … `IMG_9393.jpg` (3024 × 3024)

| Kind | Photos |
|---|---|
| Framed museum tiles | 9245, 9250, 9251, 9255, 9336, 9343, 9348, 9350, 9351, 9354, 9356, 9381 |
| Framed with a white mat | 9279 |
| Tiles on a wall (one tile is used) | 9287 (large flower), 9384 (centre medallion) |
| Coasters standing on a shelf | 9390, 9392, 9393 |

## `real_tiles/corners.json`

`{"IMG_9245": [[x, y] TL, TR, BR, BL], ...}`, the glaze corners **in the photo's own pixels**. `process_tile` takes them as they are.

- The rest were proposed automatically (the opening inside the wooden frame).
- 9 were read off gridded views by eye: 9251, 9279, 9287, 9343, 9351, 9381, 9384, 9390, 9392. (IMG_9391, the heron, was removed by the owner.)
- All were checked by flattening each photo with its corners and looking for wood or a neighbouring tile at the edges.

## Scripts that use them

| Script | What it checks |
|---|---|
| `tests/run_real.py [IMG_…]` | Every body watertight; time per tile (no args = all photos) |
| `tests/check_formats.py IMG_9255` | STL closed per colour; OBJ materials; photo texture lined up |
| `tests/check_borders.py IMG_9255 [clearance]` | Watertight; puzzle-fit gap/overlap between colours |
| `tests/make_table.py <renders_dir> <out.jpg>` | Photo-vs-render table from app screenshots `user_<name>.png` |
| `tests/lines_sheet.py`, `tests/check_labels.py` | Outline / colour-label visual sheets |
