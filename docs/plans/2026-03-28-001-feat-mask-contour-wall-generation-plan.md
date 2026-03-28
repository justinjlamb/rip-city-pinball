---
title: "feat: Generate physics walls from mask contour tracing"
type: feat
status: active
date: 2026-03-28
---

# Generate Physics Walls from Mask Contour Tracing

## Overview

Replace hand-placed wall coordinates with walls auto-generated from `table-mask.png` — a black/white mask where white = playable surface, black = walls/boundaries. A Python script traces the mask contour, simplifies it, and outputs wall data that v2.html consumes.

## Problem Frame

Wall placement has failed repeatedly because coordinates were guessed or extracted from faulty pixel analysis. The mask image (created by Justin in Photoshop) is the authoritative source of truth for the playfield boundary. The mask has one connected white region (13,875 boundary pixels) containing the main playfield, launcher channel, slingshot indentations, and outlane gaps as one continuous contour.

## Requirements Trace

- R1. Every black/white boundary in the mask becomes a physics wall
- R2. Curves must be smooth — no harsh corners where the ball gets stuck
- R3. Complete coverage: top boundary, left/right walls, launcher channel, slingshot indentations, outlane dividers, drain funnel — everything in the mask
- R4. Flipper positions connect to the surrounding wall geometry (no floating flippers)
- R5. Ball spawns inside the launcher channel on the wood surface
- R6. Output integrates into v2.html with minimal manual editing

## Scope Boundaries

- This plan covers wall generation ONLY — not flipper physics, scoring, sound, or visual polish
- The mask is treated as final — no modifications to the mask itself
- Flipper hinge positions will be derived from the drain gap in the contour

## Key Technical Decisions

- **Contour method: Moore neighborhood boundary tracing** — Standard algorithm for extracting ordered boundary pixels from a binary image. Gives a single closed contour path with proper pixel ordering. Scipy doesn't have findContours, but Moore tracing is ~30 lines of Python. Rationale: ordered points are essential for Douglas-Peucker simplification.

- **Simplification: Douglas-Peucker algorithm** — Reduces 13,875 boundary pixels to ~60-120 key points while preserving shape. Epsilon parameter controls the tradeoff between accuracy and segment count. Rationale: standard polyline simplification, well-understood, deterministic.

- **Smoothing: Chaikin's corner-cutting (1 pass)** — After DP simplification, one pass of Chaikin's algorithm rounds sharp corners by cutting 25% off each corner. This prevents balls from catching on acute angle transitions between wall segments. Rationale: simple, predictable, doesn't add many extra points.

- **Output format: JSON data file** — The script outputs a JSON array of wall segments. v2.html loads this file and creates wall() calls from it. Rationale: separates data generation from game code, easy to regenerate when the mask changes.

- **Corner gap prevention: small circle bodies at each vertex** — Matter.js wall segments are rectangles. At corners, there can be tiny gaps between adjacent rectangles. Placing a small static circle (radius = WALL_T/2) at each vertex point fills these gaps. Rationale: standard technique in Matter.js, prevents ball from tunneling through corners.

## Open Questions

### Resolved During Planning

- **One region or multiple?** — The mask has exactly 1 connected white region. Playfield and launcher merge at the top. Slingshots and outlanes are indentations in the boundary, not separate holes. This means one contour trace covers everything.

- **Where do flippers go?** — The drain gap is the narrowest point at the bottom of the contour. Flipper hinges position at the edges of this gap, derived directly from the contour data.

### Deferred to Implementation

- **Optimal DP epsilon value** — Needs visual testing. Start at 6-8px, adjust based on debug overlay alignment with the mask. Too low = too many segments (performance). Too high = loses detail on curves and slingshot indentations.

- **Whether Chaikin smoothing is sufficient or needs 2 passes** — Test with 1 pass first. If corners still catch the ball, apply 2.

## Implementation Units

- [ ] **Unit 1: Contour tracing script**

**Goal:** Python script that reads `table-mask.png`, traces the boundary contour, simplifies it, smooths it, and outputs `wall-data.json`.

**Dependencies:** None

**Files:**
- Create: `scripts/trace-mask.py`
- Create: `wall-data.json` (output)
- Read: `table-mask.png` (input)

**Approach:**
- Load mask as numpy array, threshold at 128
- Implement Moore neighborhood boundary tracing to get ordered contour points (clockwise)
- Apply Douglas-Peucker simplification (epsilon=8 as starting point)
- Apply 1 pass of Chaikin's corner-cutting on the simplified points
- Identify the drain gap: find the two closest points at y > 2200 that are horizontally separated by > 150px — these are the flipper hinge positions
- Identify the launcher channel: find the segment where the contour passes through x > 1400 in the middle heights — the ball spawn position is the center of this passage
- Output JSON: `{ "walls": [[x1,y1,x2,y2], ...], "flipperLeft": {x,y}, "flipperRight": {x,y}, "ballStart": {x,y} }`

