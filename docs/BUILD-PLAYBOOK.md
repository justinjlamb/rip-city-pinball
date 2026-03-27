# Rip City Pinball — Expert Build Playbook
*Compiled from 2 rounds of deep research (14 agents total) — Mar 22, 2026*
*This is the single source of truth for building the game. Follow it step by step.*

---

## The 30-Second Summary

Static flippers + `updateVelocity=true` + `positionIterations: 100` + ball restitution 0 + speed clamping. Stay with Matter.js. Don't fork anything. Cherry-pick patterns from pinball-schminball. Ship after Phase 5. Total estimated build time: 10-15 hours across 5-6 sessions.

---

## Phase 0: The One-Line Fix That Changes Everything (30 minutes)

**The discovery:** Matter.js's collision resolver computes velocity from `position - positionPrev`, not from `body.velocity`. When we call `Body.setAngle(body, angle)` without the third argument, it moves `anglePrev` in lockstep → zero delta → zero impulse. Pass `true` as the third argument and the resolver sees real angular velocity.

**The fix — change `positionFlipper()`:**

```javascript
// BEFORE (broken — zero impulse):
function positionFlipper(body, hinge, angle) {
  const halfLen = PADDLE_LEN / 2;
  Body.setAngle(body, angle);
  Body.setPosition(body, {
    x: hinge.x + Math.cos(angle) * halfLen,
    y: hinge.y + Math.sin(angle) * halfLen
  });
}

// AFTER (working — real impulse transfer):
function positionFlipper(body, hinge, angle) {
  const halfLen = PADDLE_LEN / 2;
  Body.setAngle(body, angle, true);      // ← updateVelocity=true
  Body.setPosition(body, {
    x: hinge.x + Math.cos(angle) * halfLen,
    y: hinge.y + Math.sin(angle) * halfLen
  }, true);                                // ← updateVelocity=true
}
```

**Then DELETE the manual force hack in `updateFlippers()`** (the `Body.applyForce` block at the bottom). The resolver handles impulse naturally now — tip hits harder than base, direction is correct, restitution is respected.

**How it works (verified against Resolver.js source):**
- Resolver computes: `bodyAAngularVelocity = bodyA.angle - bodyA.anglePrev`
- With `updateVelocity=true`, `anglePrev` stays at the OLD angle → delta is nonzero
- Contact point velocity = angular velocity × distance from hinge (perpendicular)
- Ball receives impulse proportional to this velocity
- `isStatic` check only prevents impulse TO the flipper, not FROM it

**Test:** Press Z/M — ball should launch upward with real force. Tip should hit harder than base. If this works, everything else follows.

**If it doesn't work:** Planck.js fallback (see Appendix A). But it will work — this is how the physics engine is designed.

---

## Phase 1: Physics Foundation (1 session, ~2 hours)

After confirming Phase 0 works, tune the physics engine:

### Engine Settings
```javascript
// Option A: High iterations, single update (pinball-schminball approach)
engine.positionIterations = 100;  // 17x default — brute-force collision accuracy
engine.velocityIterations = 16;
// Use default Runner or single Engine.update() per frame

// Option B: Moderate iterations + substeps (research recommendation)
engine.positionIterations = 20;
engine.velocityIterations = 10;
// Manual 3-substep loop:
function gameLoop(timestamp) {
  const delta = Math.min(timestamp - lastTimestamp, 32); // cap for tab-switch
  lastTimestamp = timestamp;
  for (let i = 0; i < 3; i++) {
    Engine.update(engine, 1000 / 180);
  }
  update();
  renderFrame();
  requestAnimationFrame(gameLoop);
}
```

**Recommendation: Use Option A first** (simpler, proven by pinball-schminball). Switch to Option B only if performance is an issue on the showcase laptop.

### Ball Properties
```javascript
const pinball = Bodies.circle(x, y, BALL_RADIUS, {
  restitution: 0,        // ← ZERO. All bounce comes from walls/bumpers.
  friction: 0.05,        // Low — glossy playfield
  frictionAir: 0.015,    // Slight air resistance
  density: 0.003,        // Heavier than default — more momentum
});
```

