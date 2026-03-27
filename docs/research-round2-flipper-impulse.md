# Research Round 2: Flipper Momentum Transfer Without Attractors

## The Root Problem

Static bodies in Matter.js have zero velocity in the physics engine's eyes. When we call `Body.setAngle()` and `Body.setPosition()` (without `updateVelocity`), both the current position/angle AND the previous position/angle (`positionPrev`/`anglePrev`) are moved together. The collision resolver computes velocity as `position - positionPrev`, which yields zero. So the ball bounces off with restitution only -- no launch.

## The Key Discovery: How Matter.js Collision Resolution Actually Works

The collision resolver (`Resolver.solveVelocity`) does NOT use `body.velocity` or `body.angularVelocity`. It derives velocity from position/angle deltas:

```javascript
// From Resolver.js — computed for ALL bodies, including static
var bodyAVelocityX = bodyA.position.x - bodyA.positionPrev.x;
var bodyAVelocityY = bodyA.position.y - bodyA.positionPrev.y;
var bodyAAngularVelocity = bodyA.angle - bodyA.anglePrev;
```

The `isStatic` check only appears when APPLYING impulse (static bodies don't receive impulse), NOT when COMPUTING velocity. So if a static body has `position !== positionPrev` or `angle !== anglePrev`, the resolver WILL see that as velocity and use it in the impulse calculation for the dynamic body.

The impulse formula:
```javascript
var share = contactShare / (inverseMassTotal + bodyA.inverseInertia * oAcN^2 + bodyB.inverseInertia * oBcN^2);
var normalImpulse = (1 + pair.restitution) * normalVelocity * share;
```

When bodyA is static (`inverseMass=0`, `inverseInertia=0`), the denominator reduces to just the ball's resistance terms, and `normalVelocity` includes the flipper's computed velocity. The impulse is nonzero and applied to the ball. This is the mechanism we exploit.

---

## Source Log

- [Matter.js Resolver.js source](https://github.com/liabru/matter-js/blob/master/src/collision/Resolver.js) - Confirmed velocity derived from positionPrev, isStatic check only on impulse application (credibility: HIGH - primary source)
- [Matter.js Body.js source](https://github.com/liabru/matter-js/blob/master/src/body/Body.js) - setPosition/setAngle/rotate with updateVelocity parameter (credibility: HIGH - primary source)
- [Matter.js Engine.js source](https://github.com/liabru/matter-js/blob/master/src/core/Engine.js) - Static bodies skip _bodiesUpdate and _bodiesUpdateVelocities (credibility: HIGH - primary source)
- [Matter.js Body API docs](https://brm.io/matter-js/docs/classes/Body.html) - rotate(body, rotation, point, updateVelocity) (credibility: HIGH - official docs)
- [Phaser forum: flipper rotation](https://phaser.discourse.group/t/matter-physics-pinball-game-how-to-rotate-flippers/1718) - Community confirms momentum transfer problem with static flippers (credibility: MEDIUM)
- [pinball-schminball engine.ts](https://github.com/igorski/pinball-schminball/blob/master/src/model/physics/engine.ts) - Uses dynamic bodies + attractor forces, no manual impulse on collision (credibility: HIGH)
- [lonekorean pinball CodePen](https://codepen.io/lonekorean/pen/KXLrVX) - Canonical Matter.js pinball, uses attractor-stopper pattern (credibility: HIGH)
- [GameDev.net flipper physics](https://gamedev.net/forums/topic/570191-flipper-physics/4643293) - General physics formulas for flipper contact velocity (credibility: MEDIUM)

---

## Approach 1: Manual Impulse on Collision (Current Approach, Improved)

### How It Works
Keep static flippers. Detect collision in `collisionStart` or `beforeUpdate`. Calculate the flipper's angular velocity from the angle change between frames. Compute the tangential velocity at the contact point. Apply a proportional force to the ball.

### The Physics
For a flipper rotating around a hinge at angular velocity omega:
- Linear velocity at a point = omega x r (perpendicular to the radius)
- At distance `d` from hinge: `v_tangential = omega * d`
- Direction is perpendicular to the radius vector (hinge -> contact point)

```javascript
// Track previous angles for velocity computation
let prevLeftAngle = FLIP_REST;
let prevRightAngle = Math.PI - FLIP_REST;

function updateFlippers() {
  // ... existing angle interpolation code ...

  // Compute angular velocities (radians per frame)
  const leftOmega = leftFlipAngle - prevLeftAngle;   // negative when swinging up
  const rightOmega = (Math.PI - rightFlipAngle) - prevRightAngle;

  // Position flippers (no updateVelocity — keeps static behavior clean)
  positionFlipper(leftPaddle, LEFT_HINGE, leftFlipAngle);
  positionFlipper(rightPaddle, RIGHT_HINGE, Math.PI - rightFlipAngle);

  // Apply impulse to ball based on flipper motion
  if (pinball && !pinball.isStatic) {
    applyFlipperImpulse(leftPaddle, LEFT_HINGE, leftOmega);
    applyFlipperImpulse(rightPaddle, RIGHT_HINGE, rightOmega);
  }

  prevLeftAngle = leftFlipAngle;
  prevRightAngle = Math.PI - rightFlipAngle;
}

function applyFlipperImpulse(flipper, hinge, omega) {
  // Only apply when flipper is actually moving
  if (Math.abs(omega) < 0.001) return;

  const bx = pinball.position.x, by = pinball.position.y;
  const dx = bx - hinge.x, dy = by - hinge.y;
  const dist = Math.sqrt(dx * dx + dy * dy);

  // Only if ball is near the flipper
  if (dist > PADDLE_LEN * 1.2 || dist < 10) return;

  // Check if ball is roughly on the flipper (not just near the hinge)
  // Use dot product with flipper direction to verify
  const flipAngle = flipper.angle;
  const flipDirX = Math.cos(flipAngle), flipDirY = Math.sin(flipAngle);
  const dot = (dx * flipDirX + dy * flipDirY) / dist;
  if (dot < 0.3) return;  // ball is behind the hinge or too far off-axis

  // Tangential velocity at contact point: v = omega * r
  // Direction is perpendicular to radius vector (rotate 90 degrees)
  // For CCW rotation (omega < 0, swinging up): perpendicular is (-dy, dx) normalized
  const perpX = -dy / dist;
  const perpY = dx / dist;

  const tangentialSpeed = omega * dist;

  // Scale factor — tune this. Higher = more launch power.
  // The raw tangentialSpeed is in units of pixels/frame, which is small.
  // We need to convert to a force magnitude that feels right.
  const IMPULSE_SCALE = 0.15;

  const impulseX = perpX * tangentialSpeed * IMPULSE_SCALE;
  const impulseY = perpY * tangentialSpeed * IMPULSE_SCALE;

  Body.applyForce(pinball, pinball.position, { x: impulseX, y: impulseY });
}
```

### Assessment
- **Pros**: No changes to flipper body type. Simple to add.
- **Cons**: Force is applied in `beforeUpdate`, not during collision resolution. This means the ball gets pushed even if it's not colliding — just being near the flipper is enough. The proximity check (`dist < PADDLE_LEN * 1.2`) is a crude approximation of "colliding." The direction calculation is approximate. The ball can get double-hit (collision restitution bounce + manual force).
- **Feel**: Acceptable but not physical. Tuning IMPULSE_SCALE is trial-and-error. The force doesn't interact naturally with the collision — it's additive, so the ball can get weird trajectories (bounced one way by restitution, pushed another by the manual force).
- **Failure modes**: Ball near flipper but not touching gets launched. Ball touching flipper tip vs base gets same force direction (wrong — tip should launch more). Double-impulse from collision + manual force feels floaty.

### Verdict: **Workable but hacky. C+ feel.**

---

## Approach 2: Kinematic Body (Dynamic + setVelocity Each Frame)

### How It Works
Make flippers dynamic bodies. Each frame, compute where the flipper should be (same angle interpolation as now), then use `Body.setVelocity()` and `Body.setAngularVelocity()` to move it there. The physics engine sees real velocity on the body, so collision resolution naturally transfers momentum.

### The Problem
Matter.js doesn't have true kinematic bodies (like Box2D). A dynamic body with `setVelocity` still gets affected by gravity, collisions, and forces. The ball pushing against the flipper would push the flipper back. You'd need to constantly fight the physics engine to keep the flipper where you want it.

```javascript
function createPaddles() {
  leftPaddle = Bodies.rectangle(0, 0, PADDLE_LEN, PADDLE_WIDTH, {
    isStatic: false,       // dynamic!
    label: 'paddleLeft',
    chamfer: { radius: 8 },
    collisionFilter: { category: CAT.ALWAYS, mask: CAT.BALL },
    restitution: 0.8,
    render: { visible: false },
    inertia: Infinity,     // resist rotation from collisions
    mass: 1000,            // very heavy — ball can't push it
    frictionAir: 0,
    friction: 0
  });
  // ... same for right ...
  World.add(world, [leftPaddle, rightPaddle]);
}

function updateFlippers() {
  // Compute target positions same as before
  const leftTarget = isLeftPaddleUp ? FLIP_ACTIVE : FLIP_REST;
  // ... interpolation ...

  // Compute where flipper SHOULD be
  const targetAngle = leftFlipAngle;
  const halfLen = PADDLE_LEN / 2;
  const targetX = LEFT_HINGE.x + Math.cos(targetAngle) * halfLen;
  const targetY = LEFT_HINGE.y + Math.sin(targetAngle) * halfLen;

  // Set velocity to reach target position in one frame
  const velX = targetX - leftPaddle.position.x;
  const velY = targetY - leftPaddle.position.y;
  const angVel = targetAngle - leftPaddle.angle;

  Body.setVelocity(leftPaddle, { x: velX, y: velY });
  Body.setAngularVelocity(leftPaddle, angVel);

  // Also force position (in case drift accumulates)
  Body.setPosition(leftPaddle, { x: targetX, y: targetY });
  Body.setAngle(leftPaddle, targetAngle);
}
```

### Assessment
- **Pros**: The physics engine sees real velocity. Collision resolution works naturally.
- **Cons**: Fighting the engine every frame. Setting position AND velocity creates conflicts — position overrides what velocity would have done. Gravity pulls the flipper down (need `frictionAir: 0`, no gravity category, or disable gravity). The ball colliding with the flipper applies force back to it, potentially causing jitter even with high mass. `inertia: Infinity` prevents collision-induced rotation but also means `setAngularVelocity` won't work properly with the resolver (the resolver uses `inverseInertia` which would be 0).
- **Feel**: Potentially good if you can prevent drift and jitter. But `inertia: Infinity` zeroes out the angular velocity contribution in the resolver's impulse formula, which defeats the purpose.
- **Failure modes**: Flipper drifts from target position over time. Jitter when ball sits on flipper. Gravity pulls flipper down between setPosition calls. Setting both velocity and position in the same frame may confuse the Verlet integrator.

### Verdict: **Theoretically sound, practically unstable. B- feel with lots of babysitting. Not recommended.**

---

## Approach 3: updateVelocity=true on Static Bodies (THE WINNER)

### How It Works
Keep flippers as static bodies. Change ONE thing: pass `updateVelocity=true` to `Body.setAngle()` and `Body.setPosition()` (or better, use `Body.rotate()` with a point). This makes the engine set `positionPrev` and `anglePrev` to the OLD values before moving, so the resolver sees nonzero velocity and computes proper collision impulses.

### Why This Works (The Deep Cut)

1. `Body.setAngle(body, newAngle, true)` sets `anglePrev = body.angle` BEFORE updating, so `angle - anglePrev = deltaAngle` = angular velocity visible to resolver.
2. `Body.setPosition(body, newPos, true)` sets `positionPrev = body.position` BEFORE moving, so `position - positionPrev = delta` = linear velocity visible to resolver.
3. The resolver computes contact-point velocity INCLUDING angular contribution:
   ```javascript
   velocityPointAX = bodyAVelocityX - offsetAY * bodyAAngularVelocity
   velocityPointAY = bodyAVelocityY + offsetAX * bodyAAngularVelocity
   ```
4. This contact-point velocity feeds into `normalVelocity`, which feeds into `normalImpulse`, which gets applied to the ball.
5. Static bodies skip `_bodiesUpdate` and `_bodiesUpdateVelocities` in `Engine.update`, so the `positionPrev`/`anglePrev` values we set survive until the resolver runs.
6. Static bodies have `inverseMass=0` and `inverseInertia=0`, which means the `share` denominator only contains the ball's terms — the impulse is purely determined by the ball's ability to receive it, scaled by the relative velocity. This is exactly correct physics for an immovable object hitting a ball.

### Even Better: Body.rotate() with Point

Instead of separate `setAngle` + `setPosition`, use `Body.rotate(body, deltaAngle, hingePoint, true)` which internally calls both with `updateVelocity=true` and correctly computes the position change from rotating around the hinge:

```javascript
Body.rotate = function(body, rotation, point, updateVelocity) {
    if (!point) {
        Body.setAngle(body, body.angle + rotation, updateVelocity);
    } else {
        var cos = Math.cos(rotation), sin = Math.sin(rotation),
            dx = body.position.x - point.x,
            dy = body.position.y - point.y;

        Body.setPosition(body, {
            x: point.x + (dx * cos - dy * sin),
            y: point.y + (dx * sin + dy * cos)
        }, updateVelocity);

        Body.setAngle(body, body.angle + rotation, updateVelocity);
    }
};
```

### Complete Implementation

```javascript
// ═══════════════════════════════════════════════════════════════
// FLIPPERS — Static bodies with updateVelocity for momentum transfer
// ═══════════════════════════════════════════════════════════════

const FLIP_REST = 0.55;
const FLIP_ACTIVE = -0.55;
const FLIP_UP_SPEED = 0.22;
const FLIP_DN_SPEED = 0.10;
let leftFlipAngle = FLIP_REST;
let rightFlipAngle = FLIP_REST;

// Position a flipper at an ABSOLUTE angle around its hinge.
// First call (initialization): no updateVelocity (don't want phantom velocity)
// Subsequent calls: use updateVelocity=true for momentum transfer
function positionFlipper(body, hinge, angle, updateVelocity = false) {
  const halfLen = PADDLE_LEN / 2;
  Body.setAngle(body, angle, updateVelocity);
  Body.setPosition(body, {
    x: hinge.x + Math.cos(angle) * halfLen,
    y: hinge.y + Math.sin(angle) * halfLen
  }, updateVelocity);
}

function createPaddles() {
  leftPaddle = Bodies.rectangle(0, 0, PADDLE_LEN, PADDLE_WIDTH, {
    isStatic: true, label: 'paddleLeft', chamfer: { radius: 8 },
    collisionFilter: { category: CAT.ALWAYS, mask: CAT.BALL },
    restitution: 0.8, render: { visible: false }
  });
  rightPaddle = Bodies.rectangle(0, 0, PADDLE_LEN, PADDLE_WIDTH, {
    isStatic: true, label: 'paddleRight', chamfer: { radius: 8 },
    collisionFilter: { category: CAT.ALWAYS, mask: CAT.BALL },
    restitution: 0.8, render: { visible: false }
  });
  World.add(world, [leftPaddle, rightPaddle]);

  leftFlipAngle = FLIP_REST;
  rightFlipAngle = FLIP_REST;
  // Initial positioning — NO updateVelocity (don't want a phantom launch)
  positionFlipper(leftPaddle, LEFT_HINGE, FLIP_REST, false);
  positionFlipper(rightPaddle, RIGHT_HINGE, Math.PI - FLIP_REST, false);
}

function updateFlippers() {
  // Left flipper angle interpolation (unchanged)
  const leftTarget = isLeftPaddleUp ? FLIP_ACTIVE : FLIP_REST;
  if (leftFlipAngle !== leftTarget) {
    if (isLeftPaddleUp) {
      leftFlipAngle = Math.max(leftFlipAngle - FLIP_UP_SPEED, leftTarget);
    } else {
      leftFlipAngle = Math.min(leftFlipAngle + FLIP_DN_SPEED, leftTarget);
    }
  }
  // updateVelocity=true: resolver sees flipper motion as velocity
  positionFlipper(leftPaddle, LEFT_HINGE, leftFlipAngle, true);

  // Right flipper (mirrored)
  const rightTarget = isRightPaddleUp ? FLIP_ACTIVE : FLIP_REST;
  if (rightFlipAngle !== rightTarget) {
    if (isRightPaddleUp) {
      rightFlipAngle = Math.max(rightFlipAngle - FLIP_UP_SPEED, rightTarget);
    } else {
      rightFlipAngle = Math.min(rightFlipAngle + FLIP_DN_SPEED, rightTarget);
    }
  }
  positionFlipper(rightPaddle, RIGHT_HINGE, Math.PI - rightFlipAngle, true);

  // NO manual force application needed! The resolver handles it.
}
```

### What Changes From Current Code

1. `positionFlipper` gains an `updateVelocity` parameter (default `false`).
2. `createPaddles` passes `false` explicitly (no change in behavior).
3. `updateFlippers` passes `true` to `positionFlipper` -- this is the only functional change.
4. The entire manual force block (lines 469-486 in current code) is DELETED.
5. Everything else stays identical: same angle interpolation, same constants, same static bodies.

### The Restitution Question

With `updateVelocity=true`, the collision impulse now includes the flipper's velocity. The `restitution: 0.8` on the flipper determines how much of the relative velocity is preserved. For pinball feel:
- `restitution: 0.8-0.9` = bouncy, satisfying launch. Ball gets most of the flipper's velocity.
- `restitution: 0.5-0.7` = controlled, more realistic. Ball gets moderate launch.
- `restitution: 1.0` = perfect elastic collision. Maximum launch power.

Current value `0.8` should be a good starting point.

### When Flipper Is Stationary

When the flipper isn't moving, `leftFlipAngle` doesn't change between frames, so `setAngle(body, sameAngle, true)` produces `anglePrev = angle` (no delta). Similarly for position. The resolver sees zero velocity, and the ball bounces off with pure restitution. This is correct -- a stationary flipper shouldn't launch the ball.

### Assessment
- **Pros**: Minimal code change (literally adding `, true` to two function calls). Uses Matter.js's OWN collision resolver -- the impulse direction, magnitude, and contact-point velocity are all computed correctly by the engine. No hacks, no approximations. Static bodies stay static (no drift, no jitter, no fighting gravity). Angular velocity contribution means tip of flipper hits harder than base (correct physics). Works with restitution naturally.
- **Cons**: The velocity is derived from position/angle delta per frame. At low framerates, the delta per frame is larger, which could produce stronger hits. At high framerates, smaller deltas mean weaker hits. However, this is true of ALL Matter.js physics, so it's consistent with the rest of the simulation.
- **Feel**: Should be the most physically correct and satisfying of all approaches. The ball's launch angle and speed are determined by the actual flipper motion, contact point, and collision normal -- exactly how real physics works.
- **Failure modes**: If `updateFlippers()` is called when the flipper ISN'T moving (same angle as last frame), passing `updateVelocity=true` correctly produces zero velocity. If the flipper reaches its angle limit and stops, the next frame has zero delta -- correct. The only edge case is the first frame after `createPaddles()` where the flipper snaps to rest position, but we handle that with `updateVelocity=false` on initialization.

### Verdict: **A+. Minimal change, maximum correctness. This is the approach.**

---

## Approach 4: Static Body + Manual Force on Collision Event

### How It Works
Use `collisionStart`/`collisionActive` events. When the ball collides with a flipper that's currently moving, compute the tangential velocity at the contact point and apply force.

```javascript
Events.on(engine, 'collisionStart', function(event) {
  event.pairs.forEach(pair => {
    const { bodyA, bodyB } = pair.collision;

    let flipper = null, ball = null, hinge = null, omega = 0;

    if (bodyA.label === 'paddleLeft' && bodyB.label === 'pinball') {
      flipper = bodyA; ball = bodyB; hinge = LEFT_HINGE;
      omega = leftFlipAngle - prevLeftAngle;
    } else if (bodyB.label === 'paddleLeft' && bodyA.label === 'pinball') {
      flipper = bodyB; ball = bodyA; hinge = LEFT_HINGE;
      omega = leftFlipAngle - prevLeftAngle;
    } else if (bodyA.label === 'paddleRight' && bodyB.label === 'pinball') {
      flipper = bodyA; ball = bodyB; hinge = RIGHT_HINGE;
      omega = (Math.PI - rightFlipAngle) - prevRightAngle;
    } else if (bodyB.label === 'paddleRight' && bodyA.label === 'pinball') {
      flipper = bodyB; ball = bodyA; hinge = RIGHT_HINGE;
      omega = (Math.PI - rightFlipAngle) - prevRightAngle;
    }

    if (!flipper || !ball || Math.abs(omega) < 0.001) return;

    // Contact point (use first contact from pair)
    const contact = pair.activeContacts[0] || pair.contacts?.[0];
    if (!contact) return;
    const cx = contact.vertex.x, cy = contact.vertex.y;

    // Radius from hinge to contact point
    const rx = cx - hinge.x, ry = cy - hinge.y;
    const dist = Math.sqrt(rx * rx + ry * ry);

    // Tangential velocity: perpendicular to radius, magnitude = omega * dist
    const perpX = -ry / dist;
    const perpY = rx / dist;
    const speed = omega * dist;

    const IMPULSE_SCALE = 0.12;
    Body.applyForce(ball, { x: cx, y: cy }, {
      x: perpX * speed * IMPULSE_SCALE,
      y: perpY * speed * IMPULSE_SCALE
    });
  });
});
```

### Assessment
- **Pros**: Only fires on actual collisions (no proximity false positives). Uses real contact point from the engine. Physically motivated direction calculation.
- **Cons**: `collisionStart` fires AFTER the resolver has already resolved the collision — so the ball gets the restitution bounce PLUS the manual force (double impulse). The `collisionActive` alternative fires every frame while touching, which would repeatedly apply force. Timing is wrong: force applied after resolution, not during. The contact point from Matter.js may not be ideal for the force application point. Need to track previous angles manually.
- **Feel**: Better than Approach 1 because it only fires on real collisions, but still has the double-impulse problem. The ball will bounce higher than expected because restitution AND manual force both contribute.
- **Failure modes**: Double impulse (restitution + manual force) makes ball trajectory unpredictable. If ball rolls along flipper surface, `collisionActive` would keep applying force every frame. If the collision normal is perpendicular to the flipper surface but the force direction is tangential to the flipper rotation, they can fight each other.

### Verdict: **B. Viable fallback but has the double-impulse problem. Approach 3 is strictly better.**

---

## Approach 5: What Does pinball-schminball Actually Do?

### Analysis of igorski/pinball-schminball engine.ts

Confirmed from source code analysis:

1. **Flippers are DYNAMIC bodies** (not static). Created with `frictionAir: 0` and `chamfer: {}`.
2. **Constrained to a static pivot** via `Matter.Constraint.create({ pointA: { x: pivotX, y: pivotY }, bodyB: flipperBody, stiffness: 0 })`. The `stiffness: 0` makes the constraint "soft" — it doesn't resist motion.
3. **Momentum transfer is 100% via attractors**. Two invisible static circles (stopper up, stopper down) positioned above and below the pivot. Each has an attractor function:
   ```typescript
   attractors: [(a, b) => {
     if (b.id !== flipperId) return;
     if ((position === UP && isFlipperUp) || (position === DOWN && !isFlipperUp)) {
       return {
         x: (a.position.x - b.position.x) * FLIPPER_FORCE,
         y: (a.position.y - b.position.y) * FLIPPER_FORCE
       };
     }
   }]
   ```
4. **No manual impulse on collision.** No `collisionStart` handler for flippers. No `applyForce` on the ball.
5. **No velocity setting.** No `setVelocity`, `setAngularVelocity`, or `setAngle` on the flipper.

### How Momentum Actually Transfers

The flippers are DYNAMIC bodies being pulled by attractor forces. As the stopper pulls the flipper, the flipper gains real velocity and angular velocity through the physics engine's normal integration. When the ball collides with this moving dynamic body, standard collision resolution transfers momentum naturally.

The attractor force is: `FLIPPER_FORCE = 0.002666 * GRAVITY = ~0.00227`

This creates a relatively slow but steady pull toward the stopper position. The flipper accelerates, picks up velocity, and that velocity is what transfers to the ball on collision. The stopper circle limits the range (once the flipper reaches the stopper, the distance approaches zero, and the force approaches zero).

### Why We Can't Use This

We already tried the attractor-stopper pattern and it was unstable: flickering, wrong angles, compound body issues. The dynamic body approach requires careful tuning of constraint stiffness, attractor force, stopper positions, and collision groups — lots of moving parts that can go wrong.

### Key Takeaway

pinball-schminball validates that Matter.js CAN transfer momentum from flippers to balls — but only when the flipper is a dynamic body with real velocity. Our Approach 3 achieves the same effect (resolver sees velocity on the flipper) without making the flipper dynamic, by exploiting the `updateVelocity` parameter.

---

## Comparative Summary

| Approach | Code Change | Physics Correctness | Pinball Feel | Stability | Verdict |
|----------|-------------|-------------------|-------------|-----------|---------|
| 1. Manual impulse (improved) | Medium | Low (proximity, not collision) | C+ | High | Fallback only |
| 2. Kinematic (dynamic + setVelocity) | Large | High (real velocity) | B- (if stable) | Low (drift, jitter) | Not recommended |
| **3. updateVelocity=true** | **Tiny (add `, true`)** | **High (resolver-native)** | **A+** | **High (stays static)** | **DO THIS** |
| 4. Collision event + force | Medium | Medium (double impulse) | B | Medium | Viable fallback |
| 5. Attractor-stopper (pinball-schminball) | Large | High | A (when working) | Low (our experience) | Already tried, unstable |

## Recommendation

**Approach 3: `updateVelocity=true`**

The change is almost embarrassingly small. The current `positionFlipper` function calls `Body.setAngle(body, angle)` and `Body.setPosition(body, pos)`. Adding `true` as the third argument to both calls makes the collision resolver see the flipper's velocity and compute proper impulses on the ball.

Lines to change:
```javascript
// BEFORE (current)
function positionFlipper(body, hinge, angle) {
  const halfLen = PADDLE_LEN / 2;
  Body.setAngle(body, angle);
  Body.setPosition(body, {
    x: hinge.x + Math.cos(angle) * halfLen,
    y: hinge.y + Math.sin(angle) * halfLen
  });
}

// AFTER
function positionFlipper(body, hinge, angle, updateVelocity = false) {
  const halfLen = PADDLE_LEN / 2;
  Body.setAngle(body, angle, updateVelocity);
  Body.setPosition(body, {
    x: hinge.x + Math.cos(angle) * halfLen,
    y: hinge.y + Math.sin(angle) * halfLen
  }, updateVelocity);
}
```

Then in `updateFlippers()`, change:
```javascript
positionFlipper(leftPaddle, LEFT_HINGE, leftFlipAngle);
// becomes:
positionFlipper(leftPaddle, LEFT_HINGE, leftFlipAngle, true);
```

And DELETE the entire manual force block (lines 469-486).

### Tuning Levers

If the launch power needs adjustment after implementing Approach 3:

| Want | Adjust |
|------|--------|
| Stronger launch | Increase `restitution` (try 0.9-1.0) or increase `FLIP_UP_SPEED` |
| Weaker launch | Decrease `restitution` (try 0.6-0.7) or decrease `FLIP_UP_SPEED` |
| Snappier flipper (faster reach) | Increase `FLIP_UP_SPEED` (try 0.25-0.30) |
| More gradual flipper return | Decrease `FLIP_DN_SPEED` (try 0.06-0.08) |
| Ball sticks to flipper more | Increase `friction` on flipper (try 0.3-0.5) |
| Ball slides off flipper more | Decrease `friction` on flipper (try 0.01) |

The biggest lever is `FLIP_UP_SPEED` because it directly determines how much angular velocity the resolver sees per frame. At 0.22 rad/frame and a paddle length of 280px, the tip velocity is `0.22 * 280 = 61.6 px/frame`, which is substantial. If that's too much, lower FLIP_UP_SPEED. If too little, raise it.

## Confidence
**Confident** -- verified against Matter.js source code (Resolver.js, Body.js, Engine.js). The mechanism is not a hack; it's using the API exactly as designed (the `updateVelocity` parameter exists for this purpose). The only unknowns are tuning values, which are empirically adjustable in seconds.

## Open Questions

1. **Frame-rate sensitivity**: The velocity delta is per-frame, not per-second. At 120fps the delta per frame is half what it would be at 60fps. Matter.js's `deltaTime` and `_baseDelta` handle this for `setVelocity`/`setAngularVelocity`, but `setAngle`/`setPosition` with `updateVelocity=true` set the raw delta without time scaling. If the game runs at variable framerates, this could cause inconsistent launch power. If this is a problem, use `Body.setVelocity` / `Body.setAngularVelocity` explicitly with time-corrected values instead of relying on `updateVelocity=true`.

2. **Alternative: Body.rotate with point**: Instead of separate setAngle + setPosition, could use `Body.rotate(flipper, deltaAngle, hingePoint, true)`. This is cleaner but requires tracking the delta angle rather than the absolute angle. The positionFlipper approach (absolute angle) is simpler for our existing code structure.

3. **Will restitution be enough?** With `restitution: 0.8`, the ball gets 80% of the relative velocity at the contact point. For a pinball feel, this should be close to right. If it's too weak, bumping to 1.0 gives a perfect elastic collision. If it's too strong, lower it. The important thing is that the DIRECTION is now correct (determined by collision normal and contact point, not a hard-coded vector).
