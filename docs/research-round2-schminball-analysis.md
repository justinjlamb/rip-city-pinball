# Pinball-Schminball: Complete Architecture Analysis

**Repo:** https://github.com/igorski/pinball-schminball
**Author:** Igor Zinken (igorski.nl), 2021-2024
**License:** MIT
**Stack:** Vue 3 + TypeScript + Vite + Matter.js 0.19 + zCanvas 6.0

---

## 1. High-Level Architecture

```
Vue App (App.vue)
  |
  +-- PinballTable component (pinball-table.vue)
        |
        +-- zCanvas (Canvas 2D rendering engine)
        |     |
        |     +-- Background Sprite (PNG image)
        |     +-- Actor Renderers (draw calls on Canvas 2D context)
        |           - BallRenderer (sprite-based, rotates)
        |           - FlipperRenderer (sprite-based, rotates around pivot)
        |           - BumperRenderer (draws circles)
        |           - RectRenderer (draws rectangles)
        |           - TriggerRenderer (draws circles with stroke)
        |
        +-- Matter.js Engine (physics simulation)
        |     |
        |     +-- Table body (SVG -> vertices -> static body)
        |     +-- Reflectors (SVG -> vertices -> static bodies)
        |     +-- Ball(s) (dynamic circular body)
        |     +-- Flippers (rectangle + constraint + attractors)
        |     +-- Bumpers (static circles, restitution=1.0)
        |     +-- Poppers (sensors, apply impulse on collision)
        |     +-- Rects (static rectangles, walls/guides)
        |     +-- Triggers (static sensors, detect ball passage)
        |
        +-- Game Logic (model/game.ts, pure functions module)
              |
              +-- Collision handler
              +-- Score system
              +-- Ball lifecycle
              +-- Underworld transitions
              +-- Tilt mechanism
```

**Key insight:** Physics and rendering are completely separated. Matter.js handles all collision/movement. zCanvas handles all drawing. The Actor class bridges them -- each Actor holds a reference to its Matter.js body and its zCanvas Sprite renderer. On every frame, Actor.update() syncs the body position to the renderer bounds.

**Rendering approach:** Canvas 2D via zCanvas library. NOT WebGL. NOT DOM/CSS. A single `<canvas>` element. The PNG background is loaded as a Sprite resource and drawn first. All actors are drawn on top. zCanvas manages the viewport (scrolling/panning) and the render loop.

---

## 2. Physics Engine (`src/model/physics/engine.ts`, 292 lines)

### createEngine()

The factory function that builds the entire physics world. Signature:

```ts
createEngine(
  table: TableDef,
  beforeUpdateHandler: () => void,
  collisionHandler: (event: CollisionEvent) => void
): Promise<IPhysicsEngine>
```

### Critical Engine Settings

```ts
engine.positionIterations = 100;  // DEFAULT is 6. This is 16x higher.
engine.velocityIterations = 16;   // DEFAULT is 4. This is 4x higher.
engine.gravity.y = GRAVITY;       // 0.85 (see game.ts constants)
```

**WHY so high?** Comment says: "in pinball we only have the ball(s) moving while all other bodies are static, as such we can increase the collision detection accuracy." This prevents the ball tunneling through thin walls at high speeds.

### Physics Constants (from `definitions/game.ts`)

```ts
GRAVITY       = 0.85
FLIPPER_FORCE = 0.002666666 * GRAVITY  // = ~0.002267
LAUNCH_SPEED  = 25 * GRAVITY           // = 21.25
MAX_SPEED     = 55 * GRAVITY           // = 46.75
```

### Table Body Creation (SVG -> Physics)

```ts
const bodyVertices = await loadVertices(table.body.source);
Matter.Bodies.fromVertices(
  table.body.left + table.body.width / 2,
  table.body.top + table.body.height / 2,
  bodyVertices,
  { isStatic: true },
  true  // flagInternal = true (removes internal edges from decomposition)
);
```

The table walls are a SINGLE complex polygon defined in an SVG file (`shape.svg`). The SVG is fetched, parsed, paths extracted, converted to vertices via `Matter.Svg.pathToVertices(path, 30)` (sample length = 30), then decomposed via `poly-decomp` into convex shapes that Matter.js can use.

The resulting body gets `setupTableBody()` applied:
```ts
body.friction    = 0;
body.restitution = 0;
```

### Reflectors

Same SVG-to-vertices pipeline as the table body, but with `restitution: 0.5` (bouncy).

### Flipper System (ATTRACTOR-BASED)

This is the most complex part. Flippers use `matter-attractors` plugin, NOT angular velocity or direct rotation.

**How it works:**
1. A rectangle body is created for the flipper visual
2. A static circle body is created at the pivot point (radius 5)
3. A constraint connects them (stiffness: 0)
4. Two invisible circles ("ignorable" bodies) are created above and below the pivot
5. These invisible circles have `attractor` plugins attached
6. When flipper is "up", the upper attractor pulls the flipper tip toward it
7. When flipper is "down", the lower attractor pulls it back