### Speed Clamping (in beforeUpdate)
```javascript
Events.on(engine, 'beforeUpdate', function() {
  const MAX_SPEED = 45;  // pinball-schminball uses 46.75
  [pinball, ...multiballs].forEach(ball => {
    if (!ball || ball.isStatic) return;
    const v = ball.velocity;
    const speed = Math.sqrt(v.x * v.x + v.y * v.y);
    if (speed > MAX_SPEED) {
      const s = MAX_SPEED / speed;
      Body.setVelocity(ball, { x: v.x * s, y: v.y * s });
    }
  });
});
```

### Stuck Ball Detection
```javascript
let stuckFrames = 0;
// In beforeUpdate:
if (pinball && !pinball.isStatic) {
  const speed = Math.sqrt(pinball.velocity.x**2 + pinball.velocity.y**2);
  if (speed < 0.3 && pinball.position.y < 2100) { // not near drain
    stuckFrames++;
    if (stuckFrames > 180) { // stuck for 3 seconds
      Body.setVelocity(pinball, { x: (Math.random()-0.5)*5, y: -3 });
      stuckFrames = 0;
    }
  } else {
    stuckFrames = 0;
  }
}
```

---

## Phase 2: Slingshots + Enhanced Bumpers (1 session, ~2 hours)

### Slingshots (triangular kicker sensors)
```javascript
// Create from existing wall positions
const leftSlingVerts = [
  { x: 435, y: 1680 }, { x: 556, y: 2020 }, { x: 180, y: 1900 }
];
const rightSlingVerts = [
  { x: 1274, y: 1680 }, { x: 1150, y: 2020 }, { x: 1390, y: 1960 }
];

function createSlingshot(vertices, label) {
  const cx = vertices.reduce((s, v) => s + v.x, 0) / 3;
  const cy = vertices.reduce((s, v) => s + v.y, 0) / 3;
  const body = Bodies.fromVertices(cx, cy, [vertices], {
    isStatic: true, isSensor: true, label: label,
    collisionFilter: { category: CAT.ALWAYS, mask: CAT.BALL }
  });
  body._layer = 'always';
  body._label = label;
  body._debugColor = '#ff4444';
  allWallBodies.push(body);
  World.add(world, body);
  return body;
}
```

### Collision handler for slingshots + enhanced bumpers
```javascript
// In collisionStart handler:
if (bodyA.label.startsWith('slingshot')) {
  const dx = ballBody.position.x - bodyA.position.x;
  const dy = ballBody.position.y - bodyA.position.y;
  const dist = Math.sqrt(dx*dx + dy*dy) || 1;
  Body.applyForce(ballBody, ballBody.position, {
    x: (dx/dist) * 0.06, y: (dy/dist) * 0.06
  });
  score += 500;
  shake = 8;
  emitParticles(bodyA.position.x, bodyA.position.y, '#ff4444', 10, 6);
  sndSlingshot();
}

// Enhanced bumper hit (add directional kick on top of restitution):
if (bodyA.label === 'bumper') {
  const dx = ballBody.position.x - bodyA.position.x;
  const dy = ballBody.position.y - bodyA.position.y;
  const dist = Math.sqrt(dx*dx + dy*dy) || 1;
  Body.applyForce(ballBody, ballBody.position, {
    x: (dx/dist) * 0.08, y: (dy/dist) * 0.08
  });
  // ... scoring, effects (existing code)
}
```

### Bumper flash effect (additive blend)
```javascript
// In renderBumperFlash:
ctx.globalCompositeOperation = 'screen'; // or 'lighter' for more intensity
ctx.beginPath();
ctx.arc(cx, cy, r * 1.3, 0, Math.PI * 2);
ctx.fillStyle = `rgba(255, 200, 50, ${flash * 0.7})`;
ctx.fill();
ctx.globalCompositeOperation = 'source-over';
```

---

## Phase 3: Scoring Engine (1 session, ~2 hours)

