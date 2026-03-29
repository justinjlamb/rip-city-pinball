---
title: "fix: Match flipper visual aesthetic to table hardware"
type: fix
status: active
date: 2026-03-28
---

# fix: Match flipper visual aesthetic to table hardware

## Overview

The code-rendered flippers use a chrome/silver gradient that clashes with the table image's hardware aesthetic. The slingshot guards, outlane rails, and other table hardware all share a consistent design language: black body, red edge trim, silver screw/bolt details. The flippers need to speak the same visual language.

## Problem Frame

The table image (`table.png`) establishes a clear hardware aesthetic for all mounted components: solid black bodies with red edge highlights and visible silver screw heads. The flippers are the only dynamic elements rendered by code, and they currently use a chrome gradient (`#d0d0d0` to `#999`) with a gray border — a completely different design vocabulary. They look bolted on from a different game.

## Requirements Trace

- R1. Flipper body matches the black fill of the table's slingshot guards
- R2. Flipper edge has the same red trim treatment as the guards (`#C8102E` or similar)
- R3. Flipper has screw/bolt details consistent with the guard hardware
- R4. Pivot cap integrates visually (currently dark circle — keep but may need color adjustment)
- R5. Shadow and depth cues maintained for readability against wood floor texture
- R6. No physics or gameplay changes — visual only

## Scope Boundaries

- Only `renderFlippers()` function in `index.html` is modified
- No changes to flipper physics, dimensions, or hit detection
- No changes to the table image
- No changes to v2.html (separate experimental version)

## Context & Research

### Relevant Code and Patterns

- `index.html:1257-1311` — `renderFlippers()`: current chrome gradient implementation
- Table hardware aesthetic (from `table.png`): black body (`#1a1a1a`-`#222`), red edge (`#C8102E`), silver screws (`#999`-`#bbb`)
- `v2.html:924-984` — `drawFlipper()`: already uses red-edge + black-body approach (stadium shape, 3px inset), good color reference but different shape
- Canvas helper functions: `px()`, `py()`, `ps()` for coordinate/size transforms

### Design Reference (from screenshot)

The slingshot guards show:
1. **Solid black body** — not gradient, flat black fill
2. **Red edge trim** — narrow red border running along outer edge
3. **Silver screw heads** — small circles with highlight, 2-3 per guard face
4. **Drop shadow** — subtle offset shadow for mounted/raised appearance
5. **Angular shape** — hard edges, no soft rounding

## Key Technical Decisions

- **Flat black fill, not gradient**: The table hardware uses solid fills. The chrome gradient reads as "different material." Switch to flat `#1a1a1a` or similar dark fill to match.
- **Red edge via two-pass drawing**: Draw the full flipper shape in red first, then draw a slightly inset shape in black on top — same technique as v2.html's `drawFlipper()`. The inset creates the red border effect without stroke alignment issues.
- **Screw positions along flipper body**: Place 2-3 screw details along the centerline of the flipper. Each screw is a small circle with a slight highlight — matches the guard screws visible in the table art.
- **Keep existing tapered shape**: The flippers already have a good tapered paddle shape (wider at hinge, narrower at tip). Keep this — just change the material rendering.
- **Subtle highlight line**: A very faint white line along one edge (like v2.html's `rgba(255,255,255,0.15)`) adds dimensionality without breaking the flat aesthetic.

## Implementation Units

- [ ] **Unit 1: Redesign flipper rendering to match table hardware aesthetic**

**Goal:** Replace chrome gradient flipper rendering with black-body/red-edge/screw-detail rendering that matches the table image's slingshot guard aesthetic.

**Requirements:** R1, R2, R3, R4, R5, R6

**Dependencies:** None

**Files:**
- Modify: `/Users/justin/Developer/rip-city-pinball/index.html` (function `renderFlippers()` at line 1257)

**Approach:**

The rendering sequence for each flipper becomes:

1. **Shadow** (keep existing, maybe darken slightly)
2. **Red edge shape** — draw full tapered paddle in `#C8102E`
3. **Black body** — draw same shape inset ~3px in `#1a1a1a`
4. **Subtle highlight** — faint white line along top edge
5. **Screw details** — 2-3 small circles along flipper centerline:
   - Outer ring: `#999` or `#aaa` fill
   - Inner dot or cross: `#666`
   - Positioned at ~30%, ~60%, and optionally ~85% along flipper length
6. **Pivot cap** — keep dark circle, adjust colors to match (black fill + red ring could tie it in)

Screw positions calculated by interpolating along the hinge-to-tip vector. Each screw is a small `arc()` call with radius ~ps(4-5).

**Patterns to follow:**
- v2.html `drawFlipper()` for the two-pass red-edge/black-body technique
- Existing `renderFlippers()` for coordinate math, tapered shape, shadow offset
- Table image's guard hardware for visual target

**Test scenarios:**
- Happy path: Flippers render with black body, red edge, and screw details at rest angle
- Happy path: Flippers maintain visual coherence during flip animation (screws rotate with body)
- Edge case: Both flippers are mirror images (left/right symmetry preserved)
- Integration: Flipper visuals read clearly against the wood texture table background at all canvas sizes

**Verification:**
- Screenshot comparison: flippers visually match the slingshot guard aesthetic (black body, red trim, silver screws)
- Flipper animation still smooth — no rendering artifacts during rapid flipping
- No physics changes — ball interaction unchanged

## System-Wide Impact

- **Interaction graph:** Only `renderFlippers()` changes. Called from `renderFrame()` during play states. No callbacks or middleware affected.
- **State lifecycle risks:** None — purely visual, no state changes.
- **Unchanged invariants:** Flipper physics bodies, collision detection, and animation timing are untouched.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Screw details too small to see at lower resolutions | Use `ps()` scaling consistently; verify at smallest supported canvas size |
| Red edge too thick or thin relative to guards | Tune inset value (start with 3px like v2.html, adjust visually) |
