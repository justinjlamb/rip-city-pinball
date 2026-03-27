# Research: Complete Pinball Game Mechanics for Matter.js

## Source Log
- [lonekorean/javascript-physics pinball demo](https://github.com/lonekorean/javascript-physics) - Complete working pinball with attractor-based flippers, bumper collision, launcher. PADDLE_PULL = 0.002, BUMPER_BOUNCE = 1.5. (credibility: high - working demo, widely referenced)
- [Lu1ky Pinball Code Deep Dive](https://frankforce.com/lu1ky-pinball-code-deep-dive/) - 9 physics substeps per frame, bumper restitution 1.7, slingshots as small bumpers (r=5), spring-based plunger. (credibility: high - detailed technical breakdown)
- [georgiee/lab-pinball-simulation](https://github.com/georgiee/lab-pinball-simulation) - Slingshot entity with rubber material, state machine (hit -> powered -> off), bumper with light-on/off animation. (credibility: high - full game architecture)
- [fishshiz/pinball-wizard](https://github.com/fishshiz/pinball-wizard) - Simple Matter.js pinball with constraint-based flippers, circle bumpers, basic launcher. (credibility: medium - simpler implementation)
- [Matter.js API docs](https://brm.io/matter-js/docs/classes/Body.html) - applyForce, setVelocity, restitution, collision events. (credibility: high - official docs)
- [Matter.js issue #134](https://github.com/liabru/matter-js/issues/134) - Confirms applyForce works in collisionStart event handler. (credibility: high - from maintainer)
- [Matter.js Runner docs](https://brm.io/matter-js/docs/classes/Runner.html) - Fixed timestep with delta, multiple engine updates per frame. (credibility: high - official)

## Working Thesis

All seven mechanics can be implemented with complete, working JavaScript code tailored to the existing Rip City Pinball codebase (1748x2432 table, Matter.js 0.20.0, static flipper approach already working). The key findings:

1. **Slingshots**: Triangular static bodies using `Bodies.fromVertices()` with 3 vertices. On collision, apply directional force away from the slingshot center. The existing wall data already defines sling positions (Left Sling Top/Bot, Right Sling Top/Bot).

2. **Bumpers**: The existing bumper code already has restitution 1.5 and applyForce. Missing: the force direction should be normalized properly, and the kick force value of 0.08 in the existing code is reasonable (Lu1ky uses bumper restitution 1.7, lonekorean uses 1.5).

3. **Plunger**: The existing implementation is functional but missing the physical spring feel. The ball sits at launcher position, space charges power, release fires. Velocity range -8 to -55 (scaled for 2432px table vs typical 800px).

4. **Multiball**: Existing implementation works. Needs: ball tracking array, per-ball layer state, drain detection per ball, and proper cleanup.

5. **Game Loop**: Current code uses Runner.run() which handles timestep internally. For pinball, manual substeps (3 per frame at 1000/180 delta) give better tunneling prevention.

6. **Scoring**: Need combo system with chain timer, multiplier, and end-of-ball bonus.

7. **Speed Clamping**: beforeUpdate handler capping velocity magnitude. MaxSpeed ~25-30 for this table scale.

## Open Questions
- None critical. All mechanics have working reference implementations that can be adapted.

## Confidence
Confident. Multiple cross-referenced sources agree on approach and values. Code adapted to match the existing codebase architecture (static flippers, image overlay, collision categories).

---

## COMPLETE IMPLEMENTATION CODE

All code below is designed to drop into the existing `index.html` for Rip City Pinball. Each section shows what to ADD or REPLACE in the existing codebase.

### 1. SLINGSHOTS

The existing wall data defines slingshot positions. We need triangular sensor bodies that detect ball contact and apply a kick force.

```javascript
// ═══════════════════════════════════════════════════════════════
// SLINGSHOTS — Triangular kicker zones near the flippers
// Detect ball collision → apply directional force → flash + score
// ═══════════════════════════════════════════════════════════════

// Slingshot definitions — triangular zones positioned from the wall data
// Left sling: between Left Sling Top (435,1673→567,1974) and Left Sling Bot (166,1888→556,2149)
// Right sling: between Right Sling Top (1274,1671→1141,1979) and Right Sling Bot (1390,1975→1138,2149)
const SLINGSHOTS = [
  {
    label: 'Left Slingshot',
    // Triangle vertices (clockwise) — forms the rubber band area
    vertices: [
      { x: 435, y: 1680 },   // top-right corner (near Left Sling Top start)
      { x: 556, y: 2020 },   // bottom-right corner (where sling walls meet)
      { x: 180, y: 1900 },   // bottom-left corner (near Left Sling Bot start)
    ],
    // Force direction: push ball up and to the right (away from left sling)
    forceDir: { x: 0.06, y: -0.04 },
    pts: 500,
  },
  {
    label: 'Right Slingshot',
    vertices: [
      { x: 1274, y: 1680 },  // top-left corner (near Right Sling Top start)
      { x: 1150, y: 2020 },  // bottom-left corner (where sling walls meet)
      { x: 1390, y: 1960 },  // bottom-right corner (near Right Sling Bot start)
    ],
    // Force direction: push ball up and to the left (away from right sling)
    forceDir: { x: -0.06, y: -0.04 },
    pts: 500,
  },
];

let slingBodies = [];
let slingFlash = [0, 0]; // flash animation state

function createSlingshots() {
  SLINGSHOTS.forEach((def, i) => {
    // Create triangular body from vertices
    const body = Bodies.fromVertices(
      // Center position (average of vertices)
      (def.vertices[0].x + def.vertices[1].x + def.vertices[2].x) / 3,
      (def.vertices[0].y + def.vertices[1].y + def.vertices[2].y) / 3,
      [def.vertices],
      {
        isStatic: true,
        isSensor: true,  // sensor — detects collision without physical blocking
        label: 'slingshot',
        collisionFilter: { category: CAT.ALWAYS, mask: CAT.BALL },
        render: { visible: false },
      }
    );
    body._slingIndex = i;
    body._label = def.label;
    body._layer = 'always';
    body._debugColor = '#ff4488';
    allWallBodies.push(body);
    slingBodies.push(body);
    World.add(world, body);
  });
}

function pingSlingshot(slingBody, ballBody) {
  const idx = slingBody._slingIndex;
  if (idx === undefined) return;
  const def = SLINGSHOTS[idx];

  // Apply directional kick force
  Body.applyForce(ballBody, ballBody.position, def.forceDir);

  // Score and effects
  addScore(def.pts, 'slingshot');
  slingFlash[idx] = 1;
  shake = 8;
  emitParticles(ballBody.position.x, ballBody.position.y, RED_GLOW, 12, 6);
  showMessage('SLING! +' + def.pts);
  sndBumper(); // reuse bumper sound or create sndSling()
}

// Render slingshot flash (add to renderFrame after renderBumperFlash)
function renderSlingFlash() {
  for (let i = 0; i < SLINGSHOTS.length; i++) {
    if (slingFlash[i] > 0.05) {
      const def = SLINGSHOTS[i];
      const cx_ = px((def.vertices[0].x + def.vertices[1].x + def.vertices[2].x) / 3);
      const cy_ = py((def.vertices[0].y + def.vertices[1].y + def.vertices[2].y) / 3);

      ctx.globalCompositeOperation = 'lighter';
      ctx.beginPath();
      ctx.moveTo(px(def.vertices[0].x), py(def.vertices[0].y));
      ctx.lineTo(px(def.vertices[1].x), py(def.vertices[1].y));
      ctx.lineTo(px(def.vertices[2].x), py(def.vertices[2].y));
      ctx.closePath();
      ctx.fillStyle = 'rgba(255,50,100,0.4)';
      ctx.globalAlpha = slingFlash[i];
      ctx.fill();
      ctx.globalCompositeOperation = 'source-over';
      ctx.globalAlpha = 1;
      slingFlash[i] *= 0.88;
    }
  }
}
```

**Integration point**: In `createEvents()` collision handler, add:
```javascript
case 'slingshot':
  pingSlingshot(bodyA, bodyB);
  break;
```

And call `createSlingshots()` in `init()` after bumper creation.


### 2. BUMPERS — Enhanced with proper directional kick

The existing bumper code is close but can be improved for "punchy" feel.

```javascript
// ═══════════════════════════════════════════════════════════════
// BUMPERS — Pop bumpers with restitution + force kick
// restitution > 1.0 adds energy on bounce
// Additional applyForce adds the "pop" feel
// ═══════════════════════════════════════════════════════════════

// Enhanced bumper creation (REPLACE existing bumper creation in init())
function createBumpers() {
  TABLE_BUMPERS.forEach((def, i) => {
    const body = Bodies.circle(def.x, def.y, def.r, {
      isStatic: true,
      label: 'bumper',
      // restitution > 1.0 means the collision ADDS energy to the ball
      // This is the key to making bumpers feel punchy
      restitution: 1.5,
      friction: 0,
      collisionFilter: { category: CAT.PLAYFIELD, mask: CAT.BALL },
      render: { visible: false }
    });
    body._layer = 'playfield';
    body._label = def.label;
    body._debugColor = LAYER_COLORS.playfield;
    body._bumperIndex = i;
    bumperBodies.push(body);
    allWallBodies.push(body);
    World.add(world, body);
  });
}

// Enhanced bumper hit handler (REPLACE existing pingBumper)
function pingBumper(bumperBody, ballBody) {
  const idx = bumperBody._bumperIndex;
  if (idx === undefined) return;
  const def = TABLE_BUMPERS[idx];

  // --- DIRECTIONAL FORCE KICK ---
  // Calculate direction from bumper center to ball (push ball away)
  const dx = ballBody.position.x - bumperBody.position.x;
  const dy = ballBody.position.y - bumperBody.position.y;
  const dist = Math.sqrt(dx * dx + dy * dy) || 1;

  // Normalize direction and apply kick force
  // 0.08 is strong enough to be satisfying without being uncontrollable
  const kickForce = 0.08;
  Body.applyForce(ballBody, ballBody.position, {
    x: (dx / dist) * kickForce,
    y: (dy / dist) * kickForce
  });

  // --- SCORING ---
  addScore(def.pts, 'bumper');

  // --- VISUAL FEEDBACK ---
  bumperFlash[idx] = 1;
  bumperHitCount[idx]++;
  shake = 12;

  // Particle burst from bumper center toward ball
  emitParticles(bumperBody.position.x, bumperBody.position.y, RED_GLOW, 15, 8);

  // Show which bumper was hit
  const shortName = def.label.split('(')[1]?.replace(')', '') || def.label;
  showMessage(shortName + '! +' + def.pts.toLocaleString());
  sndBumper();
}
```

### 3. PLUNGER / LAUNCHER

Complete implementation with physical ball in channel, charge-and-release mechanic, power meter, and one-way gate.

```javascript
// ═══════════════════════════════════════════════════════════════
// PLUNGER / LAUNCHER
// Ball sits at bottom of launcher channel on launcher floor.
// Hold SPACE to charge power (visual meter fills).
// Release SPACE to launch — ball velocity proportional to charge.
// One-way gate: ball transitions from launcher→playfield when y < 400.
// ═══════════════════════════════════════════════════════════════

// --- STATE ---
let plungerPower = 0;         // 0.0 to 1.0 charge level
let plungerCharging = false;  // true while SPACE held

// --- CONSTANTS ---
const PLUNGER_CHARGE_RATE = 0.018;  // per frame — full charge in ~55 frames (~0.9s)
const PLUNGER_MIN_POWER = 0.3;     // minimum launch power (tap launch)
const LAUNCH_VEL_MIN = -12;        // weakest launch velocity (y, negative = up)
const LAUNCH_VEL_MAX = -45;        // strongest launch velocity
const LAUNCHER_X = 1620;           // ball x position in channel
const LAUNCHER_START_Y = 1900;     // ball starting y in channel

function launchPinball() {
  // Reset ball to launcher channel
  Body.setStatic(pinball, true);
  Body.setPosition(pinball, { x: LAUNCHER_X, y: LAUNCHER_START_Y });
  Body.setVelocity(pinball, { x: 0, y: 0 });
  Body.setAngularVelocity(pinball, 0);
  setBallLayer('launcher');

  gameState = 'launch';
  plungerPower = 0;
  plungerCharging = false;
  trail = [];
}

function firePinball() {
  // Clamp power to minimum (handles quick tap)
  const power = Math.max(PLUNGER_MIN_POWER, plungerPower);

  // Interpolate velocity based on power (0→1 maps to MIN→MAX)
  const launchSpeed = LAUNCH_VEL_MIN + (LAUNCH_VEL_MAX - LAUNCH_VEL_MIN) * power;

  // Make ball dynamic and fire upward
  Body.setStatic(pinball, false);
  Body.setVelocity(pinball, { x: 0, y: launchSpeed });

  gameState = 'play';
  plungerPower = 0;
  plungerCharging = false;
  ballSaveTimer = BALL_SAVE_FRAMES; // activate ball save

  showMessage('BALL ' + ballNum);
  sndLaunch();
}

// --- PLUNGER VISUAL (power meter) ---
function renderPlunger() {
  const cx_ = offX + IMG_W * scale / 2;
  ctx.textAlign = 'center';
  ctx.font = `bold ${ps(45)}px 'Oswald', sans-serif`;
  ctx.fillStyle = WHITE;
  ctx.globalAlpha = 0.4 + Math.sin(Date.now() * 0.005) * 0.3;
  ctx.fillText('HOLD SPACE TO LAUNCH', cx_, py(1200));
  ctx.globalAlpha = 1;

  // Power meter — vertical bar next to launcher channel
  if (plungerPower > 0) {
    const mW = ps(20), mH = ps(250);
    const mX = px(LAUNCHER_X), mY = py(1500);

    // Background
    ctx.fillStyle = 'rgba(0,0,0,0.6)';
    ctx.fillRect(mX - mW / 2, mY, mW, mH);

    // Fill (grows upward)
    const fillH = mH * plungerPower;
    const mGrad = ctx.createLinearGradient(0, mY + mH - fillH, 0, mY + mH);
    mGrad.addColorStop(0, '#FFD700');  // gold at top
    mGrad.addColorStop(0.5, RED_GLOW);
    mGrad.addColorStop(1, RED);
    ctx.fillStyle = mGrad;
    ctx.fillRect(mX - mW / 2, mY + mH - fillH, mW, fillH);

    // Border
    ctx.strokeStyle = SILVER;
    ctx.lineWidth = 2;
    ctx.strokeRect(mX - mW / 2, mY, mW, mH);

    // Power percentage text
    ctx.font = `bold ${ps(18)}px 'Oswald', sans-serif`;
    ctx.fillStyle = WHITE;
    ctx.textAlign = 'center';
    ctx.fillText(Math.round(plungerPower * 100) + '%', mX, mY - ps(10));
  }

  // Draw plunger spring visual at ball position
  if (plungerCharging) {
    const springY = py(LAUNCHER_START_Y + plungerPower * 80);
    const springX = px(LAUNCHER_X);
    ctx.strokeStyle = SILVER;
    ctx.lineWidth = ps(3);
    ctx.beginPath();
    // Draw compressed spring coils
    const coils = 6;
    const coilH = ps(60) * (1 - plungerPower * 0.6);
    for (let c = 0; c < coils; c++) {
      const cy_ = springY + (c / coils) * coilH;
      const dir = c % 2 === 0 ? 1 : -1;
      ctx.lineTo(springX + dir * ps(12), cy_);
    }
    ctx.stroke();
  }
}

// --- CHARGE UPDATE (call in update()) ---
// Already handled in the existing update function:
// if (plungerCharging && gameState === 'launch') {
//   plungerPower = Math.min(1, plungerPower + PLUNGER_CHARGE_RATE);
// }

// --- ONE-WAY GATE ---
// Already handled in checkLayerTransitions():
// if (ballLayer === 'launcher' && by < 400 && bvy < 0) {
//   setBallLayer('playfield');
// }
```


### 4. MULTIBALL

Complete multiball management system with proper tracking, per-ball drain detection, and cleanup.

```javascript
// ═══════════════════════════════════════════════════════════════
// MULTIBALL — Spawn extra balls, track individually, drain independently
// ═══════════════════════════════════════════════════════════════

// --- STATE ---
let multiballs = [];        // array of extra ball bodies
let isMultiball = false;    // true when multiball is active
const MAX_MULTIBALLS = 4;   // cap on extra balls at once

function triggerMultiball() {
  if (isMultiball) {
    // Already in multiball — add bonus points instead
    addScore(25000, 'multiball_bonus');
    showMessage('MULTIBALL JACKPOT! +25,000');
    return;
  }

  isMultiball = true;
  addScore(10000, 'multiball_start');

  // Spawn 2 extra balls near the Moda Center scoop exit
  const spawnPositions = [
    { x: 900, y: 1100, vx: -5, vy: -12 },
    { x: 1000, y: 1000, vx: 3, vy: -15 },
  ];

  spawnPositions.forEach(sp => {
    if (multiballs.length >= MAX_MULTIBALLS) return;

    const mb = Bodies.circle(sp.x, sp.y, BALL_RADIUS, {
      label: 'multiball',
      collisionFilter: {
        category: CAT.BALL,
        mask: LAYER_MASK.playfield,
      },
      render: { visible: false },
      restitution: 0.5,
      friction: 0.02,
      density: 0.0012,
    });
    Body.setVelocity(mb, { x: sp.vx, y: sp.vy });
    World.add(world, mb);
    multiballs.push(mb);
  });

  showMessage('MODA CENTER -- MULTIBALL!');
  sndMultiball();
  shake = 15;
  emitParticles(950, 1050, GOLD, 40, 10);
}

// Remove a single multiball when it drains
function drainMultiball(mb) {
  emitParticles(mb.position.x, mb.position.y, RED, 15, 5);
  World.remove(world, mb);
  multiballs = multiballs.filter(m => m !== mb);

  if (multiballs.length === 0) {
    isMultiball = false;
    showMessage('MULTIBALL OVER');
  }
}

// Check for multiball drains (call in beforeUpdate)
function checkMultiballDrains() {
  for (let i = multiballs.length - 1; i >= 0; i--) {
    const mb = multiballs[i];
    const by = mb.position.y;
    const bx = mb.position.x;

    // Drain: ball below table or escaped bounds
    if (by > IMG_H + 50 || bx < -50 || bx > IMG_W + 50) {
      drainMultiball(mb);
    }
  }
}

// Apply speed clamping to ALL balls (main + multi)
function clampAllBallSpeeds() {
  const MAX_SPEED = 30;
  const allBalls = pinball && !pinball.isStatic ? [pinball, ...multiballs] : [...multiballs];

  for (const ball of allBalls) {
    const v = ball.velocity;
    const speed = Math.sqrt(v.x * v.x + v.y * v.y);
    if (speed > MAX_SPEED) {
      const s = MAX_SPEED / speed;
      Body.setVelocity(ball, { x: v.x * s, y: v.y * s });
    }
  }
}

// Render all multiball bodies
function renderMultiballs() {
  for (const mb of multiballs) {
    drawBallAt(mb.position.x, mb.position.y);
  }
}

// Multiball scoring: hits during multiball are worth 2x
function getMultiballMultiplier() {
  return isMultiball ? 2 : 1;
}
```


### 5. GAME LOOP — Fixed timestep with 3 substeps

Replace the current Runner.run() + gameLoop() approach with manual substep control for better physics accuracy.

```javascript
// ═══════════════════════════════════════════════════════════════
// GAME LOOP — 3 physics substeps per frame for anti-tunneling
// Manual Engine.update replaces Runner.run for finer control.
// ═══════════════════════════════════════════════════════════════

const PHYSICS_SUBSTEPS = 3;         // 3 updates per render frame
const PHYSICS_DELTA = 1000 / 180;   // each substep = ~5.56ms (180Hz physics)

// Ball save: first 10 seconds after launch, ball returns if drained
const BALL_SAVE_FRAMES = 600;       // 10 seconds at 60fps
let ballSaveTimer = 0;

function gameLoop(timestamp) {
  // --- PHYSICS (3 substeps) ---
  for (let i = 0; i < PHYSICS_SUBSTEPS; i++) {
    Engine.update(engine, PHYSICS_DELTA);
  }

  // --- GAME LOGIC ---
  update();

  // --- RENDER ---
  resize();
  renderFrame();

  requestAnimationFrame(gameLoop);
}

function update() {
  // Plunger charging
  if (plungerCharging && gameState === 'launch') {
    plungerPower = Math.min(1, plungerPower + PLUNGER_CHARGE_RATE);
  }

  // Ball save countdown
  if (ballSaveTimer > 0) ballSaveTimer--;

  // Drain timer (between balls)
  if (gameState === 'drain') {
    drainTimer--;
    if (drainTimer <= 0) {
      // End-of-ball bonus before moving to next ball
      applyEndOfBallBonus();

      if (ballNum >= totalBalls) {
        gameState = 'gameover';
        highScore = Math.max(score, highScore);
      } else {
        ballNum++;
        trail = [];
        comboChain = 0;
        comboTimer = 0;
        scoreMultiplier = 1;
        launchPinball();
      }
    }
  }

  // Update combo timer
  updateComboTimer();

  // Update particles
  updateParticles();
}

// --- INITIALIZATION (REPLACE the current init block at bottom of file) ---
// Remove Runner.run(runner, engine) — we do manual updates now.
tableImg.onload = function() {
  imageLoaded = true;
  init();

  // Configure engine for pinball precision
  engine.positionIterations = 30;   // higher = more accurate collisions
  engine.velocityIterations = 16;   // higher = more accurate velocity solving
  engine.constraintIterations = 4;  // higher = stiffer constraints

  // Start game loop — NO Runner needed
  requestAnimationFrame(gameLoop);
};

tableImg.onerror = function() {
  console.error('Failed to load table.png');
  init();
  engine.positionIterations = 30;
  engine.velocityIterations = 16;
  engine.constraintIterations = 4;
  requestAnimationFrame(gameLoop);
};
```

**Key difference from current code**: Remove `Runner.create()` and `Runner.run()`. The manual `Engine.update()` loop with 3 substeps at 180Hz gives much better collision detection for fast-moving balls.


### 6. SCORING ENGINE — Combo system with chain timer and end-of-ball bonus

```javascript
// ═══════════════════════════════════════════════════════════════
// SCORING ENGINE — Combos, chains, multipliers, end-of-ball bonus
// ═══════════════════════════════════════════════════════════════

// --- STATE ---
let score = 0;
let highScore = 0;
let scoreMultiplier = 1;     // persistent multiplier (increases with ramp completions)
let comboChain = 0;          // current combo count within the chain window
let comboTimer = 0;          // frames remaining in the combo window
let comboMultiplier = 1;     // multiplier from current combo chain
let endOfBallBonus = 0;      // accumulated bonus awarded at end of ball
let rampCompletions = 0;     // counts ramp completions this ball (drives multiplier)
let totalBumperHits = 0;     // total bumper hits this ball

// --- CONSTANTS ---
const COMBO_WINDOW = 120;    // frames (2 seconds at 60fps) to chain hits
const COMBO_MULT_TABLE = [1, 1, 1.5, 2, 2.5, 3, 4, 5]; // multiplier by combo chain length

// --- SCORING ---
// Point values for each event type
const SCORE_TABLE = {
  bumper:           1000,   // base bumper hit
  bumper_star:      1500,   // Star bumper (bumper 1)
  slingshot:        500,    // slingshot kick
  ramp_left:        3000,   // left ramp completion
  ramp_right:       3000,   // right ramp completion
  moda_center:      5000,   // Moda Center scoop
  multiball_start:  10000,  // triggering multiball
  multiball_bonus:  25000,  // re-entering Moda during multiball (jackpot)
  target:           750,    // drop target / standup target
};

function addScore(basePoints, eventType) {
  // Apply combo multiplier
  comboChain++;
  comboTimer = COMBO_WINDOW;
  comboMultiplier = COMBO_MULT_TABLE[Math.min(comboChain, COMBO_MULT_TABLE.length - 1)];

  // Apply multiball multiplier
  const multiMult = getMultiballMultiplier();

  // Calculate final points
  const finalPoints = Math.round(basePoints * comboMultiplier * scoreMultiplier * multiMult);
  score += finalPoints;

  // Accumulate end-of-ball bonus
  endOfBallBonus += Math.round(basePoints * 0.1); // 10% of base goes to bonus pool

  // Track stats
  if (eventType === 'bumper') totalBumperHits++;

  // Combo feedback
  if (comboChain >= 3) {
    showMessage('COMBO x' + comboChain + '! +' + finalPoints.toLocaleString());
  }

  // Extra ball every 100,000 points
  if (Math.floor((score - finalPoints) / 100000) < Math.floor(score / 100000)) {
    totalBalls++;
    showMessage('EXTRA BALL!');
    sndMultiball(); // celebratory sound
  }
}

function updateComboTimer() {
  if (comboTimer > 0) {
    comboTimer--;
    if (comboTimer <= 0) {
      // Combo chain expired
      comboChain = 0;
      comboMultiplier = 1;
    }
  }
}

// Called when a ramp is completed (ball exits a ramp)
function onRampComplete(rampName) {
  rampCompletions++;

  // Every 3 ramp completions, increase the persistent score multiplier
  if (rampCompletions % 3 === 0 && scoreMultiplier < 5) {
    scoreMultiplier++;
    showMessage(scoreMultiplier + 'X MULTIPLIER!');
  }

  const pts = rampName === 'left_ramp' ? SCORE_TABLE.ramp_left : SCORE_TABLE.ramp_right;
  addScore(pts, 'ramp');
  sndRamp();
}

// End-of-ball bonus calculation (called when ball drains)
function applyEndOfBallBonus() {
  // Base bonus from accumulated hits
  let bonus = endOfBallBonus;

  // Bumper bonus: 100 per bumper hit
  bonus += totalBumperHits * 100;

  // Ramp bonus: 1000 per ramp completion
  bonus += rampCompletions * 1000;

  // Apply score multiplier to bonus
  bonus = Math.round(bonus * scoreMultiplier);

  if (bonus > 0) {
    score += bonus;
    showMessage('END OF BALL BONUS: ' + bonus.toLocaleString());
  }

  // Reset per-ball stats
  endOfBallBonus = 0;
  totalBumperHits = 0;
  rampCompletions = 0;
  // scoreMultiplier persists across balls (reward for good play)
}

// Render combo indicator (add to renderScoreOverlay)
function renderComboIndicator() {
  if (comboChain >= 2 && comboTimer > 0) {
    const barX = offX, barW = IMG_W * scale;

    // Combo timer bar (shrinking)
    const timerPct = comboTimer / COMBO_WINDOW;
    const timerBarW = barW * 0.4;
    const timerBarH = ps(6);
    const timerBarX = offX + barW / 2 - timerBarW / 2;
    const timerBarY = offY + ps(85);

    // Background
    ctx.fillStyle = 'rgba(255,215,0,0.2)';
    ctx.fillRect(timerBarX, timerBarY, timerBarW, timerBarH);

    // Fill (shrinks as timer expires)
    ctx.fillStyle = GOLD;
    ctx.globalAlpha = 0.8;
    ctx.fillRect(timerBarX, timerBarY, timerBarW * timerPct, timerBarH);
    ctx.globalAlpha = 1;

    // Combo count text
    ctx.font = `bold ${ps(20)}px 'Oswald', sans-serif`;
    ctx.fillStyle = GOLD;
    ctx.textAlign = 'center';
    ctx.fillText(
      'COMBO x' + comboChain + ' (' + comboMultiplier + 'X)',
      offX + barW / 2,
      timerBarY + timerBarH + ps(18)
    );
  }

  // Score multiplier indicator (when > 1x)
  if (scoreMultiplier > 1) {
    ctx.font = `bold ${ps(20)}px 'Oswald', sans-serif`;
    ctx.fillStyle = '#FF6600';
    ctx.textAlign = 'left';
    ctx.fillText(scoreMultiplier + 'X MULT', offX + ps(15), offY + ps(95));
  }
}
```


### 7. SPEED CLAMPING — beforeUpdate handler

```javascript
// ═══════════════════════════════════════════════════════════════
// SPEED CLAMPING — Prevents ball tunneling through thin walls
// Runs every physics frame via beforeUpdate event.
// Also handles flipper impulse and layer transitions.
// ═══════════════════════════════════════════════════════════════

const MAX_BALL_SPEED = 30;  // maximum velocity magnitude
// For a 2432px-tall table, 30 is a good cap:
// - Ball radius is 36px, walls are 12px thick
// - At 30 vel and 3 substeps, ball moves ~10px per substep
// - Well within the 12px wall thickness

function createEvents() {
  // --- COLLISION START ---
  Events.on(engine, 'collisionStart', function(event) {
    event.pairs.forEach(pair => {
      let bodyA = pair.bodyA, bodyB = pair.bodyB;

      // Normalize: bodyB should always be the ball
      if (bodyA.label === 'pinball' || bodyA.label === 'multiball') {
        const tmp = bodyA; bodyA = bodyB; bodyB = tmp;
      }
      if (bodyB.label !== 'pinball' && bodyB.label !== 'multiball') return;

      switch (bodyA.label) {
        case 'drain':
          if (bodyB.label === 'multiball') {
            drainMultiball(bodyB);
          } else {
            handleDrain();
          }
          break;
        case 'bumper':
          pingBumper(bodyA, bodyB);
          break;
        case 'slingshot':
          pingSlingshot(bodyA, bodyB);
          break;
      }
    });
  });

  // --- BEFORE UPDATE (every physics step) ---
  Events.on(engine, 'beforeUpdate', function() {
    // 1. Update flippers
    updateFlippers();

    // 2. Check layer transitions
    checkLayerTransitions();

    // 3. Speed clamping on ALL balls
    clampAllBallSpeeds();

    // 4. Safety: drain main ball if it escapes bounds
    if (pinball && !pinball.isStatic && gameState === 'play') {
      const bx = pinball.position.x, by = pinball.position.y;
      if (bx < -50 || bx > IMG_W + 50 || by < -100 || by > IMG_H + 100) {
        handleDrain();
      }
    }

    // 5. Check multiball drains
    checkMultiballDrains();
  });

  // --- KEYBOARD ---
  document.addEventListener('keydown', function(e) {
    if (audioCtx.state === 'suspended') audioCtx.resume();

    // Flippers: Left = Z, Left Arrow, Left Shift
    if (e.code === 'ArrowLeft' || e.code === 'KeyZ' || e.code === 'ShiftLeft') {
      isLeftPaddleUp = true;
      if (gameState === 'play' || gameState === 'launch') sndFlipper();
    }
    // Flippers: Right = M, Right Arrow, Right Shift
    if (e.code === 'ArrowRight' || e.code === 'KeyM' || e.code === 'ShiftRight') {
      isRightPaddleUp = true;
      if (gameState === 'play' || gameState === 'launch') sndFlipper();
    }
    // Plunger: Space
    if (e.code === 'Space') {
      e.preventDefault();
      if (gameState === 'attract') startGame();
      else if (gameState === 'gameover') {
        gameState = 'attract'; particles = []; attractTimer = 0;
      }
      else if (gameState === 'launch') plungerCharging = true;
    }
    // Debug: Shift+D
    // (already handled in separate keydown listener)
  });

  document.addEventListener('keyup', function(e) {
    if (e.code === 'ArrowLeft' || e.code === 'KeyZ' || e.code === 'ShiftLeft') {
      isLeftPaddleUp = false;
    }
    if (e.code === 'ArrowRight' || e.code === 'KeyM' || e.code === 'ShiftRight') {
      isRightPaddleUp = false;
    }
    if (e.code === 'Space') {
      if (plungerCharging && gameState === 'launch') firePinball();
      plungerCharging = false;
    }
  });

  // --- TOUCH (mobile) ---
  canvas.addEventListener('touchstart', function(e) {
    e.preventDefault();
    if (audioCtx.state === 'suspended') audioCtx.resume();
    for (const touch of e.changedTouches) {
      if (gameState === 'attract') { startGame(); return; }
      if (gameState === 'gameover') {
        gameState = 'attract'; particles = []; attractTimer = 0; return;
      }
      if (touch.clientX < canvas.width / 2) {
        isLeftPaddleUp = true; sndFlipper();
      } else {
        isRightPaddleUp = true; sndFlipper();
      }
      if (gameState === 'launch') plungerCharging = true;
    }
  }, { passive: false });

  canvas.addEventListener('touchend', function(e) {
    e.preventDefault();
    for (const touch of e.changedTouches) {
      if (touch.clientX < canvas.width / 2) isLeftPaddleUp = false;
      else isRightPaddleUp = false;
      if (plungerCharging && gameState === 'launch') firePinball();
      plungerCharging = false;
    }
  }, { passive: false });
}

// --- BALL SAVE ---
function handleDrain() {
  if (gameState !== 'play') return;

  // Ball save: return ball to launcher
  if (ballSaveTimer > 0) {
    Body.setStatic(pinball, true);
    Body.setPosition(pinball, { x: LAUNCHER_X, y: LAUNCHER_START_Y });
    Body.setVelocity(pinball, { x: 0, y: 0 });
    Body.setStatic(pinball, false);
    Body.setVelocity(pinball, { x: 0, y: -20 }); // auto-relaunch
    setBallLayer('launcher');
    showMessage('BALL SAVED!');
    ballSaveTimer = 0; // one save per launch
    return;
  }

  gameState = 'drain';
  drainTimer = 90;  // ~1.5s pause before next ball
  emitParticles(pinball.position.x, pinball.position.y, RED, 30, 8);
  shake = 10;
  sndDrain();

  // Hide main ball
  Body.setStatic(pinball, true);
  Body.setPosition(pinball, { x: -200, y: -200 });
  Body.setVelocity(pinball, { x: 0, y: 0 });

  // Clean up remaining multiballs
  multiballs.forEach(mb => World.remove(world, mb));
  multiballs = [];
  isMultiball = false;
}

function startGame() {
  score = 0;
  ballNum = 1;
  totalBalls = 3;
  scoreMultiplier = 1;
  comboChain = 0;
  comboTimer = 0;
  comboMultiplier = 1;
  endOfBallBonus = 0;
  rampCompletions = 0;
  totalBumperHits = 0;
  bumperHitCount = [0, 0, 0, 0];
  bumperFlash = [0, 0, 0, 0];
  slingFlash = [0, 0];
  trail = [];
  particles = [];
  isMultiball = false;
  multiballs.forEach(mb => World.remove(world, mb));
  multiballs = [];
  ballSaveTimer = 0;
  launchPinball();
}
```


### INTEGRATION CHECKLIST

To integrate all mechanics into `index.html`:

1. **Add** `createSlingshots()` call in `init()` after bumper creation
2. **Replace** `pingBumper()` with enhanced version
3. **Replace** `launchPinball()` and `firePinball()` with plunger versions
4. **Replace** `triggerMultiball()` with enhanced version
5. **Replace** `gameLoop()` and initialization block (remove Runner)
6. **Add** scoring engine variables and functions
7. **Replace** `createEvents()` with the unified version
8. **Replace** `handleDrain()` and `startGame()` with enhanced versions
9. **Add** `renderSlingFlash()` call in `renderFrame()` after `renderBumperFlash()`
10. **Add** `renderComboIndicator()` call in `renderScoreOverlay()`
11. **Update** `checkLayerTransitions()` to call `onRampComplete()` when ball exits a ramp

### Layer transition integration for ramp scoring:

```javascript
// In checkLayerTransitions(), when ball transitions back to playfield from a ramp:
if (ballLayer === t.from && dirMatch) {
  if (t.to === 'moda') {
    triggerMultiball();
    setBallLayer('right_ramp');
    Body.setVelocity(pinball, { x: 2, y: -15 });
  } else {
    // Track ramp completions when exiting a ramp
    if (t.from === 'left_ramp' && t.to === 'playfield') {
      onRampComplete('left_ramp');
    } else if (t.from === 'right_ramp' && t.to === 'playfield') {
      onRampComplete('right_ramp');
    }
    setBallLayer(t.to);
  }
}
```
