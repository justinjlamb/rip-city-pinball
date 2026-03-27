# Research Critic — Adversarial Analysis
*Final — 3 iterations completed | Mar 21, 2026*

## Source Log
- [Matter.js Issue #672 - Objects passing through](https://github.com/liabru/matter-js/issues/672) - Maintainer confirms tunneling is CCD issue, still unresolved (credibility: high)
- [Matter.js Issue #5 - CCD request](https://github.com/liabru/matter-js/issues/5) - Opened Feb 2014, STILL OPEN 12 years later. No working implementation. (credibility: high)
- [h4k1m0u/pinball - Planck.js choice](https://github.com/h4k1m0u/pinball) - Developer explicitly chose Planck.js over Matter.js due to flipper-ball tunneling (credibility: high)
- [Planck.js revolute joint docs](https://piqnt.com/planck.js/docs/joint/revolute-joint) - Native motor+angle limit joints, no attractor hack needed (credibility: high)
- [Phaser forum - flipper rotation](https://phaser.discourse.group/t/matter-physics-pinball-game-how-to-rotate-flippers/1718) - Attractor pattern is described as a WORKAROUND for Matter.js lacking proper joints (credibility: high)
- [Coder's Block - lonekorean](https://codersblock.com/blog/javascript-physics-with-matter-js/) - Original attractor pattern source. Provides NO exact values. Uses invisible thick bricks to compensate for missing CCD. (credibility: high)
- [daily.dev engine comparison](https://daily.dev/blog/top-9-open-source-2d-physics-engines-compared) - Matter.js at 40% of Box2D performance, described as "less feature-rich" (credibility: medium)
- [npm-compare Planck vs Matter](https://npm-compare.com/planck,matter-js) - Matter.js has 248 open issues vs Planck's 25 (credibility: high)
- [fishshiz/pinball-wizard](https://github.com/fishshiz/pinball-wizard) - Built in 5 days, uses angular velocity NOT attractors, acknowledges flipper mechanics still need work (credibility: medium)
- [HN: Physics Engine 13x Faster](https://news.ycombinator.com/item?id=37315840) - Kinetics author notes Matter.js lacks "linkages and constraints" — that's where game physics gets hairy (credibility: medium)
- [Emanueleferonato - Planck.js revolute joints](https://emanueleferonato.com/2021/02/04/understanding-box2d-revolute-joints-html5-example-powered-by-phaser-and-planck-js/) - Clean motor-driven flipper with maxMotorTorque: 120 (credibility: high)
- [Planck.js official Pinball example](https://piqnt.com/planck.js/Pinball) - Working pinball with RevoluteJoint flippers, bullet CCD, motor control. Proof that Planck.js does this natively. (credibility: high)
- [Lu1ky Pinball 1K deep dive](https://frankforce.com/lu1ky-pinball-code-deep-dive/) - Complete pinball in 1,013 bytes using circle-only physics and 9 substeps. Proves minimal viable pinball needs very little code. (credibility: high)
- [amandafager/pinball - Phaser 3 + Matter.js](https://github.com/amandafager/pinball) - 108 commits, ball gets stuck in corners, 30-second load times. Demonstrates that even multi-person teams struggle with Matter.js pinball quality. (credibility: medium)
- [Planck.js + SVG editable table](https://piqnt.com/planck.js/) - Planck.js playground includes pinball with editable SVG tables, proving SVG+physics alignment is supported natively (credibility: medium)

## Counter-Narrative

**The research brief's architecture has a foundational physics engine problem that workarounds cannot fully solve.**

The attractor-stopper flipper pattern is not a "proven pattern" — it's a creative hack to compensate for Matter.js's lack of two critical features that Box2D/Planck.js have natively:

1. **Revolute joints with motors** — Box2D/Planck.js have built-in motorized hinge joints with angle limits, torque control, and proper angular momentum transfer. Matter.js constraints are spring-like connections that approximate this behavior but don't properly model rotational dynamics.

2. **Continuous Collision Detection (CCD)** — Box2D has bullet mode that prevents tunneling through swept collision testing. Matter.js has had a CCD feature request open since **February 2014** (12 years) with no working implementation. The workarounds (substeps, thick invisible bricks, speed clamping) are band-aids, not solutions.

The attractor pattern works by using invisible bodies with gravitational pull to swing flippers. This is mechanically fragile because:
- It depends on precise force tuning (the "magic numbers" PADDLE_PULL = 0.002, stiffness = 0)
- It fights the constraint system rather than working with it
- It requires invisible thick bricks attached to flippers to prevent ball tunneling
- Force magnitudes that work at one scale break at another
- Adding table elements (bumpers, slingshots) changes the force dynamics

**Planck.js solves these problems by design:**
```javascript
// Planck.js flipper — native, no hacks
const flipperJoint = world.createJoint(planck.RevoluteJoint({
    bodyA: pivot,
    bodyB: flipper,
    anchorPoint: pivot.getWorldCenter(),
    lowerAngle: -30 * Math.PI / 180,
    upperAngle: 30 * Math.PI / 180,
    enableLimit: true,
    maxMotorTorque: 120,
    motorSpeed: 0,
    enableMotor: true
}));
// To flip: flipperJoint.setMotorSpeed(20);
// To release: flipperJoint.setMotorSpeed(-10);
```

No attractors. No invisible bricks. No magic numbers. Native angle limits prevent over-rotation. Motor torque transfers real angular momentum to the ball. CCD bullet mode prevents tunneling.

## Unverified Claims

- Claim: "PADDLE_PULL = 0.002 is the proven value" — Evidence quality: **weak**. The lonekorean blog post provides NO numerical values. The research brief's values appear to be extracted from source code of one implementation at one scale. No evidence these are stable across different table sizes or ball weights.

- Claim: "pinball-schminball uses EXACTLY our architecture" — Evidence quality: **moderate**. It does use Matter.js + PNG + SVG + attractors. But "exactly our architecture" overstates the similarity — pinball-schminball is ~5,500 lines of TypeScript with Vue3 and has had extensive development time. The architecture is similar; the maturity is not.

- Claim: "positionIterations: 100 and velocityIterations: 16 for collision accuracy" — Evidence quality: **weak**. These are from pinball-schminball's code, but positionIterations: 100 is extreme (default is 6). This suggests the developer was fighting collision problems rather than solving them. High iteration counts are a brute-force workaround, not a tuning win.

- Claim: "3 substeps at 180Hz physics solves tunneling" — Evidence quality: **moderate**. Substeps reduce tunneling probability but don't eliminate it. A ball moving at maxSpeed 25 across a 3px gap at 180Hz can still tunnel. Only CCD truly solves this. Box2D has CCD; Matter.js does not.

- Claim: "Collision categories/masks are industry standard for ramps" — Evidence quality: **strong** for the general concept, but the complexity of implementing this correctly in Matter.js vs the value it adds for a showcase demo is unexamined.

## Unstated Assumptions

1. **Matter.js is the right tool.** The research brief never questions this choice. It treats Matter.js as given and asks "how do we make it work?" instead of "should we use something else?" Planck.js provides every feature the brief identifies as critical (revolute joints, CCD, proper momentum transfer) natively, without plugins or hacks.

2. **The showcase needs full pinball mechanics.** Ramp layers, multiball, SVG alignment, slingshots, combo scoring — this is the scope of a commercial pinball game, not a workplace showcase demo for interns. The audience will be impressed by a ball that bounces well and flippers that snap, not by collision category masks on invisible ramp sensors.

3. **Pre-rendered PNG is locked in.** The brief assumes a single Gemini-generated table image that gets split into layers. But if the physics boundaries don't match the art (and they won't, first try), you either: (a) regenerate the art, (b) live with visible misalignment, or (c) hand-edit SVG paths pixel by pixel. None of these are fast.

4. **A father-daughter team can absorb 5,500 lines of TypeScript reference code.** The research brief points to pinball-schminball as "the" reference implementation. It's a Vue3 TypeScript project with Matter.js plugins, data-driven table definitions, and complex physics tuning. This is not a learning-friendly codebase for someone who's learning.

5. **8 phases can be completed in 17 days part-time.** The brief lists 8 implementation phases. Even if each phase took only 2 days of focused work (and Phase 1 already took a full day with no success), that's 16 days of full-time work. Part-time with a learning partner, you're looking at 30+ days minimum.

## Alternative Approaches

### Option A: Switch to Planck.js (moderate effort, high payoff)
- Native revolute joints with motors (no attractor hack)
- Native CCD via bullet bodies (no tunneling workarounds)
- Box2D documentation and tutorials are vast
- Slightly less beginner-friendly API than Matter.js
- Migration cost: rewrite physics layer (~1-2 days for someone experienced)

### Option B: Fork pinball-schminball and reskin (lowest effort, highest risk)
- Already a working Matter.js pinball game
- Replace table PNG, adjust SVG collision shapes
- Risk: Vue3 + TypeScript complexity may be harder to modify than building fresh
- Risk: "learning" goal is undermined if it's just reskinning

### Option C: Radically simplify scope (recommended for timeline)
- Skip: ramps, multiball, SVG alignment, split image layers, combo scoring
- Keep: flippers, bumpers, plunger, basic scoring, Portland theme art
- Use simple geometric collision shapes (not SVG traces)
- Target: "fun to play for 60 seconds" not "faithful pinball simulation"
- This is achievable in 5-7 days part-time

### Option D: Use Construct 3 (no-code option)
- Visual game builder with built-in physics
- Multiple pinball tutorials exist
- Good for father-daughter collaboration (visual, immediate feedback)
- Trade-off: less "coding" learning, more "game design" learning
- Could produce a playable game in 3-5 days

## Confidence in Critique
**Confident.** The counter-arguments are well-sourced from primary technical documentation (Matter.js GitHub issues, Planck.js docs, the original pattern author's blog post). The CCD gap is a documented, 12-year-old architectural limitation, not speculation. The scope concern is arithmetic (8 phases x estimated days > available time). The attractor pattern fragility is demonstrated by the user's own experience fighting it on day one.

The mainstream view (use Matter.js + attractors + substeps) is **partially flawed** — it can work, but it's fighting the engine's design rather than working with it, and the scope implied by the research brief is unrealistic for the timeline and team composition.

## Iteration 3 Findings — Steel-Manning Matter.js

**Fair counterpoint:** Matter.js pinball games DO exist and work (lonekorean CodePen, pinball-schminball, pinball-wizard, CodePen by agalliat). The attractor pattern CAN produce playable results. The ecosystem is larger (17k+ stars, more tutorials, more Stack Overflow answers). Planck.js has 1/30th the community.

**But the evidence still favors the critique:**
- The Phaser 3 pinball project (amandafager) with 108 commits still has bugs (ball stuck in corners). This is a multi-person team project.
- pinball-wizard was built in 5 days but the author says flippers "still need work." Direct angular velocity, not attractors.
- The Planck.js official examples include a working pinball with RevoluteJoint + bullet CCD + motor control in ~50 lines. The equivalent Matter.js setup requires attractors plugin + invisible bricks + speed clamping + 100 position iterations.
- Lu1ky Pinball proves a complete, satisfying pinball game can exist in 1,013 bytes. Scope is the enemy, not technology.

**The steel-man for staying with Matter.js:** If the team has already invested time learning Matter.js, switching costs are real. The pinball-schminball reference implementation exists. The attractor pattern will work if you get the values right. But "if you get the values right" is exactly the fragility concern — the team already spent a full day NOT getting the values right.

## Final Assessment

### Top 5 Critical Findings

1. **Matter.js lacks CCD — this is a 12-year-old unfixed architectural gap.** Every tunneling workaround (substeps, thick bricks, speed clamping) is a band-aid. Planck.js/Box2D have native CCD via bullet bodies. This is the single biggest risk to game quality.

2. **The attractor flipper pattern is a hack, not a feature.** It exists because Matter.js lacks revolute joints with motors. Planck.js has these natively. The "proven values" (PADDLE_PULL = 0.002) are extracted from one implementation at one scale and are not documented by the original author as universal constants.

3. **The scope is 2-3x what the timeline allows.** Eight phases, part-time work, father-daughter team where one person is learning. Phase 1 (flippers alone) consumed a full day with no working result. The math does not add up to April 7.

4. **The pre-rendered PNG approach creates an art-physics coupling trap.** Any time collision shapes don't match the visual art, you either regenerate art (slow, non-deterministic with AI) or hand-trace new SVG paths (tedious). This will be the #1 source of "it looks wrong" debugging.

5. **The research brief treats a 5,500-line TypeScript reference implementation as a blueprint.** pinball-schminball is not a tutorial — it's a mature codebase. Treating it as "study these files first" underestimates the complexity gap between reading code and understanding architecture.

### Strongest Counter-Argument (2 sentences)
Matter.js is the wrong physics engine for pinball. Planck.js provides the two features most critical to pinball — motorized revolute joints and continuous collision detection — as built-in capabilities rather than plugin workarounds, and the team's day-one struggle with flippers is a direct consequence of fighting Matter.js's architectural limitations rather than a tuning problem that better values will solve.

### Assessment
The mainstream view (stick with Matter.js, use the attractor pattern, follow the 8-phase plan) is **partially flawed**. The physics engine choice is defensible but suboptimal. The attractor pattern works but is fragile. The scope is unrealistic. The recommended path: either switch to Planck.js and radically simplify scope (Option A+C), or fork pinball-schminball and reskin it (Option B). Building from scratch with Matter.js through 8 phases in 17 days part-time with a learning partner is the least likely path to a working showcase demo.

### Iterations Used: 3
