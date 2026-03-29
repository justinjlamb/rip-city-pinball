---
title: "fix: Redesign ramp — replace collision filtering with scripted path"
type: fix
status: active
date: 2026-03-28
---

# Fix: Redesign Ramp

## Problem Frame

The collision-filtering ramp approach is fundamentally broken. Matter.js lacks continuous collision detection for static bodies. When a fast ball enters the ramp, it passes through the thin guide walls (8px) in a single physics step. Once outside the ramp channel, the ball is stuck in RAMP collision mode and can no longer interact with any playfield element — it passes through flippers, walls, bumpers. The game becomes unplayable.

This is not a tuning problem. It's a design problem. Thicker walls, more physics iterations, and speed clamping are all band-aids that don't address the core issue: Matter.js cannot reliably prevent a fast ball from tunneling through thin static walls.

## Solution: Scripted Path Ramp

Replace the physics-based ramp with a scripted path approach:

1. Ball hits the entrance sensor → ball is removed from the physics simulation
2. Ball is visually animated along the bezier path over ~1.5 seconds
3. At the exit point, ball is re-added to the physics simulation with controlled velocity
4. The ball is visible the entire time — it looks like it's riding the ramp
5. No collision filtering needed. No mask switching. No tunneling possible.

This looks and feels identical to a real physics ramp from the player's perspective. The ball visibly travels along the curved path. The difference is mechanical: instead of guide walls keeping the ball on track (which fails), the code directly controls the ball's position during the ramp traversal.

## Requirements Trace

- R1. Ball visibly travels along the ramp path (not teleported)
- R2. Ball cannot get stuck or lost during ramp traversal
- R3. Ramp awards points on completion
- R4. Ball re-enters playfield physics at the exit with controlled velocity
- R5. Works reliably at any ball speed

## Scope Boundaries

- Remove ALL collision filtering code (COL.RAMP, setBallToRamp, setBallToPlayfield, onRamp state)
- Keep COL.PLAYFIELD and COL.BALL as they are (they don't cause problems)
- Remove ramp guide walls entirely (no physics walls for the ramp)
- Keep the canvas-drawn ramp rails (visual only)
- Keep the entrance sensor (PLAYFIELD category, detects ball entry)
- Remove exit sensor (no longer needed — scripted path ends at the exit point)

## Key Technical Decisions

- **Ball removed from physics during ramp:** `World.remove(world, ball)` when entering, `World.add(world, ball)` when exiting. During traversal, the ball body exists but is not in the physics world — it's positioned manually each frame along the bezier.

- **Animation speed:** Traverse the bezier from t=0 to t=1 over ~90 frames (1.5 seconds at 60fps). This gives a natural-feeling ramp speed. The animation always completes — the ball cannot "fail" the ramp by going too slow. If we want a speed requirement, check the ball's velocity at the entrance and reject slow balls before removing them from physics.

- **Speed gate at entrance:** Only trigger the ramp if the ball is moving upward with speed > 8. Slow balls bounce off the entrance area normally.

- **Re-entry velocity:** When the ball exits the ramp, set a fixed velocity vector pointing toward the right inlane. This is consistent and predictable.

## Implementation Units

- [ ] **Unit 1: Remove collision filtering ramp, implement scripted path**

**Goal:** Replace the entire ramp system. Remove physics guide walls, collision categories for ramp, mask switching. Add scripted bezier traversal.

**Files:**
- Modify: `v2.html`

**Approach:**
- Remove: `COL.RAMP`, `setBallToRamp()`, `setBallToPlayfield()`, `onRamp`, `rampBallBody` state
- Remove: All ramp guide wall creation in `createRamp()` (the `createWall` calls with `COL.RAMP`)
- Remove: Cap walls, exit sensor
- Remove: Ramp collision handling in the `collisionStart` event (entrance and exit handlers)
- Remove: Gravity reduction block in `update()`
- Remove: Rollback and failsafe blocks in `update()`
- Keep: `createRamp()` but simplified — only creates the entrance sensor and caches rail points for rendering
- Keep: `renderRamp()` unchanged (visual rails)
- Add: `rampAnimating` boolean, `rampT` float (0 to 1), `rampBall` reference
- Add: In collision handler, when ball hits `ramp-entrance` and speed > 8: set `rampAnimating = true`, `rampT = 0`, `rampBall = ballBody`, `World.remove(world, ballBody)`
- Add: In `update()`, if `rampAnimating`: increment `rampT` by 1/90 per frame, position ball along bezier at `rampT`, when `rampT >= 1`: `World.add(world, rampBall)`, set exit velocity, award points, set `rampAnimating = false`
- Keep: All `COL.PLAYFIELD` collision filters on existing bodies (they work fine)

**Verification:**
- Ball enters ramp entrance → visibly slides along the bezier path → exits at the end with controlled velocity → lands on playfield → all walls and flippers work normally
- Ball too slow to enter → bounces off entrance area normally
- No ball ever gets stuck or lost
- All existing gameplay (bumpers, slingshots, multiball, launcher) unchanged