### Combo System
```javascript
let comboCount = 0;
let comboTimer = 0;
const COMBO_WINDOW = 120; // frames (2 sec at 60fps)
const COMBO_MULT = [1, 1, 1.5, 2, 2.5, 3, 4, 5];
let scoreMultiplier = 1; // persistent multiplier from ramp completions

function registerHit(basePoints, label) {
  comboCount++;
  comboTimer = COMBO_WINDOW;
  const comboMult = COMBO_MULT[Math.min(comboCount - 1, COMBO_MULT.length - 1)];
  const pts = Math.round(basePoints * comboMult * scoreMultiplier);
  score += pts;
  if (comboCount > 1) {
    showMessage(`${comboCount}x COMBO! +${pts.toLocaleString()}`);
  } else {
    showMessage(`${label} +${pts.toLocaleString()}`);
  }
}

// In update():
if (comboTimer > 0) {
  comboTimer--;
  if (comboTimer <= 0) comboCount = 0;
}
```

### Scoring Values
```javascript
const POINTS = {
  BUMPER: 1000,
  SLINGSHOT: 500,
  RAMP_ENTRY: 2000,
  RAMP_COMPLETE: 5000,
  DETAILS_FORM: 2500,
  MODA_CENTER: 10000,
  MULTIBALL_JACKPOT: 50000,
};
```

### End-of-Ball Bonus
```javascript
let ballBonus = 0; // accumulated during play
let rampCompletions = 0;
let bumperHitsThisBall = 0;

function calculateEndOfBallBonus() {
  const bonus = ballBonus
    + (bumperHitsThisBall * 100)
    + (rampCompletions * 1000);
  const total = bonus * scoreMultiplier;
  score += total;
  showMessage(`BONUS: ${total.toLocaleString()}`);
  // Reset per-ball counters
  ballBonus = 0;
  bumperHitsThisBall = 0;
}
```

### Ball Save
```javascript
let ballSaveActive = false;
let ballSaveTimer = 0;
const BALL_SAVE_DURATION = 600; // 10 seconds at 60fps

function activateBallSave() {
  ballSaveActive = true;
  ballSaveTimer = BALL_SAVE_DURATION;
}

// In update():
if (ballSaveTimer > 0) {
  ballSaveTimer--;
  if (ballSaveTimer <= 0) ballSaveActive = false;
}

// In handleDrain():
if (ballSaveActive) {
  ballSaveActive = false;
  launchPinball(); // re-launch without losing a ball
  showMessage('BALL SAVED!');
  return;
}
```

---

## Phase 4: Plunger Polish (1 session, ~1 hour)

### Launcher as Sensor (pinball-schminball pattern)
```javascript
// Create a popper sensor at the bottom of the launcher channel
const launchSensor = Bodies.rectangle(1620, 2050, 80, 20, {
  isStatic: true, isSensor: true, label: 'launcher_popper',
  collisionFilter: { category: CAT.LAUNCHER, mask: CAT.BALL }
});

// Ball spawns ON the popper, overlapping it
function launchPinball() {
  Body.setStatic(pinball, false);
  Body.setPosition(pinball, { x: 1620, y: 2030 });
  Body.setVelocity(pinball, { x: 0, y: 0 });
  setBallLayer('launcher');
  gameState = 'launch';
  plungerPower = 0;
}

// Charge and fire
function firePinball() {
  const power = Math.max(0.2, plungerPower);
  const vel = -12 - (power * 33); // range: -12 to -45
  Body.setVelocity(pinball, { x: 0, y: vel });
  gameState = 'play';
  activateBallSave();
  sndLaunch();
  showMessage('BALL ' + ballNum);
}
```

### Power Meter Visual
```javascript
function renderPlunger() {
  if (plungerPower <= 0) return;
  const mW = ps(20), mH = ps(300);
  const mX = px(1680), mY = py(1600);

  // Background
  ctx.fillStyle = 'rgba(0,0,0,0.7)';
  ctx.fillRect(mX - mW/2, mY, mW, mH);

  // Fill (red gradient)
  const fillH = mH * plungerPower;
  const grad = ctx.createLinearGradient(0, mY + mH - fillH, 0, mY + mH);
  grad.addColorStop(0, '#FF2244');
  grad.addColorStop(1, '#C8102E');
  ctx.fillStyle = grad;
  ctx.fillRect(mX - mW/2 + 2, mY + mH - fillH, mW - 4, fillH);

  // Border
  ctx.strokeStyle = '#A2AAAD';
  ctx.lineWidth = 2;
  ctx.strokeRect(mX - mW/2, mY, mW, mH);
}
```

