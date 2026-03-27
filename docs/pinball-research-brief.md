# Rip City Pinball — Research Brief
*Compiled Mar 21, 2026 from 5 parallel research agents*

## The Problem We Hit Today

We spent hours fighting flippers, physics alignment, ramp layers, and visual quality. Root causes:
1. Wrong flipper architecture (static bodies can't transfer impulse to ball)
2. Wrong parameter values (PADDLE_PULL 45x too high, causing flickering)
3. No reference implementation to learn from
4. Building before understanding the fundamentals

This brief fixes all of that.

---

## The Reference Implementation: pinball-schminball

**GitHub:** https://github.com/igorski/pinball-schminball
**Demo:** https://igorski.nl/application/pinball-schminball

Uses EXACTLY our architecture:
- PNG background images for table art
- SVG collision shapes for physics boundaries
- Matter.js + matter-attractors plugin
- TypeScript, ~5,500 lines

**Study these files first:**
- `src/model/physics/engine.ts` — Matter.js setup, flipper constraints, SVG body loading
- `src/definitions/tables/table1.ts` — Data-driven table definition (PNG + SVG refs)
- `src/definitions/game.ts` — Type definitions (TableDef, FlipperDef, etc.)

---

## Build Order (What to Do First, Second, Third)

### Phase 1: Fix the Flippers (THE foundation)
Nothing else matters if flippers don't work. Switch from static bodies back to dynamic bodies with attractors, using the CORRECT values.

**The proven pattern (from lonekorean, confirmed by pinball-schminball):**
- Flipper = **dynamic body** (NOT static) — compound of trapezoid + invisible brick
- Hinge = zero-length constraint with **stiffness: 0** (not 1)
- Angle control = attractor stoppers with **PADDLE_PULL = 0.002** (not 0.06 or 0.09)
- Why dynamic matters: Matter.js only transfers momentum from bodies with real velocity. Static bodies have zero velocity in the engine's eyes → zero impulse to ball on collision.

```javascript
// THE critical values
const PADDLE_PULL = 0.002;  // force magnitude for attractors
constraint.stiffness = 0;   // let the constraint be springy
engine.constraintIterations = 4; // increase if still jittery (default 2)
```

### Phase 2: Physics Substeps + Speed Clamping
Prevents ball tunneling through flippers and walls.

```javascript
// Run 3 physics steps per render frame (180Hz physics at 60fps)
function gameLoop() {
  for (let i = 0; i < 3; i++) {
    Matter.Engine.update(engine, 1000 / 180);
  }
  render();
  requestAnimationFrame(gameLoop);
}

// Clamp ball speed every frame
Matter.Events.on(engine, 'beforeUpdate', function() {
  const maxSpeed = 25;
  const v = pinball.velocity;
  const speed = Math.sqrt(v.x * v.x + v.y * v.y);
  if (speed > maxSpeed) {
    const s = maxSpeed / speed;
    Matter.Body.setVelocity(pinball, { x: v.x * s, y: v.y * s });
  }
});
```

Also set `positionIterations: 100` and `velocityIterations: 16` (from pinball-schminball) for collision accuracy.

### Phase 3: Ball Physics Tuning

| Property | Value | Why |
|---|---|---|
| radius | 36 (current) | OK for 1748px table |
| density | 0.003 | Heavier = more momentum, less jitter (we had 0.0012) |
| restitution | 0.4 | Ball itself shouldn't be super bouncy (we had 0.5, close) |
| friction | 0.05 | Low — glossy playfield |
| frictionAir | 0.018 | Prevents infinite acceleration |

### Phase 4: SVG Physics Alignment (Replace Manual Editor)
Instead of dragging boxes in our physics-editor.html, trace physics boundaries from the table image:

**Option A — Figma/Illustrator workflow:**
1. Import table.png into Figma
2. Trace physics boundaries as vector paths on a separate layer
3. Export paths as SVG
4. Load with `Matter.Svg.pathToVertices()` + `decomp.js` for concave shapes

**Option B — PhysicsEditor tool:**
- https://www.codeandweb.com/physicseditor
- Auto-traces collision outlines from transparency
- Exports JSON directly for Matter.js

Both are dramatically more precise than our drag-and-drop editor.

### Phase 5: Split Table Image for Z-Ordering
Generate (or split) the table art into two PNGs:

1. **background.png** — Playfield surface, everything the ball rolls ON
2. **foreground.png** — Ramp covers, plastic ramps (with transparency) — everything the ball passes UNDER

Draw order per frame:
```
1. background.png
2. Ball shadow (offset dark circle)
3. Ball (if on playfield layer)
4. foreground.png (ramp covers)
5. Ball (if on ramp layer — draws ABOVE ramp)
6. Effects (bumper flashes, particles)
```

### Phase 6: Ramp Layer System (Confirmed Correct)
Our collision category/mask approach is the industry standard. Refinements:

- Use actual `isSensor: true` Matter.js bodies at ramp entrances/exits
- **Velocity direction check** — ball must be moving upward with speed > 2 to enter a ramp
- **Position-based fallback** in `beforeUpdate` — sensors can miss fast balls
- **Always include SENSOR category in ball's mask** regardless of layer
- Only change the ball's mask, never the wall categories

### Phase 7: Bumpers & Slingshots
Both need force application ON TOP of restitution:

```javascript
// On bumper collision:
const kickForce = 0.04;
Matter.Body.applyForce(ball, ball.position, {
  x: (dx / dist) * kickForce,
  y: (dy / dist) * kickForce
});
// Plus: restitution 1.3-1.7 on bumper body (adds energy)
// Plus: 100ms visual flash (screen blend mode)
// Plus: audio cue same frame
```

Slingshots: same pattern but with triangular static bodies + force on contact.

### Phase 8: Scoring & Game Feel
- Combo system with 2-second chain window
- Bumpers: 100-1000 pts (constant trickle)
- Ramp completion: 2000-5000 pts (skill reward)
- Moda Center multiball jackpot: 50,000+ pts
- End-of-ball bonus with multiplier
- Ball save: 10 seconds after launch

---

## Tuning Values Quick Reference

```javascript
// Engine
engine.gravity.y = 0.85;           // start here, tune up
engine.positionIterations = 100;   // collision accuracy
engine.velocityIterations = 16;

// Ball
ball.density = 0.003;
ball.restitution = 0.4;
ball.friction = 0.05;
ball.frictionAir = 0.018;

// Flippers
PADDLE_PULL = 0.002;               // attractor force
constraint.stiffness = 0;          // let it be springy
flipper.density = 0.02;            // heavy enough to push ball

// Bumpers
bumper.restitution = 1.5;          // above 1.0 = adds energy
bumperKickForce = 0.04;            // additional force on hit

// Walls
wall.restitution = 0.3;            // outer walls: low bounce
guideRail.restitution = 0.5;       // lane dividers: moderate
rubber.restitution = 0.8;          // rubber bands: bouncy

// Speed
maxBallSpeed = 25;                 // clamp every frame
launchVelocity = -8 to -25;       // range for plunger
```

---

## Reference Repos (Ranked by Relevance)

| Rank | Repo | Why Study It |
|---|---|---|
| 1 | [pinball-schminball](https://github.com/igorski/pinball-schminball) | PNG+SVG architecture, Matter.js, data-driven tables |
| 2 | [lab-pinball-simulation](https://github.com/georgiee/lab-pinball-simulation) | Best ramp/layer system, full game architecture |
| 3 | [festive-tree-pinball](https://github.com/mckingho/festive-tree-pinball) | Clean Matter.js flipper constraints, background art system |
| 4 | [pinball-wizard](https://github.com/fishshiz/pinball-wizard) | Simplest Matter.js pinball (~460 lines) |
| 5 | [javascript-physics](https://github.com/lonekorean/javascript-physics) | Proven attractor flipper pattern with exact values |
| 6 | [vpx-js](https://github.com/vpdb/vpx-js) | Visual Pinball in browser (architecture reference only) |

---

## What We Did Wrong Today (Lessons)

1. **Built flippers as static bodies** → zero impulse to ball. Must be dynamic.
2. **PADDLE_PULL was 0.06-0.09** → should be 0.002. 30-45x too high = flickering.
3. **Constraint stiffness was 1** → should be 0. Fights the attractor forces.
4. **No speed clamping** → ball tunnels through flippers at high speed.
5. **Single physics step per frame** → need 3 substeps for collision accuracy.
6. **Manual drag-and-drop physics alignment** → SVG trace is more precise.
7. **Single table image** → need background + foreground layers for z-ordering.
8. **Iterating visuals before physics worked** → physics first, visuals second.

---

## Sources

### Flipper Mechanics
- [lonekorean/javascript-physics (GitHub)](https://github.com/lonekorean/javascript-physics)
- [Pinball Physics CodePen](https://codepen.io/lonekorean/pen/KXLrVX)
- [JavaScript Physics with Matter.js (Coder's Block)](https://codersblock.com/blog/javascript-physics-with-matter-js/)
- [Matter.js issue #494: Limiting angle of rotation](https://github.com/liabru/matter-js/issues/494)

### Ramp/Layer Systems
- [georgiee/lab-pinball-simulation](https://github.com/georgiee/lab-pinball-simulation)
- [Ouigo Let's Play Case Study (p2.js ramp layers)](https://mercimichel.medium.com/ouigo-lets-play-case-study-b763f69dd89c)
- [vpx-js ramp-hit-generator.ts](https://github.com/vpdb/vpx-js)

### Physics Tuning
- [Lu1ky Pinball Code Deep Dive](https://frankforce.com/lu1ky-pinball-code-deep-dive/)
- [VPE Flipper Documentation](https://docs.visualpinball.org/creators-guide/manual/mechanisms/flippers.html)
- [The Quest for Great Pinball Physics](https://paladinstudios.com/2011/07/28/the-quest-for-great-pinball-physics/)

### Image Overlay Architecture
- [CartoonSmart Pinball Tutorial (dynamic z-depth)](https://cartoonsmart.com/pinball-games-for-ios-or-tvos-video-tutorials/)
- [PhysicsEditor for Phaser 3 / Matter.js](https://www.codeandweb.com/physicseditor/tutorials/how-to-create-physics-shapes-for-phaser-3-and-matterjs)
- [Canvas GPU Acceleration (Chrome)](https://developer.chrome.com/blog/taking-advantage-of-gpu-acceleration-in-the-2d-canvas)