```ts
// Attractor force calculation:
{
  x: (a.position.x - b.position.x) * FLIPPER_FORCE,  // 0.002267
  y: (a.position.y - b.position.y) * FLIPPER_FORCE,
}
```

The ignorable circles use a special collision group so balls pass through them:
```ts
const ignoreGroup = Matter.Body.nextGroup(true);  // non-colliding group
```

**Flipper dimensions (hardcoded in Flipper class):** 132w x 41h

**Pivot positioning:**
- Left flipper: pivot at `left - width/2` (left edge)
- Right flipper: pivot at `left + width/2` (right edge)

**Movement restriction circles:**
```ts
// Left flipper
ignorableX = pivotX + 30
lowerMult = 0.8
upper: createIgnorable(ignorableX, pivotY - width, height * 1.5, plugin(UP))
lower: createIgnorable(ignorableX, pivotY + width * 0.8, height, plugin(DOWN))

// Right flipper
ignorableX = pivotX - 20
lowerMult = 0.7
upper: createIgnorable(ignorableX, pivotY - width, height * 1.5, plugin(UP))
lower: createIgnorable(ignorableX, pivotY + width * 0.7, height, plugin(DOWN))
```

The entire composite (body + pivot + constraint + 2 ignorables) is rotated by `actor.angle` around the pivot point.

### Speed Cap

```ts
capSpeed(body: Matter.Body): void {
  Matter.Body.setVelocity(body, {
    x: Math.max(Math.min(body.velocity.x, MAX_SPEED), -MAX_SPEED),  // clamp to +/- 46.75
    y: Math.max(Math.min(body.velocity.y, MAX_SPEED), -MAX_SPEED),
  });
}
```

Called on `beforeUpdate` for every ball. Prevents physics explosions.

### Ball Launch

```ts
launchBall(body: Matter.Body, impulse: Point): void {
  Matter.Body.setVelocity(body, impulse);  // NOT applyForce. Direct velocity set.
}
```

### Debug Renderer

A commented-out Matter.Render that overlays physics wireframes on top of the game canvas. Available in non-production mode. Renders at 75% opacity with angle indicators, collision points, and velocity vectors.

### IPhysicsEngine Interface

```ts
interface IPhysicsEngine {
  engine: Matter.Engine;
  update: (ticks: number) => void;
  addBody: (actor: Actor, label: string) => Matter.Body;
  removeBody: (body: Matter.Body) => void;
  updateBodyPosition: (body: Matter.Body, position: Point) => void;
  launchBall: (body: Matter.Body, impulse: Point) => void;
  triggerFlipper: (type: ActorTypes, upwards: boolean) => void;
  capSpeed: (body: Matter.Body) => void;
  destroy: () => void;
}
```

---

## 3. Table Definitions (`src/definitions/tables/`)

### TableDef Schema

```ts
type TableDef = {
  name: string;              // Display name
  soundtrackId: string;      // Music track ID
  width: number;             // Table pixel width
  height: number;            // Table pixel height (TALL, like real pinball)
  underworld?: number;       // Y coordinate where underworld begins
  background: string;        // Path to PNG background
  body: ShapeDef;            // SVG collision shape for walls
  poppers: PopperDef[];      // Ball launchers + kickers
  flippers: FlipperDef[];    // Flipper positions
  reflectors: ShapeDef[];    // SVG-shaped bouncy surfaces
  rects: ObjectDef[];        // Rectangular static bodies (walls, guides)
  bumpers: ObjectDef[];      // Circular bumpers
  triggerGroups: TriggerDef[]; // Scoring triggers
};
```

### Table 1: "Endless August"
- **Dimensions:** 800 x 2441 pixels
- **Underworld starts at:** y=1441 (table extends 1000px below the "normal" play area)
- **Background:** `./assets/sprites/table1/background.png`
- **SVG body:** `./assets/sprites/table1/shape.svg` (positioned at left=-101, top=-845)
- **Poppers (7):**
  - Ball launcher at (750, 1380), force = 24 * GRAVITY = 20.4, direction UP (default)
  - 2 one-time "lucky" saves at sides of bottom flippers: (18, 1282) and (703, 1282)
  - 2 reflectors near center: at (335, 720) angle 62deg UP_LEFT force 1.5, and (380, 720) angle -62deg UP_RIGHT force 1.5
  - 2 slingshots: at (150, 1090) angle 62deg UP_RIGHT force 4, and (528, 1090) angle -62deg UP_LEFT force 4
- **Flippers (6):**
  - 2 top flippers: left at (54, 533) angle 20deg, right at (572, 650) angle -20deg
  - 2 bottom flippers: left at (215, 1310), right at (410, 1310)
  - 2 underworld flippers: left at (215, 2280), right at (530, 2075)