---

## Phase 5: Image Layering (1 session, ~2 hours)

### Step 1: Split the image (15-30 min in GIMP)
1. Open `table.png` in GIMP
2. Select the chrome ramp areas (Lasso/Pen tool) — the elevated rails that the ball should pass under
3. Copy selection → Paste as New Image → Export as `foreground.png` (PNG with transparency)
4. Original `table.png` is the background as-is

### Step 2: Load both images
```javascript
const bgImg = new Image();
const fgImg = new Image();
bgImg.src = 'table.png';
fgImg.src = 'foreground.png';
let bgLoaded = false, fgLoaded = false;
bgImg.onload = () => { bgLoaded = true; checkReady(); };
fgImg.onload = () => { fgLoaded = true; checkReady(); };
function checkReady() {
  if (bgLoaded && fgLoaded) startGame();
}
```

### Step 3: Draw order
```javascript
function renderFrame() {
  ctx.save();
  if (shake > 0.3) { /* shake transform */ }
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // 1. Background
  ctx.drawImage(bgImg, offX, offY, IMG_W * scale, IMG_H * scale);

  // 2. Flippers (always visible, rotate with physics)
  renderFlippers();

  // 3. Ball on playfield (UNDER ramp covers)
  if (ballLayer !== 'right_ramp' && ballLayer !== 'left_ramp') {
    renderBallShadow();
    renderBall();
    renderMultiballs();
  }

  // 4. Foreground (ramp covers — transparent PNG)
  if (fgLoaded) {
    ctx.drawImage(fgImg, offX, offY, IMG_W * scale, IMG_H * scale);
  }

  // 5. Ball on ramp (ABOVE ramp covers)
  if (ballLayer === 'right_ramp' || ballLayer === 'left_ramp') {
    renderBallShadow();
    renderBall();
  }

  // 6. Effects (bumper flashes, slingshot kicks)
  renderBumperFlash();

  // 7. Particles
  renderParticles();

  // 8. UI
  renderScoreOverlay();
  if (gameState === 'launch') renderPlunger();
  if (gameState === 'drain' || gameState === 'gameover') renderOverlay();

  // 9. Debug
  if (debugPhysics) renderDebugOverlay();

  ctx.restore();
}
```

### Ball Shadow
```javascript
function renderBallShadow() {
  if (!pinball || pinball.isStatic) return;
  const sx = px(pinball.position.x) + ps(4);
  const sy = py(pinball.position.y) + ps(4);
  const r = ps(BALL_RADIUS);
  const grad = ctx.createRadialGradient(sx, sy, r*0.2, sx, sy, r*1.2);
  grad.addColorStop(0, 'rgba(0,0,0,0.3)');
  grad.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.beginPath();
  ctx.arc(sx, sy, r * 1.2, 0, Math.PI * 2);
  ctx.fillStyle = grad;
  ctx.fill();
}
```

---

## SHIP HERE. Phases 6-8 are stretch goals.

---

## Phase 6 (stretch): Sound Polish
- Vary bumper pitch by index: `[660, 740, 830, 920]` Hz
- Add `DynamicsCompressorNode` to prevent audio clipping
- `visibilitychange` listener → `audioCtx.resume()` on tab return

## Phase 7 (stretch): Touch Controls
```javascript
canvas.addEventListener('touchstart', (e) => {
  e.preventDefault();
  for (const touch of e.changedTouches) {
    if (touch.clientX < canvas.width / 2) { isLeftPaddleUp = true; sndFlipper(); }
    else { isRightPaddleUp = true; sndFlipper(); }
    if (gameState === 'launch') plungerCharging = true;
  }
}, { passive: false });
// + CSS: touch-action: none; overscroll-behavior: none; position: fixed;
```

## Phase 8 (stretch): SVG Precision
Only if curved boundaries feel jaggy during playtesting. Trace specific curves in Figma, export SVG, load via `Matter.Svg.pathToVertices()` + `poly-decomp`.

