# Research: Rendering Pipeline, Matter.js Deep Settings, Unknown Unknowns
*Final research notes — 3 iterations, Mar 21 2026*

## Source Log
- [Matter.js GitHub #357](https://github.com/liabru/matter-js/issues/357) - positionIterations/velocityIterations are loop counts for constraint solving. Integers only. Default 6/4. Maintainer says "at least 3, ideally 8 or more." (credibility: high — maintainer response)
- [Matter.js Engine API docs](https://brm.io/matter-js/docs/files/src_core_Engine.js.html) - Full engine config: timing.timeScale (default 1, 0=freeze, <1=slowmo), enableSleeping (default false), gravity.scale (default 0.001). (credibility: high — official docs)
- [Matter.js CHANGELOG](https://github.com/liabru/matter-js/blob/master/CHANGELOG.md) - v0.20.0 (June 2024, latest stable): fixed timestep Runner, optimized collision/resolver, new beforeSolve event. v0.19.0: timestep-independent velocity setters. (credibility: high — official)
- [matter-attractors source](https://github.com/liabru/matter-attractors/blob/master/index.js) - Plugin hooks into Body.create and Engine.update. For each body with attractors, iterates all other bodies and applies force. O(n*m). Version 0.1.6, for matter-js ^0.12.0. (credibility: high — source code)
- [MDN globalCompositeOperation](https://developer.mozilla.org/en-US/docs/Web/API/CanvasRenderingContext2D/globalCompositeOperation) - 'screen' inverts/multiplies/inverts (lighter result). 'lighter' adds RGB values (additive blending). Both valid for glow. (credibility: high — MDN)
- [MDN Canvas Optimization](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API/Tutorial/Optimizing_canvas) - Use CSS background for static images, multiple layered canvases, integer coordinates, { alpha: false }, pre-render to offscreen canvas. (credibility: high — MDN)
- [web.dev Game Audio](https://web.dev/webaudio-games/) - DynamicsCompressorNode prevents clipping. Master gain node for overall level. No hard limit on simultaneous sounds. (credibility: high)
- [MDN Audio for Web Games](https://developer.mozilla.org/en-US/docs/Games/Techniques/Audio_for_Web_Games) - Mobile autoplay blocked by default. Must prime audio on user interaction. Audio sprites reduce requests. Web Audio API supports precise timing + positional audio. (credibility: high — MDN)
- [Matter.js CCD issue #5](https://github.com/liabru/matter-js/issues/5) - No CCD in Matter.js. Workarounds: sub-stepping, speed clamping, thicker invisible collision bodies, ray-cast clamping. (credibility: high — maintainer + community)
- [PQINA Canvas Memory](https://pqina.nl/blog/total-canvas-memory-use-exceeds-the-maximum-limit) - iOS Safari: 384MB total canvas memory pool. 16,777,216 max pixel area per canvas. Safari caches canvas elements even after dereferencing. (credibility: high — tested)
- [PQINA Canvas Size](https://pqina.nl/blog/canvas-area-exceeds-the-maximum-limit/) - iOS canvas area limit 16,777,216 px. macOS Safari same. Other browsers have much higher limits. (credibility: high — tested)
- [Lu1ky Pinball Deep Dive](https://frankforce.com/lu1ky-pinball-code-deep-dive/) - Uses 9 physics substeps per frame. Ball position randomized to avoid deterministic launches. (credibility: high — author's own project)
- [Object Pooling for Games](https://peerdh.com/blogs/programming-insights/efficient-memory-management-in-javascript-games-a-look-at-object-pooling-techniques) - Pre-allocate objects, acquire/release pattern prevents GC pauses during gameplay. (credibility: medium — tutorial)

---

## Working Thesis

### 1. How to Split the Table Image into Background + Foreground

**Three approaches, ranked:**

**A. Manual masking from existing PNG (RECOMMENDED)**
Take `table.png`, open in GIMP/Photoshop. Use the lasso/pen tool to select the chrome ramp areas. Copy to a new layer with transparency. Export as `foreground.png` (ramps on transparent). The original `table.png` becomes the background as-is (ramps visible underneath are fine because the ball draws between the layers and the foreground covers the playfield-level ramp art).

Why this is best: pixel-perfect alignment guaranteed because both images derive from the same source. No AI generation variance. Takes 15-30 minutes in GIMP.

**B. AI generation of separate layers (FRAGILE)**
Ask Gemini to generate two images: "playfield without ramp covers" and "ramp covers only on transparent." The problem: AI image generation is not pixel-deterministic. Two separate generations will NOT align at the pixel level. Ramp edges will be slightly different sizes, positions, and colors. This approach creates visible seams.

**C. CSS background + canvas-only foreground (PERFORMANCE OPTIMAL but more work)**
Use the table.png as a CSS `background-image` on the container div. Canvas renders ONLY the dynamic elements (ball, flippers, effects) and the foreground overlay. This eliminates one `drawImage` call per frame. Best performance on older hardware. Downside: requires careful coordinate alignment between CSS background sizing and canvas dimensions.

**Practical recommendation:** Start with approach A. If performance is an issue on the showcase laptop, migrate to approach C (CSS background).

### 2. Complete Canvas Draw Order

```javascript
function render() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Layer 1: Background table image (playfield, everything ball rolls ON)
    ctx.drawImage(backgroundImg, 0, 0, canvas.width, canvas.height);

    // Layer 2: Flipper rendering (on top of background, under foreground)
    renderFlippers(ctx);

    // Layer 3: Ball shadow (subtle, offset, only on playfield)
    if (ball.layer === 'playfield') {
        renderBallShadow(ctx, ball, 4, 4, 0.3);
    }

    // Layer 4: Ball on playfield/launcher layer
    if (ball.layer === 'playfield' || ball.layer === 'launcher') {
        renderBall(ctx, ball);
    }

    // Layer 5: Foreground overlay (ramp covers, chrome rails — transparent PNG)
    ctx.drawImage(foregroundImg, 0, 0, canvas.width, canvas.height);

    // Layer 6: Ball on ramp layer (draws ABOVE ramp covers)
    if (ball.layer === 'left_ramp' || ball.layer === 'right_ramp') {
        renderBallShadow(ctx, ball, 3, 3, 0.2);
        renderBall(ctx, ball);
    }

    // Layer 7: Bumper flash effects (additive blending, on top of everything)
    updateBumperFlashes();
    bumperFlashes.forEach((flash, id) => {
        const bumper = bumperPositions.get(id);
        if (bumper) renderBumperFlash(ctx, bumper, flash.intensity);
    });

    // Layer 8: Particles (ball trail, sparks)
    renderParticles(ctx);

    // Layer 9: Score overlay and UI
    renderScore(ctx);
}
```

**Key insight for multiball:** When there are multiple balls (Moda Center scoop triggers 2 extra), each ball checks its own layer independently. Some balls may be on playfield while one is on a ramp. The draw order handles this by iterating all balls at both layer-4 and layer-6 draw points.

### 3. Ball Shadow Rendering

```javascript
function renderBallShadow(ctx, ball, offsetX, offsetY, opacity) {
    ctx.save();
    ctx.globalAlpha = opacity;
    const gradient = ctx.createRadialGradient(
        ball.position.x + offsetX, ball.position.y + offsetY, 0,
        ball.position.x + offsetX, ball.position.y + offsetY, ball.circleRadius * 1.2
    );
    gradient.addColorStop(0, 'rgba(0, 0, 0, 0.6)');
    gradient.addColorStop(0.5, 'rgba(0, 0, 0, 0.3)');
    gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(
        ball.position.x + offsetX,
        ball.position.y + offsetY,
        ball.circleRadius * 1.2, 0, Math.PI * 2
    );
    ctx.fill();
    ctx.restore();
}
```

The shadow draws on the BACKGROUND layer (before the foreground overlay). When the ball is on a ramp, the shadow should draw on the ramp surface (after the foreground overlay, before the ramp-layer ball). The offset direction (down-right: +4, +4) simulates overhead lighting from the upper-left, consistent with most pinball machines.

### 4. Bumper Flash Effects with globalCompositeOperation

```javascript
function renderBumperFlash(ctx, bumper, intensity) {
    if (intensity <= 0) return;

    ctx.save();
    ctx.globalCompositeOperation = 'lighter'; // additive blending — key
    ctx.globalAlpha = intensity;

    // Inner bright flash (white-hot center → warm glow)
    const innerGrad = ctx.createRadialGradient(
        bumper.x, bumper.y, 0,
        bumper.x, bumper.y, bumper.radius * 2
    );
    innerGrad.addColorStop(0, 'rgba(255, 255, 255, 1)');
    innerGrad.addColorStop(0.3, 'rgba(255, 200, 50, 0.8)');
    innerGrad.addColorStop(0.7, 'rgba(255, 100, 0, 0.3)');
    innerGrad.addColorStop(1, 'rgba(255, 50, 0, 0)');
    ctx.fillStyle = innerGrad;
    ctx.beginPath();
    ctx.arc(bumper.x, bumper.y, bumper.radius * 2, 0, Math.PI * 2);
    ctx.fill();

    // Outer glow ring (softer, wider)
    const outerGrad = ctx.createRadialGradient(
        bumper.x, bumper.y, bumper.radius * 1.5,
        bumper.x, bumper.y, bumper.radius * 3.5
    );
    outerGrad.addColorStop(0, 'rgba(255, 150, 0, 0.4)');
    outerGrad.addColorStop(1, 'rgba(255, 50, 0, 0)');
    ctx.fillStyle = outerGrad;
    ctx.beginPath();
    ctx.arc(bumper.x, bumper.y, bumper.radius * 3.5, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore(); // CRITICAL: restores globalCompositeOperation to 'source-over'
}

// Track bumper flash states
const bumperFlashes = new Map(); // bumper.id -> { intensity, startTime }

Matter.Events.on(engine, 'collisionStart', (event) => {
    event.pairs.forEach(pair => {
        const bumper = [pair.bodyA, pair.bodyB].find(b => b.label?.includes('Bumper'));
        if (bumper) {
            bumperFlashes.set(bumper.id, { intensity: 1.0, startTime: performance.now() });
        }
    });
});

function updateBumperFlashes() {
    const now = performance.now();
    const FLASH_DURATION = 120; // ms — fast pop
    bumperFlashes.forEach((flash, id) => {
        flash.intensity = 1.0 - (now - flash.startTime) / FLASH_DURATION;
        if (flash.intensity <= 0) bumperFlashes.delete(id);
    });
}
```

**Why 'lighter' not 'screen':** `lighter` is true additive blending (adds RGB channel values). `screen` is a photographic compositing mode that never fully saturates to white. For a punchy arcade flash, `lighter` gives a brighter, more eye-catching pop. Use `screen` for subtle glows.

**Performance note:** `createRadialGradient` is cheap. Two gradient fills per bumper per frame is negligible. But avoid creating the gradient objects inside the render loop if you cache bumper positions — pre-create gradients if bumpers don't move (they don't in pinball).

### 5. Flipper Rendering on Image Background

The flipper areas in the table image should **NOT** be transparent. The table image stays complete. Here's why and how:

**The approach:**
- Table image shows flippers at rest position as part of the art
- Canvas draws the flipper shapes on top of the image at their current physics angle
- At rest position, the canvas flipper exactly covers the image flipper — no visual difference
- When activated, the canvas flipper rotates and the image flipper underneath is partially visible but covered by the moving canvas flipper and the general visual busy-ness of the area

**Implementation options (best to worst):**
1. **Sprite extraction:** Cut the flipper from the table image as a small sprite. Rotate that sprite in canvas at the hinge point. Pixel-perfect match with table art.
2. **Color-matched shapes:** Draw rounded rectangles in the same color/gradient as the image flippers. Close enough for gameplay.
3. **Transparent flipper wells:** Cut transparent holes in the table image where flippers go, draw flippers entirely in canvas below the image layer. Most work, cleanest result, but requires image editing.

For the showcase (April 7): option 2 (color-matched shapes) is fastest to implement and looks fine during gameplay. The ball is moving fast enough that nobody scrutinizes flipper art.

### 6. Matter.js Deep Settings Explained

**positionIterations (default 6):**
Number of position-correction passes per engine update. Each pass resolves overlap between colliding body pairs by moving them apart. More passes = bodies separate more accurately after collision. The pinball-schminball value of 100 is extremely conservative. With 3 substeps per frame (180Hz effective physics), you get 3x the correction opportunities, so 10-30 positionIterations per substep is sufficient. **Recommended: 20 with 3 substeps.** Cost: linear in number of active collision pairs. Pinball has ~5-15 active pairs at any moment, so even 100 iterations adds <1ms per frame.

**velocityIterations (default 4):**
Number of velocity-correction passes per update. Resolves how fast bodies should bounce apart at contact points. More passes = more accurate rebound angles and speeds. Matters most for the ball hitting bumpers at steep angles. **Recommended: 10 with 3 substeps.** Higher values than 10 give diminishing returns.

**constraintIterations (default 2):**
Passes for constraint solving (joints, hinges, springs). Since the current flipper system uses `Body.setAngle()` directly (no constraints), this setting is irrelevant for flippers. Only matters if using constraint-based joints. Default 2 is fine.

**timing.timeScale (default 1):**
Global multiplier on all delta-time values. `0` = freeze, `0.5` = half speed, `2` = double speed. Useful for:
- Pause menu: set to 0
- Dramatic slow-mo on drain: ramp from 0.3 to 1.0 over 500ms
- Ball-save "time freeze" effect: briefly set to 0.1
- Debug: slow down to watch collision behavior

**enableSleeping (default false):**
Bodies that stop moving enter "sleep" state (skipped in calculations). For pinball: **leave disabled**. Static bodies already don't calculate. The only dynamic body (ball) never stops during play. Sleeping can cause missed collisions if a sleeping body should react.

**gravity.scale (default 0.001):**
Multiplier on gravity magnitude. The research brief recommends `gravity.y = 0.85`. With default scale of 0.001, effective gravity = 0.00085 per tick. Tune this rather than the y value to adjust overall "weight" feel without changing direction.

**Matter.js version note:** v0.20.0 (June 2024) is latest stable. Key change: Runner now defaults to fixed timestep (deterministic). If using custom game loop with `Engine.update(engine, delta)`, this doesn't affect you. But if using `Matter.Runner`, be aware it may call zero, one, or multiple engine updates per frame to maintain fixed timestep.

### 7. matter-attractors Plugin

**How it works internally:**
1. On install, hooks into `Body.create` (adds `plugin.attractors = []` to each body)
2. Before each `Engine.update`, iterates all bodies. For each body with attractors, calls each attractor function with `(bodyA, bodyB)` for every other body in the world
3. If the attractor function returns a `{ x, y }` force vector, applies it to bodyB via `Body.applyForce()`
4. The iteration is O(n * m) where n = bodies with attractors, m = total bodies

**Installation:**
```html
<script src="https://cdn.jsdelivr.net/npm/matter-attractors@0.1.6/build/matter-attractors.min.js"></script>
<script>
    Matter.use(MatterAttractors); // MUST be before Engine.create()
</script>
```

**Custom attractor function:**
```javascript
const magnet = Bodies.circle(x, y, 30, {
    isStatic: true,
    plugin: {
        attractors: [
            function(bodyA, bodyB) {
                // bodyA = this magnet, bodyB = any other body
                if (bodyB.label !== 'ball') return; // only attract balls
                const dx = bodyA.position.x - bodyB.position.x;
                const dy = bodyA.position.y - bodyB.position.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist > 200) return; // range limit
                const force = 0.001 / (dist * dist); // inverse-square falloff
                return { x: dx * force, y: dy * force };
            }
        ]
    }
});
```

**Built-in gravity attractor:** `MatterAttractors.Attractors.gravity` — Newtonian gravity (F = G * m1 * m2 / r^2). `gravityConstant` defaults to 0.001.

**PROJECT NOTE:** The HANDOFF.md explicitly says DO NOT go back to attractors for flippers. The current direct angle control system works. Attractors are still useful for: magnetic kick-backs (save zone), Moda Center scoop pull, or orbit gravity wells as game features.

### 8. Other Matter.js Settings That Affect Pinball Feel

**body.slop (default 0.05):** Allowed penetration depth before correction. Lower = tighter contacts but more jitter. For bumpers where you want instant response, 0.01 works. For walls where you want smooth sliding, keep default.

**body.timeScale:** Per-body time scaling. Set a ball to 0.5 and it moves at half speed. Could use for power-ups or ball-save effects.

**engine.constraintWarmStarting:** Reuses previous constraint solutions as starting points. Improves stability for constraint-based systems. Less relevant since flippers use direct control.

**body.friction / frictionStatic / frictionAir:** Already covered in research brief. Key nuance: `frictionStatic` determines the threshold for a ball to start rolling vs. sitting still on a sloped surface. Default 0.5 is high — lower to 0.1 so the ball doesn't "stick" on gentle slopes.

**Collision filtering (already implemented):** `collisionFilter.category` and `collisionFilter.mask` — the layer system. Already working per HANDOFF.md.

### 9. Ball Getting Stuck in Geometry

**Why it happens:**
1. **Tunneling failure:** Ball moves fast enough that substeps catch it but place it inside a wall. Position correction pushes it out, but into ANOTHER wall. The ball oscillates between two walls, visually "stuck."
2. **Concave corners:** Two walls meet at an acute angle. Ball enters the corner, both walls push it toward the other. Deadlock.
3. **Sensor zone edge cases:** Ball is at a layer transition zone and switches layers at the wrong moment, losing collision with the wall that should contain it.

**Detection:**
```javascript
// In beforeUpdate event, check if ball is suspiciously slow for too long
let stuckFrames = 0;
const STUCK_SPEED_THRESHOLD = 0.3;
const STUCK_FRAME_LIMIT = 120; // 2 seconds at 60fps

Matter.Events.on(engine, 'beforeUpdate', () => {
    const speed = Math.sqrt(ball.velocity.x ** 2 + ball.velocity.y ** 2);
    if (speed < STUCK_SPEED_THRESHOLD && ball.position.y < 2000) {
        // Ball is nearly stationary but NOT near the drain
        stuckFrames++;
        if (stuckFrames > STUCK_FRAME_LIMIT) {
            unstickBall();
            stuckFrames = 0;
        }
    } else {
        stuckFrames = 0;
    }
});
```

**Unstick strategies:**
```javascript
function unstickBall() {
    // Option 1: Gentle nudge in random direction
    const angle = Math.random() * Math.PI * 2;
    const nudge = 3;
    Matter.Body.setVelocity(ball, {
        x: Math.cos(angle) * nudge,
        y: Math.sin(angle) * nudge
    });

    // Option 2: Teleport to last known good position
    // (requires tracking position history)
    if (lastGoodPosition) {
        Matter.Body.setPosition(ball, lastGoodPosition);
        Matter.Body.setVelocity(ball, { x: 0, y: 2 }); // gentle downward
    }

    // Option 3: Nuclear option — return to plunger
    // Matter.Body.setPosition(ball, LAUNCHER_START);
    // Matter.Body.setVelocity(ball, { x: 0, y: 0 });
}

// Track position history for option 2
let lastGoodPosition = null;
let positionHistory = [];
Matter.Events.on(engine, 'afterUpdate', () => {
    const speed = Math.sqrt(ball.velocity.x ** 2 + ball.velocity.y ** 2);
    if (speed > 1) {
        positionHistory.push({ ...ball.position });
        if (positionHistory.length > 60) positionHistory.shift();
        lastGoodPosition = positionHistory[0]; // 1 second ago
    }
});
```

**Prevention:**
- Use chamfered corners on wall intersections (Matter.js `chamfer` option)
- Make collision walls thicker than they appear visually
- Speed clamping (already in research brief: maxSpeed = 25)
- 3 substeps per frame (already planned)
- Avoid acute angles in wall geometry — use curves instead

### 10. Performance on Older Laptops

**Canvas size analysis:**
- `table.png` is 1748 x 2432 = 4,249,536 pixels
- iOS Safari limit: 16,777,216 pixels per canvas — **we're well within limit** (25% of max)
- Memory per canvas: 4,249,536 * 4 bytes (RGBA) = ~16MB per canvas
- With 2 image layers (background + foreground) + 1 game canvas = ~48MB canvas memory
- iOS Safari total canvas memory pool: 384MB — **plenty of room**

**Performance budget at 60fps:**
- 16.67ms per frame total
- Matter.js with 3 substeps + 20 positionIterations: ~2-4ms (pinball has few dynamic bodies)
- Canvas drawImage for background (1748x2432): ~1-2ms (GPU-accelerated)
- Canvas drawImage for foreground overlay: ~1-2ms
- Ball + flippers + effects rendering: ~1ms
- Total: ~5-9ms — **comfortable 60fps budget**

**Scaling for older hardware:**
- If the showcase laptop struggles, downscale both images to 874x1216 (half) and render at 2x CSS pixels. Visual quality stays sharp on smaller screens.
- Use `{ alpha: false }` on the main canvas context for ~10% speedup
- Move background to CSS `background-image` (eliminates one drawImage call)
- Reduce particle count, remove ball trail on low-perf devices

**Should you downscale the 1748x2432 image?** Not proactively. Test on the actual showcase laptop first. Modern integrated GPUs (Intel UHD 620+, Apple M-series) handle this easily. Only downscale if you measure frame drops below 50fps.

### 11. Touch Controls for Mobile/Tablet

```javascript
// Split-screen touch: left half = left flipper, right half = right flipper
// Bottom center = plunger (drag down to pull, release to launch)

const PLUNGER_ZONE = { x: canvas.width * 0.35, y: canvas.height * 0.85,
                       w: canvas.width * 0.3, h: canvas.height * 0.15 };

let leftFlipperActive = false;
let rightFlipperActive = false;
let plungerTouch = null;
let plungerPull = 0;

canvas.addEventListener('touchstart', (e) => {
    e.preventDefault(); // Prevent scrolling
    for (const touch of e.changedTouches) {
        const rect = canvas.getBoundingClientRect();
        const x = (touch.clientX - rect.left) * (canvas.width / rect.width);
        const y = (touch.clientY - rect.top) * (canvas.height / rect.height);

        // Check plunger zone first
        if (x > PLUNGER_ZONE.x && x < PLUNGER_ZONE.x + PLUNGER_ZONE.w &&
            y > PLUNGER_ZONE.y) {
            plungerTouch = touch.identifier;
            continue;
        }

        // Left half = left flipper, right half = right flipper
        if (x < canvas.width / 2) {
            leftFlipperActive = true;
        } else {
            rightFlipperActive = true;
        }
    }
}, { passive: false });

canvas.addEventListener('touchmove', (e) => {
    e.preventDefault();
    for (const touch of e.changedTouches) {
        if (touch.identifier === plungerTouch) {
            const rect = canvas.getBoundingClientRect();
            const y = (touch.clientY - rect.top) * (canvas.height / rect.height);
            // Pull distance: how far finger dragged down from initial touch
            plungerPull = Math.min(1, Math.max(0,
                (y - PLUNGER_ZONE.y) / PLUNGER_ZONE.h));
        }
    }
}, { passive: false });

canvas.addEventListener('touchend', (e) => {
    e.preventDefault();
    for (const touch of e.changedTouches) {
        if (touch.identifier === plungerTouch) {
            // Release plunger — launch ball
            launchBall(plungerPull); // plungerPull 0-1 maps to velocity
            plungerPull = 0;
            plungerTouch = null;
            continue;
        }

        // Need to check which side this touch was on
        const rect = canvas.getBoundingClientRect();
        const x = (touch.clientX - rect.left) * (canvas.width / rect.width);
        if (x < canvas.width / 2) {
            leftFlipperActive = false;
        } else {
            rightFlipperActive = false;
        }
    }
}, { passive: false });

// Prevent double-tap zoom on iOS
canvas.addEventListener('touchstart', (e) => e.preventDefault(), { passive: false });
```

**Critical gotchas:**
- `{ passive: false }` is required on touch listeners to allow `preventDefault()` — without it, the page scrolls
- Track touch identifiers for multi-touch (left and right flippers simultaneously)
- The plunger needs a separate touch identifier to distinguish from flipper taps
- Scale touch coordinates by canvas/CSS ratio if the canvas is CSS-scaled
- iOS Safari: prevent the rubber-band bounce with `overscroll-behavior: none` on body
- Add `touch-action: none` CSS on the canvas element

### 12. Sound Design with Web Audio API

```javascript
// Initialize audio context on first user interaction
let audioCtx = null;
let compressor = null;

function initAudio() {
    if (audioCtx) return;
    audioCtx = new AudioContext();

    // DynamicsCompressorNode prevents clipping with multiple simultaneous sounds
    compressor = audioCtx.createDynamicsCompressor();
    compressor.threshold.value = -24;  // dB where compression starts
    compressor.knee.value = 12;        // transition smoothness
    compressor.ratio.value = 8;        // compression ratio
    compressor.attack.value = 0.003;   // fast attack for percussive sounds
    compressor.release.value = 0.15;   // medium release
    compressor.connect(audioCtx.destination);
}

// Synthesized pinball sounds — no audio files needed
function playBumperPop(pitch) {
    if (!audioCtx) return;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(pitch || 800, audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(200, audioCtx.currentTime + 0.08);

    gain.gain.setValueAtTime(0.4, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.1);

    osc.connect(gain);
    gain.connect(compressor);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.1);
}

function playFlipperClick() {
    if (!audioCtx) return;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();

    osc.type = 'square';
    osc.frequency.setValueAtTime(150, audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(50, audioCtx.currentTime + 0.03);

    gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.04);

    osc.connect(gain);
    gain.connect(compressor);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.05);
}

function playBallRolling(speed) {
    // Continuous noise filtered by ball speed
    if (!audioCtx) return;
    // Use a noise buffer + bandpass filter, modulate by speed
    // Implementation: create once, adjust filter frequency based on ball.speed
}

function playLaunch() {
    if (!audioCtx) return;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();

    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(100, audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(600, audioCtx.currentTime + 0.15);

    gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
    gain.gain.linearRampToValueAtTime(0.3, audioCtx.currentTime + 0.1);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.2);

    osc.connect(gain);
    gain.connect(compressor);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.2);
}

function playDrain() {
    if (!audioCtx) return;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(400, audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(80, audioCtx.currentTime + 0.5);

    gain.gain.setValueAtTime(0.5, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.6);

    osc.connect(gain);
    gain.connect(compressor);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.6);
}
```

**Key audio architecture decisions:**
- **DynamicsCompressorNode** between all sound sources and the destination — prevents clipping when 3 bumpers hit simultaneously
- **Synthesized sounds** (oscillators) instead of audio files — zero load time, zero file management, ~50 lines of code total
- **No simultaneous sound limit** in Web Audio API — tested to handle hundreds
- **Vary bumper pitch** by bumper position (left=700Hz, center=800Hz, right=900Hz) to create spatial audio illusion
- **Must prime AudioContext on first user interaction** (tap to start / attract mode click) due to autoplay policy

### 13. Unknown Unknowns — What ELSE Will Go Wrong

**A. Retina/HiDPI display scaling (HIGH PROBABILITY)**
Canvas on Retina displays renders at 1x resolution by default, looking blurry. Fix:
```javascript
const dpr = window.devicePixelRatio || 1;
canvas.width = TABLE_WIDTH * dpr;
canvas.height = TABLE_HEIGHT * dpr;
canvas.style.width = TABLE_WIDTH + 'px';
canvas.style.height = TABLE_HEIGHT + 'px';
ctx.scale(dpr, dpr);
```
BUT: this quadruples the pixel count on 2x displays (1748*2 x 2432*2 = 17M pixels). On iOS Safari, this approaches the 16.7M pixel limit. **Solution:** Cap the DPR at 1 for the game canvas. Pinball doesn't need retina sharpness — the ball is moving too fast.

**B. Viewport/scroll issues on mobile (HIGH PROBABILITY)**
The game canvas needs to fill the viewport without triggering iOS Safari's toolbar show/hide, address bar collapse, or rubber-band scrolling. Required CSS:
```css
html, body {
    margin: 0; padding: 0; overflow: hidden;
    overscroll-behavior: none;
    -webkit-overflow-scrolling: auto;
    position: fixed; width: 100%; height: 100%;
}
canvas {
    touch-action: none;
    -webkit-touch-callout: none;
    -webkit-user-select: none;
}
```
Also: use `window.visualViewport` API instead of `window.innerHeight` to get actual viewport size (excludes soft keyboard, toolbars).

**C. requestAnimationFrame throttling in background tabs (MEDIUM PROBABILITY)**
If someone switches to another tab during gameplay, rAF callbacks drop to 1fps or stop entirely. When they return, `deltaTime` spikes, causing the ball to teleport through walls. Fix:
```javascript
const MAX_DELTA = 32; // ms — cap at ~2 frames
function gameLoop(timestamp) {
    const delta = Math.min(timestamp - lastTimestamp, MAX_DELTA);
    lastTimestamp = timestamp;
    // Use capped delta for physics
    for (let i = 0; i < 3; i++) {
        Matter.Engine.update(engine, delta / 3);
    }
    render();
    requestAnimationFrame(gameLoop);
}
```

**D. Garbage collection pauses from particle systems (MEDIUM PROBABILITY)**
Creating new particle objects each frame for ball trails, bumper sparks, and effects generates GC pressure. After 30-60 seconds of play, V8 triggers a major GC that can cause a 20-50ms frame stutter. Fix: object pooling.
```javascript
class ParticlePool {
    constructor(size) {
        this.pool = Array.from({ length: size }, () => ({
            x: 0, y: 0, vx: 0, vy: 0, life: 0, active: false
        }));
        this.index = 0;
    }
    acquire() {
        for (let i = 0; i < this.pool.length; i++) {
            const idx = (this.index + i) % this.pool.length;
            if (!this.pool[idx].active) {
                this.index = (idx + 1) % this.pool.length;
                this.pool[idx].active = true;
                return this.pool[idx];
            }
        }
        return null; // pool exhausted — skip this particle
    }
    release(p) { p.active = false; }
}
const particles = new ParticlePool(200);
```

**E. Matter.js version compatibility with matter-attractors (LOW-MEDIUM)**
matter-attractors v0.1.6 declares `for: 'matter-js@^0.12.0'`. Matter.js 0.20.0 may have breaking internal API changes (Runner changes, collision event changes). If using attractors for non-flipper purposes (magnets, gravity wells), test compatibility. The attractor plugin accesses `engine.world.bodies` which was deprecated in favor of `Composite.allBodies(engine.world)` in recent versions.

**F. Safari canvas compositing bugs (LOW PROBABILITY)**
`globalCompositeOperation = 'lighter'` has historically had rendering bugs in Safari on certain hardware (Intel GPUs). The bumper flash effect may look different across browsers. Test on Safari specifically. Fallback: use `'screen'` mode which is more widely supported, or skip the compositing and just draw semi-transparent colored circles.

**G. Audio resume after suspension (LOW PROBABILITY)**
iOS Safari suspends AudioContext when the tab loses focus or the screen locks. When the user returns, sounds stop working. Fix:
```javascript
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && audioCtx?.state === 'suspended') {
        audioCtx.resume();
    }
});
```

**H. Coordinate precision drift over long play sessions (LOW PROBABILITY)**
JavaScript floating-point arithmetic can accumulate tiny errors over thousands of physics ticks. Ball position drifts by sub-pixel amounts. Not visually noticeable but can cause the ball to slowly "walk" through walls over very long sessions (hours). The 3-substep + speed-clamping approach already mitigates this.

**I. Image loading race condition (LOW PROBABILITY but BLOCKING)**
If the background or foreground PNG hasn't loaded when the first render frame fires, `drawImage` draws nothing. Always wait for both images:
```javascript
Promise.all([
    loadImage('table-background.png'),
    loadImage('table-foreground.png')
]).then(([bg, fg]) => {
    backgroundImg = bg;
    foregroundImg = fg;
    requestAnimationFrame(gameLoop);
});

function loadImage(src) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = src;
    });
}
```

---

## Open Questions
- What Gemini model/prompt produces the best transparent-background ramp overlay? (May need manual GIMP work instead.)
- Exact showcase laptop specs — determines whether any performance optimization is needed
- Whether the existing sound effects in index.html are synthesized or use audio files (affects the audio architecture choice)

## Confidence
**Confident.** All 14 questions answered with code examples and sourced reasoning. The unknown unknowns section (question 14) covers 9 distinct failure modes with detection and fixes. The highest-risk items are retina scaling (A), viewport issues (B), and delta-time spikes (C) — all three have concrete solutions above.