- **Reflectors (2):** SVG-shaped bouncy surfaces at left/right of slingshot area
- **Rects (20):** Walls, blockers, guides. Mix of visible and invisible (`visible: false`). Include outer boundary walls and underworld guide rails.
- **Bumpers (11):** 3 in top cluster, 8 in underworld spread across the area
- **Trigger Groups (8):**
  - MULTIBALL (4 triggers across top, roundRobin=true, BOOL type)
  - UNDERWORLD (1 invisible sensor trigger at center)
  - MULTIPLIER (3 triggers, roundRobin=true, BOOL)
  - 3 SEQUENCE_COMPLETION (SERIES type, messages: LOOP, LOOP, TRICK_SHOT)
  - 1 SEQUENCE_COMPLETION (BOOL type, message: GROUP_COMPLETE)

### Table 2: "Rollerball"
- **Dimensions:** 800 x 2290 pixels
- **No underworld** (no `underworld` property)
- **Poppers (4):** launcher at (740, 544) force 21, directional pushers, one "lucky" save
- **Flippers (8):** 4 pairs stacked vertically (top, second, second-from-bottom, bottom)
- **Reflectors:** none
- **Rects (26):** More complex layout with many invisible guide walls
- **Bumpers (8):** Distributed across play area
- **Trigger Groups (8):** Includes a TELEPORT trigger (moves ball back to launcher)

**Key architectural point:** Both tables are 800px wide. Heights vary (2441 vs 2290). The aspect ratio is approximately 3:1 (tall portrait), mimicking real pinball table proportions.

---

## 4. Type System (`src/definitions/game.ts`, 231 lines)

### Game Constants

```ts
FRAME_RATE = 60
BALL_WIDTH = 40, BALL_HEIGHT = 40
GRAVITY = 0.85
FLIPPER_FORCE = 0.002267 (0.002666666 * 0.85)
LAUNCH_SPEED = 21.25 (25 * 0.85)
MAX_SPEED = 46.75 (55 * 0.85)
MAX_BUMPS = 3 (tilt after 3 bumps)
BUMP_IMPULSE = 4
BUMP_TIMEOUT = 2000 (ms between bump count decay)
BALLS_PER_GAME = 3
RETRY_TIMEOUT = 3000 (free retry if ball lost within 3s of launch)
TRIGGER_EXPIRY = 5000 (ms before incomplete series triggers reset)
SEQUENCE_REPEAT_WINDOW = 3000 (ms to repeat sequence for bonus)
```

### Scoring Values

```ts
AwardablePoints = {
  BUMPER: 500,
  TRIGGER: 100,
  TRIGGER_GROUP_COMPLETE: 2500,
  TRIGGER_GROUP_SEQUENCE_COMPLETE: 25000,
  UNDERWORLD_UNLOCKED: 10000,
  ESCAPE_BONUS: 25000,
};
```

All points are multiplied by `game.multiplier` (starts at 1, doubles on MULTIPLIER trigger completion, caps at 32).

### Enums

```ts
ActorTypes: CIRCULAR, RECTANGULAR, LEFT_FLIPPER, RIGHT_FLIPPER, TRIGGER
ActorLabels: BALL="ball", FLIPPER="flipper", POPPER="popper", BUMPER="bumper", TRIGGER="trigger", TRIGGER_GROUP="trigger-group"
GameMessages: MULTIPLIER, MULTIBALL, LOOP, GROUP_COMPLETE, TRICK_SHOT, UNDERWORLD_UNLOCKED, ESCAPE_BONUS, GOT_LUCKY, TRY_AGAIN, TILT
GameSounds: BALL_OUT, BUMP, BUMPER, EVENT, FLIPPER, POPPER, TRIGGER
TriggerTarget: MULTIPLIER, MULTIBALL, SEQUENCE_COMPLETION, UNDERWORLD, TELEPORT
TriggerTypes: BOOL (all must be hit), SERIES (all in succession within timeout)
ImpulseDirection: LEFT, RIGHT, UP, DOWN, DOWN_LEFT, DOWN_RIGHT, UP_LEFT, UP_RIGHT
```

### GameDef (runtime state)

```ts
type GameDef = {
  id: string | null;
  active: boolean;
  paused: boolean;
  table: number;       // index into tables array
  score: number;
  balls: number;       // remaining balls
  multiplier: number;  // score multiplier (1-32)
  underworld: boolean; // whether underworld is currently accessible
};
```

---

## 5. SVG Loading Pipeline (`src/services/svg-loader.ts`, 57 lines)

```
SVG file path
  -> fetch() as text
  -> DOMParser.parseFromString() as "image/svg+xml"
  -> querySelectorAll("path")
  -> Matter.Svg.pathToVertices(path, 30)  // sample length 30
  -> Returns Vector[][] (cached by file path)
```

**Dependencies:**
- `poly-decomp` - Decompose concave polygons into convex ones (required by Matter.js)
- `pathseg` polyfill - Loaded at runtime via `loadScript("./pathseg.js")` for SVGPathSeg API

