# Test fixtures: permanent regression set

**Don't delete, move or replace these files.** The owner wants these tiles used as test subjects for every change to the colour or geometry pipeline.

## `real_tiles/`: the owner's photos (Museum of Old Taiwan Tiles)
- `NN_name.jpg`: 16 test tiles, numbered 01–16. Tile 13 (bear) and tile 14 (leopard cat) come from the same four-coaster photo.
- `corners.json` maps each tile to `[upload_id, [[x,y]×4]]`, giving the glaze corners TL, TR, BR, BL **in 2048-px coordinates**, so scale by `image_width / 2048`. The corners were set by hand and checked on a contact sheet. Tiles 07, 10, 13 and 16 still include a thin strip of frame or the neighbouring tile along one edge.
- `originals/`: the owner's unmodified uploads (2576×2576), named by upload id. Includes two duplicates the owner sent twice (the pink star and the blue knot) and the four-coaster photo.

What each tile stresses:

| Tile | Stresses |
|---|---|
| 01 teal octagon, 03 green star, 11 blue knot, 12 pink star | geometric, symmetric, crisp tube-lines |
| 02 sunflower, 16 purple sunflower | thin white outlines, glaze crazing, low-contrast petal lines |
| 04 star 75, 10 star 61 | sticker labels on the glaze |
| 05 no smoking | Chinese characters; a product label covers the right edge |
| 06 lion peony, 07 chrysanthemum, 15 green lattice | painterly/shaded, glossy relief, texture (false-line risk) |
| 08 rose octagon, 09 single rose | small central detail, thin dark stem and veins |
| 13 bear, 14 leopard cat | modern coasters, faces, spots, white on black |

## `museum_wikimedia/`: 4 crops from Wikimedia Commons
"Interior of the Museum of Old Taiwan Tiles-03", CC-licensed. These are low-resolution, blurry framed tiles. Use them to test the auto-outline (MediaPipe locks onto the frame or the motif on B and C).

## How to use
- `../check_labels.py`, `../run_real.py` and `../out/user/compare.py` read `tests/out/user/`. Point them at `fixtures/real_tiles/`, or copy the files there.
- Every change: run all 16 tiles, look at a photo-vs-result sheet, and check that every body is watertight.