**Patterns to follow:**
- Existing `curveSegments()` function in v2.html shows the wall segment format expected
- The `wall()` function takes (x1, y1, x2, y2, label)

**Test scenarios:**
- Happy path: Script reads mask, outputs JSON with >40 wall segments covering the full boundary
- Happy path: Output JSON contains flipperLeft, flipperRight, and ballStart positions
- Edge case: DP epsilon=8 produces a contour that, when overlaid on the mask, has max deviation < 10px from the true boundary
- Edge case: Chaikin smoothing doesn't eliminate small features like outlane divider indentations (verify slingshot vertices survive)
- Edge case: The contour is closed (last segment connects back to first point)

**Verification:**
- Run the script, visually overlay the simplified contour on the mask image to confirm alignment
- Confirm wall count is in the 60-120 range (not 13,875 raw pixels, not 10 sparse guesses)
- Confirm flipper positions are at the drain gap edges
- Confirm ball start is inside the launcher channel

- [ ] **Unit 2: Visual verification tool**

**Goal:** Script that renders the generated wall segments overlaid on the mask and the table image, so we can visually confirm accuracy before putting them in the game.

**Dependencies:** Unit 1

**Files:**
- Create: `scripts/verify-walls.py`
- Output: `wall-overlay.png` (visual check)

**Approach:**
- Load `wall-data.json`
- Load both `table-mask.png` and `table-layer0.png`
- Draw the wall segments as colored lines on top of both images
- Draw circles at vertex points (corner gap bodies)
- Mark flipper positions and ball start
- Save as PNG for visual inspection

**Test scenarios:**
- Happy path: Output image shows colored wall lines tracing the mask boundary with no visible gaps
- Happy path: Flipper positions appear at the drain gap, ball start appears in the launcher channel
- Edge case: Zooming into corners shows no gap between adjacent wall segments

**Verification:**
- Open `wall-overlay.png` and confirm walls follow the mask boundary
- Justin reviews and approves before proceeding to Unit 3

- [ ] **Unit 3: Integrate wall data into v2.html**

**Goal:** v2.html loads `wall-data.json` and creates physics walls from it, replacing all hand-placed wall code.

**Dependencies:** Unit 2 (approved)

**Files:**
- Modify: `v2.html`

**Approach:**
- Remove all existing hand-placed wall() and curveWall() calls
- Add fetch of `wall-data.json` at startup
- Loop through wall array, create wall() for each segment
- Create small circle bodies at each vertex for corner gap prevention
- Set flipper hinge positions from JSON data
- Set ball start position from JSON data
- Flippers connect to the rail geometry naturally because their hinge positions come from the contour's drain gap edges

**Test scenarios:**
- Happy path: Game loads, ball appears in launcher channel on the wood surface
- Happy path: Ball launches, travels through the table, bounces off walls that align with the image
- Happy path: Flippers visually connect to the surrounding rail walls
- Happy path: Ball doesn't escape through any gap in the boundary
- Edge case: Ball rolls smoothly through curves without getting stuck
- Edge case: Ball drains through the gap between flippers (drain gap is the right size)
- Integration: Debug mode (Shift+D) shows wall overlay that matches the mask boundary

**Verification:**
- Open in Safari, Shift+D debug mode, visually confirm wall overlay matches table image
- Play test: launch ball, flip, let it drain, repeat — no stuck balls, no escapes, no floating flippers

## System-Wide Impact

- **Wall data is now external** — `wall-data.json` becomes the source of truth for table geometry. Any future table image change requires re-running `trace-mask.py` with a new mask.
- **Flipper positions are derived, not hardcoded** — If the drain gap changes in the mask, flippers automatically reposition.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| DP simplification loses slingshot detail | Verify with overlay tool (Unit 2) before integrating. Adjust epsilon if needed. |
| Moore tracing produces disordered points at narrow passages (launcher channel neck) | The mask has only 1 region with no sub-pixel-width passages. The launcher channel is ~78px wide — well above the threshold for clean tracing. |
| Corner gaps let ball tunnel through | Circle bodies at vertices fill gaps. Standard Matter.js technique. |
| Chaikin smoothing rounds off the drain gap | Exclude the drain gap vertices from smoothing — they need to stay sharp for flipper positioning. |

## Sources & References

- Mask image: `table-mask.png` (1694x2376, 1 white region, 13,875 boundary pixels)
- Table image: `table-layer0.png` (1694x2376)
- Game file: `v2.html` (Matter.js physics engine)
- Available Python: PIL, numpy, scipy.ndimage (no cv2, no skimage)