---

## Quick Reference — All Tuning Values

```javascript
// Engine
engine.positionIterations = 100;
engine.velocityIterations = 16;
engine.gravity.y = 1.0;

// Ball
BALL_RADIUS = 36;
ball.restitution = 0;       // ZERO — all bounce from walls
ball.friction = 0.05;
ball.frictionAir = 0.015;
ball.density = 0.003;

// Speed
MAX_SPEED = 45;

// Flippers
FLIP_REST = 0.55;           // rest angle (rad)
FLIP_ACTIVE = -0.55;        // active angle (rad)
FLIP_UP_SPEED = 0.22;       // activation speed (rad/frame)
FLIP_DN_SPEED = 0.10;       // return speed (rad/frame)
LEFT_HINGE = { x: 560, y: 2200 };
RIGHT_HINGE = { x: 1120, y: 2200 };
PADDLE_LEN = 280;
PADDLE_WIDTH = 32;
// KEY: positionFlipper uses updateVelocity=true

// Bumpers
bumper.restitution = 1.5;   // above 1.0 = adds energy
bumperKickForce = 0.08;

// Slingshots
slingshotKickForce = 0.06;

// Launcher
launchVelMin = -12;
launchVelMax = -45;

// Scoring
COMBO_WINDOW = 120;         // frames (2 sec)
BALL_SAVE_DURATION = 600;   // frames (10 sec)

// Walls
outerWall.restitution = 0.3;
guideRail.restitution = 0.5;
```

---

## Decision Log

| Question | Answer | Evidence |
|----------|--------|----------|
| Matter.js or Planck.js? | Matter.js | Existing working code, `updateVelocity` solves impulse gap |
| Attractor flippers or static? | Static + `updateVelocity=true` | Source-code verified in Resolver.js |
| Fork pinball-schminball? | No — cherry-pick patterns only | Fork is 34-50 hrs, cherry-pick is 5-8 |
| Substeps or high iterations? | High iterations (simpler) | pinball-schminball ships with positionIterations=100 |
| Ball restitution? | 0 (zero) | pinball-schminball uses 0, walls provide all bounce |
| Image layers? | Manual GIMP masking | Pixel-perfect alignment guaranteed |
| Build vs. polish showcase.html? | Build pinball AND polish showcase | Showcase is mostly done, pinball is the differentiator |

---

## Appendix A: Planck.js Fallback

If `updateVelocity=true` fails (unlikely based on source analysis), Planck.js port is the fallback. Estimated 6-10 hours. The Planck.js official pinball demo uses:

```javascript
const flipper = world.createDynamicBody({ position: Vec2(x, y) });
flipper.createFixture(Box(1.75, 0.3), { density: 5.0 });
const joint = world.createJoint(RevoluteJoint({
  motorSpeed: 0,
  maxMotorTorque: 1000,
  enableMotor: true,
  lowerAngle: -30 * Math.PI / 180,
  upperAngle: 5 * Math.PI / 180,
  enableLimit: true,
}, ground, flipper, flipper.getPosition()));
// Flip: joint.setMotorSpeed(20); Release: joint.setMotorSpeed(-10);
```

Most of our code (rendering, scoring, sound, UI, layer system, debug mode) is engine-independent and would survive the port.

---

## Sources (Complete)

All scratchpad files with full source trails: `~/Developer/rip-city-pinball/docs/research-*.md`

Key references:
- [Matter.js Resolver.js](https://github.com/liabru/matter-js/blob/master/src/collision/Resolver.js) — impulse computation from position deltas
- [Matter.js Body.js](https://github.com/liabru/matter-js/blob/master/src/body/Body.js) — `updateVelocity` parameter
- [pinball-schminball](https://github.com/igorski/pinball-schminball) — reference implementation
- [lonekorean/javascript-physics](https://github.com/lonekorean/javascript-physics) — canonical Matter.js pinball
- [Lu1ky Pinball deep dive](https://frankforce.com/lu1ky-pinball-code-deep-dive/) — physics tuning values
- [Planck.js Pinball example](https://piqnt.com/planck.js/Pinball) — fallback reference
