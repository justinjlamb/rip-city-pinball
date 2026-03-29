---
title: "fix: Ramp ball escape — channel unsealed, exit sensor too small"
type: fix
status: active
date: 2026-03-28
---

# Fix: Ramp Ball Escape

## Problem Frame

When the ball enters the ramp, it rides up the guide walls but flies off the top of the channel and disappears. Root cause: the ramp channel is open at both ends — no cap wall connects the left rail to the right rail at the top. The exit sensor (radius 30) is too small to reliably catch a fast-moving ball.

## Requirements Trace

- R1. Ball must stay inside the ramp channel for the entire journey
- R2. Ball must reliably hit the exit sensor and transition back to playfield
- R3. No ball should ever leave the visible play area

## Scope Boundaries

- Fix the ramp channel sealing only — don't change the ramp path, entrance position, or scoring
- Don't change flipper physics in this fix

## Key Technical Decisions

- **Seal both ends of the ramp channel:** Add a wall connecting the last left rail point to the last right rail point (top cap), and the first left rail point to the first right rail point (bottom cap). These walls use RAMP collision category so they only affect balls in ramp mode.

- **Enlarge the exit sensor:** Increase radius from 30 to the full channel half-width. A ball anywhere across the channel width will hit it.

- **Add a failsafe:** If the ball is in ramp mode and goes off-screen (y < -100 or x > IMG_W + 100), immediately revert to playfield mode and reposition the ball at the ramp exit point. This prevents permanent ball loss.

## Implementation Units

- [ ] **Unit 1: Seal the channel and fix the exit**

**Goal:** Close the ramp channel at both ends, enlarge the exit sensor, add off-screen failsafe.

**Files:**
- Modify: `v2.html`

**Approach:**
- In `createRamp()`, after generating the rail walls, add two cap walls:
  - Bottom cap: `createWall(leftRail[0], rightRail[0], 'ramp-cap-bottom', COL.RAMP)`
  - Top cap: `createWall(leftRail[last], rightRail[last], 'ramp-cap-top', COL.RAMP)`
- Move the exit sensor to the midpoint of the top cap wall (center of the last rail points)
- Increase exit sensor radius to `RAMP.width / 2`
- In `update()`, add failsafe: if `onRamp && (ball.y < -100 || ball.x > IMG_W + 100)`, revert to playfield and reposition at exit

**Verification:**
- Ball enters ramp, rides along rails, hits the top cap or exit sensor, transitions back to playfield cleanly. Ball never leaves the screen while on the ramp.