**Caching:** Vertex results are cached in a `Map<string, Vector[][]>`. Same SVG file won't be parsed twice.

**Critical detail:** `Matter.Common.setDecomp(PolyDecomp)` must be called before any SVG vertex conversion. This is done at module load time.

---

## 6. Actor System (`src/model/`)

### Actor (base class, 181 lines)

All game objects extend Actor. Key responsibilities:
- Holds Matter.js body reference
- Holds zCanvas Sprite renderer reference
- Converts between Matter.js center-of-mass coordinates and top-left rendering coordinates
- Syncs position on every frame via `cacheBounds()`

**Constructor flow:**
1. Convert degrees to radians for angle
2. Offset bounds from top-left to center-of-mass (Matter.js convention)
3. If rotated, compute rotated bounding box and adjust position
4. Call `register()` which adds body to physics engine and renderer to canvas

**Key coordinate translation (the most important pattern):**

Matter.js positions bodies at their center of mass. Rendering uses top-left corner. The Actor bridges this:

```ts
// In constructor (top-left -> center):
this.bounds = {
  left: left + this.halfWidth,
  top: top + this.halfHeight,
  width, height
};

// In cacheBounds (center -> top-left for rendering):
this.bounds.left = body.position.x - this.halfWidth;
this.bounds.top = body.position.y - this.halfHeight;
```

### Ball (`src/model/ball.ts`, 54 lines)

```ts
class Ball extends Actor {
  // Type: CIRCULAR, fixed: false (dynamic body)
  // Physics properties:
  body.friction = 0.05;
  body.frictionAir = 0.001;
  body.frictionStatic = 0.1;
  body.restitution = 0;  // NO bounce off walls
  body.slop = 0.001;     // Very tight collision tolerance
  // Uses BallRenderer, labeled "ball"
}
```

**Ball creation** (in `model/game.ts`):
```ts
function createBall(left: number, top: number): Ball {
  return new Ball({ left, top, width: BALL_WIDTH, height: BALL_HEIGHT }, engine, canvas);
  // BALL_WIDTH = BALL_HEIGHT = 40 pixels
}
```

Ball is always created at the first popper's position minus BALL_HEIGHT (so it sits just above the launcher).

### Bumper (`src/model/bumper.ts`, 49 lines)

```ts
class Bumper extends Actor {
  collided = false;  // Flag for renderer animation
  // Type: CIRCULAR, fixed: true (static)
  body.restitution = 1.0;  // Full bounce
  // Uses BumperRenderer, labeled "bumper"
}
```

### Flipper (`src/model/flipper.ts`, 59 lines)

```ts
class Flipper extends Rect {
  private isUp = false;
  // Hardcoded dimensions: width=132, height=41
  // fixed: false (dynamic, moved by attractors)
  body.friction = 0.05;

  trigger(up: boolean): boolean {
    if (up === this.isUp) return false;
    this.isUp = up;
    this.engine.triggerFlipper(this.type, this.isUp);
    return up;
  }
}
```

### Popper (`src/model/popper.ts`, 101 lines)

