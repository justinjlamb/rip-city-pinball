# Fork vs. Build: pinball-schminball Evaluation

## Source Log
- [github.com/igorski/pinball-schminball] - Full source review of all 5,509 lines. MIT licensed. TypeScript + Vue 3 + Vite + zcanvas + matter-js + matter-attractors. (credibility: high -- read every relevant file)
- [Rip City Pinball index.html] - Full review of all 1,278 lines. Vanilla JS + Matter.js + canvas 2D. (credibility: high -- it's our code)
- Build test: `npm install` (2s, 289 packages) and `npm run build` (1.25s) both succeed cleanly on macOS. (credibility: high -- tested empirically)

---

## 1. Build & Dependencies

**pinball-schminball builds cleanly.** `npm install` pulls 289 packages (2s), `npm run build` via Vite produces a production bundle in 1.25s. Zero errors.

**Dependencies that matter:**
- `matter-js` 0.19.0 (we use 0.20.0 via CDN -- minor version diff, compatible)
- `matter-attractors` 0.1.6 -- their flipper system depends on this
- `zcanvas` 6.0.5 -- Igor Zinken's own canvas rendering library. Handles sprites, viewport panning, animation loop, resource loading. **Deep coupling** -- every Actor, every Renderer, the game loop, and viewport management all go through zcanvas
- `poly-decomp` 0.3.0 + `pathseg` 1.2.1 -- for SVG-to-physics conversion
- `vue` 3.5.13 + `vue-i18n` for UI chrome
- `axios` + `bowser` -- for high scores service + browser detection

**Our current deps:** Matter.js from CDN. That's it. Zero build step.

---

## 2. What "Reskinning" Actually Requires

### The easy parts:
- Replace `background.png` -- swap their 800x2441 PNG with our 1748x2432 PNG
- Replace scoring labels/text -- `definitions/game.ts` constants + `messages.json` i18n strings
- Replace sprite PNGs (ball, flippers) -- `public/assets/sprites/`

### The hard parts (this is where the cost lives):

**A. Physics shape replacement (the big one)**
Their table walls are a SINGLE SVG path file (`shape.svg`, 24 lines) that defines the entire table boundary as one complex compound shape. `svg-loader.ts` parses SVG paths into Matter.js vertices via `Matter.Svg.pathToVertices()` + `poly-decomp` for convex decomposition.

Our table uses ~30 individual wall segments + ~16 bezier curves, each defined as separate `Bodies.rectangle()` calls with explicit coordinates. We don't have an SVG representation of our table.

**To reskin, you'd need to:** Either (a) create an SVG that traces our entire table boundary -- a significant art/tooling task, or (b) rip out the SVG loading system and replace it with our segment-based wall creation. Option (b) means rewriting `engine.ts` lines 102-117 (table body + reflector loading).

**B. Collision layer system -- they don't have one**
Our game has a collision category/mask system with 5 layers (ALWAYS, PLAYFIELD, LEFT_RAMP, RIGHT_RAMP, LAUNCHER). The ball changes layer when entering trigger zones. This is fundamental to our table design -- ramps pass OVER the playfield.

pinball-schminball has NO layer system. All bodies collide with everything. Their "underworld" is a separate vertical section below the main table (at y > 1441), not an overlapping layer. Their engine creates bodies without collision filter categories.

**Forking would require adding our entire layer system** to engine.ts, table definitions, and game.ts. This is not reskinning -- it's a feature addition to their engine.

**C. zcanvas rendering library -- complete replacement needed**
Every visual element (ball, bumpers, flippers, background, triggers) renders through zcanvas `Sprite` subclasses. zcanvas manages the animation loop, viewport panning, sprite layering, and resource loading.

Our game renders everything through raw canvas 2D context calls (ctx.arc, ctx.fillRect, gradients, composite operations). Our visual style (neon glows, chrome flipper gradients, basketball-textured ball, particle effects, screen shake) is all hand-drawn.

**You cannot reskin their renderers.** You'd have to rewrite every renderer class to produce our visual style, OR strip zcanvas entirely and replace it with our canvas rendering system. Either way, the rendering is a complete rewrite.

**D. Table dimensions -- different coordinate spaces**
Their tables are 800x2441 pixels. Our table image is 1748x2432. All physics coordinates, flipper positions, bumper positions, trigger zones would need to be recalculated. Every number in the table definition changes.

---

## 3. Vue 3 Coupling

**How tightly is Vue coupled to game logic?**

The game logic itself (`model/game.ts`, `model/physics/engine.ts`, actor classes) is **pure TypeScript with no Vue dependency**. Vue only appears in:
- `App.vue` -- game lifecycle (start, pause, settings screens)
- `pinball-table.vue` -- wraps the zcanvas instance, handles keyboard/touch input, displays score/messages
- UI chrome components (menus, modals, settings, high scores, tutorial)

**Could you strip Vue?** Yes, and it's the easier part. The game engine (`model/game.ts`) exports pure functions: `init()`, `update()`, `setFlipperState()`, `bumpTable()`, `scaleCanvas()`. These take a `zCanvas` and game config -- no Vue reactivity involved. The Vue components are presentation wrappers.

**But stripping Vue solves the wrong problem.** Vue is maybe 600 lines of wrapper code. The expensive dependencies are zcanvas (deeply integrated into every actor and renderer) and the SVG physics pipeline (incompatible with our table definition format).

---

## 4. Table Definition Schema

Their `TableDef` type (definitions/game.ts lines 216-230):
```typescript
type TableDef = {
    name: string;
    soundtrackId: string;
    width: number;
    height: number;
    underworld?: number;
    background: string;
    body: ShapeDef;        // SVG path for the ENTIRE table boundary
    poppers: PopperDef[];  // ball launchers + reflectors
    flippers: FlipperDef[];
    reflectors: ShapeDef[]; // MORE SVG shapes (slingshot triangles)
    rects: ObjectDef[];     // rectangular static bodies (walls, blockers)
    bumpers: ObjectDef[];   // circular bumpers
    triggerGroups: TriggerDef[];  // sensor groups that award points/bonuses
};
```

**Could we create a table3.ts for Rip City?** Partially. We could fill in: `flippers`, `bumpers`, `rects` (our straight walls), `poppers` (our launcher). But the `body` field requires an SVG, the `reflectors` require SVGs, and we don't have `triggerGroups` -- our trigger system is spatial zones with layer transitions, not collision-based sensors.

More importantly: their schema has no concept of collision layers/categories. Adding our layer system means extending `ObjectDef`, `FlipperDef`, and the engine to support per-body collision filters. That's schema surgery, not data entry.

---

## 5. Flipper Approach

**Their approach: matter-attractors plugin**

Each flipper is a dynamic rectangle body pinned to a static pivot via a `Constraint`. Two invisible "attractor" circles are placed above and below the flipper. When `triggerFlipper()` sets the flipper state, the attractor bodies pull the flipper up or down using the `matter-attractors` plugin (which applies forces between bodies each physics tick).

Key parameters:
- Flipper body: 132x41px rectangle, chamfered edges, no friction air
- `FLIPPER_FORCE = 0.002266...` -- the attractor force multiplier
- Constraint stiffness: 0 (floppy joint, relies on attractors for positioning)

**Our approach: static body, direct angle control**

Each flipper is a static rectangle. On each frame, we calculate the target angle (rest vs. active), lerp toward it, then `Body.setAngle()` + `Body.setPosition()` to move it. When the flipper is moving upward and the ball is nearby, we `Body.applyForce()` directly on the ball.

Key parameters:
- Paddle: 280x32px, chamfer radius 8
- FLIP_REST = 0.55 rad, FLIP_ACTIVE = -0.55 rad
- FLIP_UP_SPEED = 0.22 rad/frame, FLIP_DN_SPEED = 0.10 rad/frame
- Force: { x: +/-0.02, y: -0.06 } when ball is within paddle length

**Would forking give us "working flippers for free"?**

No. Their flippers work for their table geometry and scale (800px wide, 132px flippers). Our table is 1748px wide with 280px flippers. The attractor force constants, pivot positions, invisible boundary circles, and constraint geometry would all need recalibration. Flipper tuning is one of the hardest parts of pinball physics -- you can't just change numbers and expect it to feel right.

Additionally, their attractor approach has a known weakness: the ball can sometimes pass through the flipper at high speed because attractors create forces, not hard constraints. Our static-body approach has more deterministic collision because the flipper is always exactly where we say it is.

**Neither approach is clearly superior.** Ours is simpler and more predictable. Theirs is more physically realistic (flipper actually "swings") but requires the attractor plugin and careful tuning.

---

## 6. Time Estimates

### Option A: Fork pinball-schminball and reskin

| Task | Time | Notes |
|------|------|-------|
| Learn codebase architecture | 3-4 hrs | 5,500 lines across 49 files, TypeScript, zcanvas internals, attractor physics |
| Strip Vue, replace with vanilla JS input handling | 2-3 hrs | Touch areas, keyboard, game lifecycle |
| Replace/strip zcanvas rendering with our canvas2D | 8-12 hrs | Every renderer class, animation loop, viewport panning |
| Create SVG physics shape for our table OR replace SVG system | 6-10 hrs | Either trace our table in SVG (art task) or rewrite engine body loading |
| Add collision layer system | 4-6 hrs | New concept for their engine, per-body categories, ball mask switching |
| Recalibrate all physics for 1748x2432 coordinates | 3-4 hrs | Every position, every force constant, flipper tuning |
| Port our custom features (debug overlay, layer vis, attract mode) | 3-4 hrs | Their debug mode is minimal |
| Add Moda Center multiball, ramp scoring, layer transitions | 3-4 hrs | Game logic specific to our table |
| TypeScript overhead (we're vanilla JS) | 2-3 hrs | Either learn TS workflow or strip types |
| **Total** | **34-50 hrs** | |

### Option B: Continue building from scratch

| Task | Time | Notes |
|------|------|-------|
| Fix current flipper impulse tuning | 2-3 hrs | Ball sometimes doesn't get enough upward velocity |
| Add remaining playfield features (targets, lanes, rollover switches) | 4-6 hrs | We have the physics editor, geometry is mapped |
| Scoring system expansion | 2-3 hrs | Combo multipliers, target groups, Moda Center bonus |
| Sound effects refinement | 1-2 hrs | We have the synth engine, needs more sounds |
| Attract mode polish, game over screen | 1-2 hrs | Already working, needs visual polish |
| Mobile touch controls | 1-2 hrs | Already working, needs testing |
| Viewport panning (if table taller than screen) | 2-3 hrs | Not needed yet -- our table fits most screens |
| **Total** | **13-21 hrs** | |

### Option C: Cherry-pick engine patterns

| Task | Time | Notes |
|------|------|-------|
| Study their engine.ts patterns | 1-2 hrs | Understand positionIterations, velocityIterations, speed cap |
| Port speed cap logic | 0.5 hrs | Simple utility function |
| Port bumper restitution approach | 0.5 hrs | We already have this, theirs is slightly different |
| Evaluate attractor flippers vs our approach | 1-2 hrs | Test in isolation, see if it's better |
| Port trigger group concept (if useful) | 2-3 hrs | Their sensor-based trigger groups are a good pattern |
| **Total** | **5-8 hrs** | |

---

## 7. The Third Option: Cherry-Pick

**What's worth extracting from pinball-schminball:**

1. **`positionIterations = 100`** -- They crank collision detection accuracy way up since only the ball moves. We should test this (currently using Matter.js defaults). One line.

2. **Speed cap pattern** -- `capSpeed()` clamps ball velocity to `MAX_SPEED` on every engine tick. We don't have this -- our ball can occasionally reach escape velocity. Easy to port.

3. **Trigger group concept** -- Their `TriggerGroup` class (161 lines) is a well-designed pattern for "hit these N targets to unlock a bonus." Types: BOOL (hit all in any order) and SERIES (hit in sequence within a time window). We could port this concept (not the code, since it's coupled to zcanvas) to add target groups to our table.

4. **Popper/reflector concept** -- Sensor bodies that apply impulses on collision. Clean pattern for slingshots, kickers, and ball save mechanisms.

5. **Table definition schema** -- The idea of a data-driven table definition is good, but their schema doesn't fit our needs (no layers, requires SVG). We could design our own schema inspired by theirs.

**What's NOT worth extracting:**

- Attractor-based flippers -- adds dependency (matter-attractors), more complex, not clearly better than our approach
- zcanvas rendering -- completely different rendering paradigm
- SVG physics pipeline -- we already have our physics editor + segment-based approach
- Vue UI chrome -- we don't need it

---

## Working Thesis

**Continue building from scratch (Option B), cherry-pick specific patterns (Option C).**

The fork path is a trap. It looks shorter on paper ("they already have a working game!") but the actual work is dominated by REPLACING their systems, not reusing them. Of the 5,500 lines in pinball-schminball:
- ~1,200 lines are Vue UI chrome (menus, modals, settings, i18n) -- we don't need
- ~500 lines are zcanvas rendering -- incompatible with our rendering
- ~300 lines are the SVG physics pipeline -- incompatible with our table format
- ~450 lines are the game loop + Actor/physics engine -- partially useful, but deeply coupled to zcanvas
- ~600 lines are styles/config -- irrelevant

The reusable kernel is maybe 200-300 lines of game logic patterns (trigger groups, poppers, speed cap, collision handling). Those patterns can be understood and reimplemented in our vanilla JS codebase in ~5-8 hours -- faster than learning and then surgically replacing the 5,000 lines of infrastructure we don't want.

**Key factors in this recommendation:**

1. **Build toolchain overhead.** We currently have zero build step -- open index.html in a browser and it works. Forking means adopting Vite + TypeScript + Vue + npm. For a project where Justin's daughter is learning alongside, the simplicity of "one HTML file" is a feature, not a limitation.

2. **Our table design is fundamentally different.** The collision layer system (ramps overlapping the playfield) is not an afterthought -- it's the core architecture of our table. Their engine has no concept of this. Adding it means touching every body creation path.

3. **We already have working infrastructure.** Physics editor (647 lines), debug overlay with per-layer filtering, working flippers, collision events, multiball, attract mode. Forking means rebuilding all of this inside their architecture.

4. **Flipper tuning is table-specific.** Whether we use attractors or direct control, the constants need to be tuned for our specific table geometry. No free lunch here.

---

## Immediate Actions from Cherry-Pick

Port these to our existing codebase (est. 2-3 hours total):

```javascript
// 1. Crank collision detection accuracy (one line in init())
engine.positionIterations = 100;
engine.velocityIterations = 16;

// 2. Speed cap on every tick (add to beforeUpdate handler)
const MAX_SPEED = 55;
function capSpeed(body) {
  Body.setVelocity(body, {
    x: Math.max(Math.min(body.velocity.x, MAX_SPEED), -MAX_SPEED),
    y: Math.max(Math.min(body.velocity.y, MAX_SPEED), -MAX_SPEED),
  });
}
```

Then design our own trigger group system inspired by theirs, but using our collision categories and spatial trigger zones.

---

## Confidence

**Confident.** Read every relevant file in both codebases. Built the fork project to verify it works. Compared architectures point by point. The incompatibilities (collision layers, rendering, table format, coordinate space) are structural, not cosmetic. No amount of reskinning bridges them -- you'd be rewriting the game inside their file structure, which is strictly worse than continuing in ours.

---

## Open Questions

- None critical. The recommendation is clear from the code analysis.
- Minor: Should we adopt TypeScript for our game at some point? Not for the fork question, but for long-term maintainability. (Answer: not yet -- single-file simplicity matters more while learning.)