The ball launcher/kicker. A sensor body (detects collision but doesn't reflect ball).

```ts
class Popper extends Rect {
  once: boolean;           // One-time use (safety catches)
  direction: ImpulseDirection;
  force: number;

  getImpulse(): Point {
    // Returns {x, y} velocity vector based on direction and force
    // UP: {0, -force}
    // DOWN: {0, force}
    // LEFT: {-force, 0}
    // UP_LEFT: {-force, -force/2}
    // etc.
  }
}
```

**Key pattern:** Popper is invisible by default (renderer only in debug mode). The impulse is directional -- the `ImpulseDirection` enum maps to x/y component combinations. Diagonal directions use `force/2` for the secondary axis.

### Rect (`src/model/rect.ts`, 65 lines)

Base class for rectangular actors. Extends Actor with:
- Pivot point tracking (for rotation rendering)
- `setupTableBody()` applied to make friction=0, restitution=0
- Visible rects use RectRenderer, invisible ones return null

### Trigger (`src/model/trigger.ts`, 51 lines)

Individual trigger sensor. Type: CIRCULAR, fixed: true. Has `active` boolean state.

### TriggerGroup (`src/model/trigger-group.ts`, 162 lines)

Container for related Trigger actors. Manages group completion logic.

**Trigger types:**
- **BOOL:** All triggers must be hit (any order). Group completes when `activeTriggers.size === triggers.length`
- **SERIES:** All triggers must be hit within `TRIGGER_EXPIRY` (5000ms). Timer starts on first hit, resets all if expired.

**Round-robin mechanic:** When `roundRobin: true`, flipping left/right flippers rotates which triggers are active. Left flipper shifts active states left (array shift), right flipper shifts right (array pop/unshift). This creates a "catch the lit trigger" mechanic.

**Completion counter:** `completions` tracks how many times the group was completed. For SEQUENCE_COMPLETION targets, points are multiplied by completions (rewarding rapid re-completion). Counter resets after `SEQUENCE_REPEAT_WINDOW` (3000ms) or on `TRIGGER_EXPIRY`.

**Overrides `register()` differently:** Instead of creating a single body, creates child Trigger actors from the ObjectDef array. The TriggerGroup itself has no physics body -- individual Triggers do. The game maps each Trigger's body ID to the parent TriggerGroup in the actorMap.

---

## 7. Game Logic (`src/model/game.ts`, 452 lines)

This is the game controller. Pure TypeScript module (not a class). Manages the entire game lifecycle.

### Module-Level State

```ts
let engine: IPhysicsEngine;
let ball: Ball;
let table: TableDef;
let inUnderworld = false;
const actorMap: Map<number, Actor> = new Map();  // body.id -> Actor
const balls: Ball[] = [];
let triggerGroups: TriggerGroup[] = [];
let flippers: Flipper[] = [];
let tableHasUnderworld: boolean;
let canvas: zCanvas;
let backgroundRenderer: Sprite;
let panOffset = 0;           // half viewport height minus half ball width
let viewportWidth = 0;
let viewportHeight = 0;
let underworldOffset = 0;    // table.underworld - viewportHeight
let roundStart = 0;          // performance.now() at round start
let bumpAmount = 0;
let tilt = false;
let paused = false;
const ENGINE_INCREMENT = 1000 / FRAME_RATE;  // 16.67ms
```

### init() -- Game Initialization

1. Clean up previous instances (dispose all actors, clear canvas)
2. Create physics engine with collision handler
3. Load PNG background as zCanvas Sprite
4. Create all Actors from table definition:
   - Poppers -> Popper instances
   - Flippers -> Flipper instances
   - Bumpers -> Bumper instances
   - TriggerGroups -> TriggerGroup instances (each creates child Triggers)
   - Rects -> Rect instances
5. Start music
6. Call `startRound()`
7. Return `{ width, height: table.underworld ?? height }` -- viewport limits

### Collision Handler (inline in init())

On every `collisionStart`, iterates pairs. Only processes pairs where `bodyB` is the ball.

**bodyA label routing:**
- `"popper"`: Apply popper's impulse to ball. If `once`, show GOT_LUCKY message and remove popper.
- `"bumper"`: Award 500 points, set `bumper.collided = true` (triggers animation), play sound.
- `"trigger"`: Find parent TriggerGroup, call `trigger(bodyId)`. If not SERIES type, award 100 points. If group completed:
  - UNDERWORLD: Set `game.underworld = true`, award 10000, show message. After 2.5s, if ball is slow, launch it upward.
  - MULTIPLIER: Double `game.multiplier` (cap at 32).
  - MULTIBALL: Award 2500, spawn 5 extra balls staggered 150ms apart at current position.
  - SEQUENCE_COMPLETION: Award 25000 * completions count.
  - TELEPORT: Award 25000 (ESCAPE_BONUS), remove ball, respawn at launcher after 2s.

### update() -- Frame Update (called by zCanvas render loop)

```ts
export const update = (timestamp, framesSinceLastRender): void => {
  // 1. Update physics: capped at 2x normal increment to prevent glitches
  engine.update(Math.min(ENGINE_INCREMENT * framesSinceLastRender, ENGINE_INCREMENT * 2));

  // 2. Update all actors (sync physics -> rendering)
  actorMap.forEach(actor => actor.update(timestamp));

  // 3. Pan viewport to follow lowest ball
  if (balls.length > 1) {
    balls.sort by top position descending;  // follow lowest ball
  }
  canvas.panViewport(0, computedY);
};
```

**No substeps.** Single `Engine.update()` call per frame. But the high `positionIterations` (100) and `velocityIterations` (16) compensate.

**Viewport panning logic:**
```ts
const y = ball.bounds.top - panOffset;
// panOffset = (viewportHeight / 2) - (BALL_WIDTH / 2)
// This centers the ball vertically in the viewport

canvas.panViewport(0,
  y > underworldOffset && (top < underworld || !inUnderworld)
    ? underworld - viewportHeight  // Lock viewport at underworld boundary
    : y                             // Follow ball
);
```

### handleEngineUpdate() -- Physics Pre-Update

Called on every physics tick (Matter.js `beforeUpdate` event). For each ball:

1. Cap speed to MAX_SPEED on both axes
2. Check underworld entry/exit:
   - Single ball entering underworld with `game.underworld = true`: transition to underworld mode, apply low-pass filter on music (2000Hz)
   - Single ball exiting underworld: award ESCAPE_BONUS (25000), reset underworld, remove filter
   - Multiball entering underworld: just remove that ball
3. Check if ball fell off table bottom: remove ball, either end round or respawn
4. If single ball lost within `RETRY_TIMEOUT` (3000ms) of round start: free retry (respawn at launcher)

### Tilt System (bumpTable)

```ts
export const bumpTable = (game): void => {
  // Give stationary balls a random impulse
  for (ball of balls) {
    if (Math.abs(ball.velocity.y) > 2) continue;  // airborne = no effect
    const horizontalForce = ball.velocity.x > 0 ? BUMP_IMPULSE : -BUMP_IMPULSE;
    engine.launchBall(ball.body, { x: Math.random() * horizontalForce, y: -BUMP_IMPULSE });
  }
  // Tilt after 3 bumps
  if (++bumpAmount >= MAX_BUMPS) {
    tilt = true;  // Disables flippers
    messageHandler(TILT, 5000);
    endRound(game, 5000);
  }
  // Bump count decays after 2000ms
  setTimeout(() => { bumpAmount = Math.max(0, bumpAmount - 1); }, BUMP_TIMEOUT);
};
```

### Ball Lifecycle

```
startRound()
  -> createBall(popper[0].left, popper[0].top - BALL_HEIGHT)
  -> Ball sits on launcher popper
  -> Player triggers popper by collision (ball placed overlapping it)
  -> Ball launches upward

Ball in play:
  -> Physics simulation
  -> Collisions trigger game events
  -> Viewport follows ball

Ball lost:
  -> Falls past table.height (or underworld height if accessible)
  -> removeBall() -> dispose actor, remove from balls array
  -> If within RETRY_TIMEOUT of start: free retry
  -> Otherwise: endRound()

endRound():
  -> Play BALL_OUT sound
  -> Set low-pass filter to 1000Hz
  -> Wait timeout (3500ms default, 5000ms for tilt)
  -> Decrement game.balls
  -> If balls === 0: game.active = false (game over)
  -> Otherwise: startRound() again
```

### Multiball

```ts
function createMultiball(amount: number, left: number, top: number): void {
  for (let i = 0; i < amount; ++i) {
    setTimeout(() => createBall(left - (BALL_WIDTH * i), top), 150 * i);
  }
}
```

Creates 5 balls staggered 150ms apart, offset horizontally by `BALL_WIDTH * i`. During multiball, viewport follows the lowest ball. If any multiball enters the underworld, it's just removed (no transition). When only 1 ball remains, normal single-ball rules resume.

### Viewport Scaling (scaleCanvas)

```ts
export const scaleCanvas = (clientWidth, clientHeight): void => {
  canvas.setDimensions(table.width, table.height);  // World size = table size
  const zoom = clientWidth < table.width ? clientWidth / table.width : 1;
  viewportWidth = width / zoom;
  viewportHeight = height / zoom;
  canvas.setViewport(viewportWidth, viewportHeight);
  canvas.scale(zoom);
  panOffset = (viewportHeight / 2) - (BALL_WIDTH / 2);
  underworldOffset = table.underworld - viewportHeight;
};
```

The game world is always 800px wide (table width). The viewport is sized to fit the client window. If the client is narrower than 800px, it scales down. The viewport scrolls vertically to follow the ball.

---

## 8. Rendering System (`src/renderers/`)

All renderers extend zCanvas's `Sprite` class. They override `draw()` which receives the `IRenderer` (Canvas 2D wrapper) and `Viewport` (scroll offset).

### BallRenderer (69 lines)

- Uses a pre-loaded PNG sprite (`ball.png`)
- Spins based on velocity: `rotation += velocity.x * SPIN_SPEED` (SPIN_SPEED = 30)
- Always spins at least slightly (if x=0, uses 0.2)
- Draws via `renderer.drawImageCropped()` with rotation via `getDrawProps()`
- Manually calls `update()` in `draw()` because balls are not in the main actorMap forEach

### FlipperRenderer (67 lines)

- Uses pre-loaded PNG sprites (`flipper_left.png` / `flipper_right.png`)
- Rotates around a pivot point (from the Flipper/Rect actor's `getPivot()`)
- Converts angle from radians to degrees for zCanvas rotation
- Draws via `renderer.drawImageCropped()`

### BumperRenderer (78 lines)

- Draws circles (NOT sprite-based)
- Default state: transparent fill with #00AEEF (blue) stroke, radius * 1.1 (slightly larger)
- Collision state: solid #00AEEF fill at normal radius
- Collision animation: 15 frames of solid color, then reset
- Pre-computes collision offset on construction

### RectRenderer (74 lines)

- Draws rectangles or rounded rectangles (if `radius > 0`)
- Color: "gray" (hardcoded)
- Handles rotation via pivot point
- Uses `bowser` library to detect Safari < 16 (no `roundRect()` support) and falls back to no radius
- Draws via `renderer.drawRect()` or `renderer.drawRoundRect()`

### TriggerRenderer (50 lines)

- Draws circles with stroke only (no fill)
- Active: white (#FFF) stroke
- Inactive: blue (#00AEEF) stroke
- Stroke size: 2

**Key rendering insight:** The PNG background contains ALL the visual art (table artwork, flipper visual, etc). The renderers draw simple geometric shapes ON TOP of the background for interactive elements. Only the ball and flippers use actual PNG sprites. Everything else is drawn as primitive shapes (circles, rectangles).

---

## 9. Underworld System

The "underworld" is a vertically extended play area below the normal table. Think of it as a bonus level below the drain.

**How it works:**
1. Table definition specifies `underworld: 1441` (Y coordinate where it starts)
2. There's a trigger group with `target: TriggerTarget.UNDERWORLD` -- the player must hit this trigger to unlock it
3. When unlocked, `game.underworld = true` -- the ball can now pass through the underworld boundary instead of being lost
4. When ball enters underworld: music gets low-pass filtered (2000Hz), `inUnderworld = true`
5. When ball exits back up through boundary: award ESCAPE_BONUS (25000), reset underworld, remove filter
6. If ball falls off the bottom of the full table (including underworld): normal ball-lost behavior
7. During multiball: balls that enter the underworld are just removed (no transition)

**Viewport behavior:** When ball is above the underworld threshold and not in underworld mode, viewport panning is locked so it doesn't scroll past the underworld boundary. This prevents showing the underworld area before it's unlocked.

Table 2 has NO underworld (property not defined). Table 1's underworld extends from y=1441 to y=2441 (1000 extra pixels of play area) with its own flippers, bumpers, and walls.

---

## 10. Input System (`pinball-table.vue`)

### Keyboard Controls
- **Left arrow (37):** Left flipper (keydown=up, keyup=down)
- **Right arrow (39):** Right flipper
- **Space (32):** Bump table (throttled to 150ms)
- **P (80):** Pause (debug only)
- **Up/Down arrows (38/40):** Pan viewport (debug only)

### Touch Controls
- **Left half of screen:** touchstart=left flipper up, touchend=left flipper down
- **Right half of screen:** touchstart=right flipper up, touchend=right flipper down
- **Swipe up (>100px in <400ms):** Bump table

Touch areas are full-height, half-width fixed `<div>` elements overlaying the canvas. `overscroll-behavior: contain` prevents browser navigation gestures.

### Flipper State Flow

```
User input -> setFlipperState(type, isDown)
  -> For each flipper of matching type: flipper.trigger(isDown)
    -> engine.triggerFlipper(type, isUp)
      -> Sets isLeftFlipperUp or isRightFlipperUp boolean
      -> Attractor plugin checks these booleans on each physics step
      -> Attractor force pulls flipper body toward up or down position

  -> On flipper release (isDown=false):
    -> For each trigger group: moveTriggersLeft() or moveTriggersRight()
    -> This implements the round-robin trigger shifting
```

**Important:** ALL flippers of the same type fire together. If a table has 3 left flippers, pressing left arrow activates all 3.

---

## 11. Audio System (`src/services/audio-service.ts`)

- Web Audio API with BiquadFilter for low-pass filtering (underworld effect)
- Sound effects with random pitch variation (`detune` in -1200 to +1200 cent range) to prevent repetitive sounds
- Music from local MP3 files (SoundCloud API was originally used but disabled due to token invalidation)
- Sound effects: ball_out, bump, bumper, event, flipper, popper, trigger (all `.mp3`)
- Effects bus with BiquadFilter for detuning
- Master bus -> low-pass filter -> AudioContext.destination
- `setFrequency()` ramps filter frequency over 1.5s (used for underworld transitions)

---

## 12. Asset Pipeline

### Sprites (PNG)
- `ball.png` - Ball sprite (loaded as ImageBitmap via zCanvas.Loader)
- `flipper_left.png` - Left flipper sprite (ImageBitmap)
- `flipper_right.png` - Right flipper sprite (ImageBitmap)
- `table{N}/background.png` - Table background (loaded as Image via zCanvas)

### SVGs (Physics shapes)
- `table{N}/shape.svg` - Table walls/boundaries collision shape
- `table{N}/reflector_left.svg` - Left reflector shape (table 1 only)
- `table{N}/reflector_right.svg` - Right reflector shape (table 1 only)

### Audio
- `music_{trackId}.mp3` - Background music per table
- `sfx_*.mp3` - Sound effects (7 files)

### Preloading (`src/services/asset-preloader.ts`)
1. Load `pathseg.js` polyfill via script injection
2. Queue all sprite bitmaps (ball, flippers)
3. Queue all table backgrounds and SVG files
4. Process queue sequentially (one asset at a time)

---

## 13. Vue App Structure

### Component Hierarchy
```
App.vue
  +-- Loader (shown during asset preload)
  +-- HeaderMenu (collapsable during game)
  +-- PinballTable (main game, async loaded)
  |     +-- RoundResults (score overlay between rounds)
  +-- Tutorial (first-time overlay, async loaded)
  +-- Modal
        +-- NewGameWindow (table selection, player name)
        +-- HighScores
        +-- Settings
        +-- HowToPlay
        +-- About
```

### Game Lifecycle in App.vue
1. `preloadAssets()` on mount
2. Audio context unlocked on first user interaction
3. `initGame()` creates GameDef object:
   ```ts
   game = {
     id: randomOrHighScoreId,
     active: false,
     paused: showTutorial,
     table: selectedTableIndex,
     score: 0,
     balls: BALLS_PER_GAME,  // 3
     multiplier: 1,
     underworld: false,
   };
   ```
4. Setting `game.id` triggers watcher in PinballTable which calls `init()`
5. Game runs until `game.active` becomes false
6. If high scores enabled, score is submitted on game end

---

## 14. Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `matter-js` | 0.19.0 | Physics engine |
| `matter-attractors` | 0.1.6 | Flipper movement via attraction forces |
| `poly-decomp` | 0.3.0 | Concave polygon decomposition for SVG shapes |
| `pathseg` | 1.2.1 | SVGPathSeg polyfill for Matter.Svg.pathToVertices |
| `zcanvas` | 6.0.5 | Canvas 2D rendering, sprite management, viewport |
| `vue` | 3.5+ | UI framework |
| `bowser` | 2.11.0 | Browser detection (Safari roundRect check) |
| `lodash.throttle` | 4.1.1 | Bump throttling |
| `axios` | 1.13.5 | HTTP (used for SoundCloud API, currently disabled) |
| `tiny-script-loader` | 2.2.1 | Dynamic script loading (pathseg polyfill) |

---

## 15. Architecture Decisions and WHY

### Why Canvas 2D (zCanvas) instead of WebGL?
The game uses zCanvas which wraps Canvas 2D. This is simpler than WebGL, has better browser compatibility, and is sufficient for 2D sprite rendering with rotation. The game doesn't need particle effects, shaders, or 3D transforms that would justify WebGL complexity.

### Why attractors for flippers instead of angular constraints?
Matter.js constraints can be finicky for controlled angular movement. The attractor approach gives more predictable flipper behavior -- the flipper is "pulled" toward its target position by invisible anchor points, creating a smooth arc motion without having to calculate angular velocities or deal with constraint instability.

### Why SVG for table walls?
SVG paths can represent arbitrary curved shapes (the organic curves of a pinball table). Converting SVG to vertices via `Matter.Svg.pathToVertices()` with `poly-decomp` for convex decomposition is the standard Matter.js approach for complex shapes. It's more precise than manually defining rectangle/circle bodies to approximate curves.

### Why sensors for poppers/triggers?
Sensors detect collision without physically blocking the ball. This is correct for:
- Poppers: The ball should pass through and receive an impulse, not bounce off
- Triggers: The ball should pass through invisible checkpoints, not be deflected

### Why separate background PNG?
The background PNG contains all the visual art -- the painted table surface, decorative elements, lane markings. Physics bodies (rectangles, circles) don't need to match the art exactly. Invisible bodies can guide the ball where the visual art suggests rails/walls exist. This decouples art from physics completely.

### Why module-level state in game.ts?
The game controller uses module-level variables instead of a class. This is a deliberate choice for a singleton game state -- there's only ever one active game. It avoids `this` binding issues and keeps the API simple (exported functions vs. class methods).

### Why no substeps?
Matter.js `Engine.update()` is called once per frame with `positionIterations: 100` and `velocityIterations: 16` instead. This is equivalent to many substeps in terms of collision accuracy but simpler to implement. The high iteration counts compensate for the single-step approach.

### Why speed capping?
Without `capSpeed()`, the ball could reach velocities where it tunnels through bodies between physics steps. Clamping to MAX_SPEED (46.75) on each axis prevents this. The cap is applied in the `beforeUpdate` callback, ensuring it's enforced before each simulation step.

---

## 16. Patterns Directly Applicable to Rip City Pinball

### Ball Properties to Replicate
```ts
friction: 0.05
frictionAir: 0.001
frictionStatic: 0.1
restitution: 0     // NO bounce off walls
slop: 0.001        // Tight collision
```

### Engine Settings to Replicate
```ts
positionIterations: 100
velocityIterations: 16
gravity.y: 0.85
```

### Flipper Architecture
The attractor-based flipper system is complex but proven. Key numbers:
- Flipper body: 132w x 41h
- Pivot circle: radius 5
- Constraint stiffness: 0
- Attractor force: 0.002267
- Restriction circles above/below pivot (offset by +/-30px)

### Viewport Scrolling
- Viewport centers on ball vertically
- `panOffset = (viewportHeight / 2) - (BALL_WIDTH / 2)`
- Smooth following, no interpolation (direct position set per frame)

### Popper/Launcher Pattern
- Ball spawns directly on top of the popper sensor
- When ball contacts popper, `setVelocity()` is called (not applyForce)
- Direction and force are configurable per popper

### Table Definition as Data
Everything is declarative -- positions, sizes, angles, forces. Tables are pure data objects. This makes table creation a design task, not a coding task.
