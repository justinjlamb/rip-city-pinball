# Research Round 2 — Critic Findings
*Adversarial analysis of Round 1 comparator conclusions*
*2026-03-22 | 3 iterations*

## Source Log
- [Matter.js issue #157 — Moving bodies accurately](https://github.com/liabru/matter-js/issues/157) - Maintainer confirms: setPosition bypasses velocity calculations entirely. "Setting position will quite literally set position. And the collision resolver will not know how to handle it as the velocities that caused it are technically nonexistent." (credibility: HIGH)
- [Phaser forum — Matter flipper rotation](https://phaser.discourse.group/t/matter-physics-pinball-game-how-to-rotate-flippers/1718) - Unresolved core issue: tweening/setting flipper position alone doesn't transfer momentum to ball. Only working solution in thread: attractor-based approach. (credibility: HIGH)
- [h4k1m0u/pinball](https://github.com/h4k1m0u/pinball) - Developer explicitly chose Planck.js OVER Matter.js "because of the tunneling happening during the collision between flipper & ball with the latter." (credibility: HIGH)
- [Planck.js official Pinball demo](https://piqnt.com/planck.js/Pinball) - ~60 lines of code. Revolute joints with motors, `enableMotor: true`, `maxMotorTorque: 1000`, `bullet: true` for CCD. This is what "native flipper support" looks like. (credibility: HIGH)
- [Lu1ky Pinball deep dive](https://frankforce.com/lu1ky-pinball-code-deep-dive/) - Custom physics, NO engine. Flippers = 65 individual circles along an arc. Velocity derived from position delta between frames. 9 physics substeps. Entire game in 1KB. (credibility: HIGH)
- [Pinball Wizard — 5-day Matter.js build](https://github.com/fishshiz/pinball-wizard) - Developer says "the most difficult part was figuring out how to get my paddles to move correctly." Used angular velocity on keyDown. ~460 lines. (credibility: MEDIUM)
- [Amano Games — custom pinball physics](https://amano.games/devlog/making-a-pinball-game-for-the-playdate-part-02-the-physics) - Built custom rigid body physics in C after failing with collision masks. Took a week-long 2D physics course. Cut corners where it made sense for pinball specifically. (credibility: HIGH)
- [Ernest Adams — Pinball Design Challenges (Gamasutra)](https://www.gamedeveloper.com/design/designer-s-notebook-the-unique-design-challenge-of-pinball-simulations) - "The ball must behave exactly the way a real ball would." Physics flaws are immediately noticeable. Common amateur mistake: over-complicating with features unavailable in physical machines. (credibility: HIGH)
- [Matter.js 0.20.0 Body API docs](https://brm.io/matter-js/docs/classes/Body.html) - CONFIRMED: `Body.setAngle(body, angle, [updateVelocity=false])` — "If `updateVelocity` is `true` then angular velocity is inferred from the change in angle." Same for `setPosition`. This is the missing parameter. (credibility: HIGH)

## Challenge 1: The Static Flipper Impulse Gap is NOT Solved

**The comparator's claim: "The flipper problem is already solved."**

**Verdict: FALSE. The problem is masked, not solved.**

The current implementation uses `Body.setAngle()` + `Body.setPosition()` on static bodies, with a manual impulse hack: "Ball gets a small upward impulse when flipper is actively swinging and ball is nearby" (from HANDOFF.md).

This is architecturally broken per Matter.js's own maintainer:

> "Setting position will quite literally set position. And the collision resolver will not know how to handle it as the velocities that caused it are technically nonexistent." — @formula1 on Matter.js issue #157

What this means in practice:
1. Static bodies repositioned via `setAngle`/`setPosition` have **zero velocity** in the engine's eyes
2. When the flipper "hits" the ball, the collision resolver sees a stationary object — it deflects the ball but transfers NO momentum
3. The manual impulse hack compensates, but it's disconnected from the actual collision geometry — it's a proximity-based force, not a physics-accurate response
4. This produces flippers that PUSH the ball but don't LAUNCH it with the crisp, directional snap of real pinball

**The real fixes (ranked by reliability):**

1. **`Body.setAngle(angle, true)` with `updateVelocity: true`** — This is the undocumented second parameter. When true, Matter.js infers velocity from the position/angle change. The collision resolver then sees a body WITH velocity and can transfer momentum properly. This is the cheapest fix if it works.

2. **Dynamic bodies with constraints** — The attractor-stopper pattern from lonekorean. This was the Round 1 research recommendation but was rejected because it proved "unstable." The instability was from wrong parameter values (PADDLE_PULL 45x too high), not from the pattern itself.

3. **Manual impulse proportional to flipper angular velocity** — Calculate the flipper's angular velocity from the angle delta, compute the contact point's linear velocity (angVel * distance from hinge), apply that as a directed impulse on the ball at the collision point. This is what Lu1ky Pinball does (velocity from position delta). It works but requires careful tuning.

**The cheapest experiment:** Try `Body.setAngle(body, newAngle, true)` — literally adding one boolean parameter. If Matter.js 0.20.0 supports this, the impulse problem may solve itself. If not, option 3 (manual impulse proportional to angular velocity at contact point) is the most predictable path.

## Challenge 2: The 5-Phase Plan Assumes Linear Progress

**Realistic failure mode analysis:**

| Phase | Estimated | Failure Mode | Probability | Why |
|-------|-----------|-------------|-------------|-----|
| 1: Physics Tuning | 2 hrs | Substep changes break existing flipper timing; speed clamping makes game feel sluggish | MEDIUM | Substeps change the effective force magnitudes. Every physics value needs re-tuning. |
| 2: Slingshots + Bumpers | 2 hrs | Positioning slingshot sensors requires visual alignment iteration; force values need extensive tuning per-body | LOW | Straightforward if Phase 1 is solid. |
| 3: Scoring | 2 hrs | Low risk — pure game logic, no physics dependency | LOW | Could be done in parallel with anything. |
| 4: Plunger Polish | 1 hr | Low risk — already partially working | LOW | Cosmetic. |
| 5: Image Layering | 2 hrs | GIMP image splitting requires artistic skill; transparency masking of ramp areas is fiddly; z-order bugs are hard to debug | MEDIUM | This is image editing work, not code. Different skill. |

**The real blocker is Phase 0 (unlisted): making flippers actually launch the ball.** Without this, the game is broken at a fundamental level. The plan assumes this is solved. It isn't.

**Secondary blocker:** Physics body alignment. The HANDOFF says "editor-mapped walls/curves need testing with actual gameplay." This is unpredictable iteration time. Walls that look aligned in debug mode may produce bizarre ball behavior in gameplay (ball stuck in corners, weird bounces off invisible edges, ball escaping the table).

## Challenge 3: Is showcase.html the Better Bet?

**Current state comparison:**

| Dimension | showcase.html | index.html (pinball) |
|-----------|--------------|---------------------|
| Status | "Mostly done" — working, runs continuously | Broken fundamentals (flipper impulse) |
| Risk | Low — polish work only | High — unsolved physics problems |
| Wow factor (current) | Medium — nice but static-feeling | Low — flippers don't launch the ball |
| Wow factor (ceiling) | High with investment | Very high IF physics works |
| Time to "wow" | 4-8 hours of polish | Unknown — could be 4 hours or 40 |
| Showcase fit | Explains her role clearly | Fun, interactive, memorable |

**What a "wow" version of showcase.html would look like:**
- Full-screen cinematic mode with dark backdrop, ambient sound
- Real event names from the pop culture list scrolling through (Linkin Park, Dave Chappelle, Monster Jam...)
- Particle effects that intensify during "busy season" visualization
- Click an event to see the full department communication chain animate
- Mobile-optimized for people passing by on phones
- Easter egg: a "Details Form" counter that increments
- Ambient background audio (crowd noise fading in/out)

**Time estimate for wow showcase:** 8-12 hours. Achievable in 4-5 sessions.

**The strategic question:** Is a polished, impressive visualization that clearly communicates her role BETTER for the showcase than a half-broken pinball game? Almost certainly yes, if those are the only two options.

**But they're not the only two options.** The real question is whether the pinball game can be rescued to a "fun and impressive" state. See Challenge 4.

## Challenge 4: The Planck.js Question Wasn't Properly Dismissed

**The comparator said: "Switching cost is real."**

**Let's actually quantify it.**

Planck.js official pinball demo: ~60 lines. Features used:
- `RevoluteJoint` with `enableMotor: true`, `maxMotorTorque: 1000`, `enableLimit: true`
- `bullet: true` on ball for continuous collision detection (CCD)
- Motor speed toggles on key press (positive/negative)

What this gives you FOR FREE that Matter.js doesn't have:
1. **Revolute joints with motors** — flippers rotate around a hinge with configurable torque. No attractor hacks. No manual impulse. No `setAngle`. Just... joints that work like joints.
2. **Continuous Collision Detection** — `bullet: true`. Ball never tunnels through flippers or walls. Matter.js issue #5 (CCD) has been open since 2014.
3. **Proper momentum transfer** — motor-driven rotation means the flipper HAS angular velocity. The collision resolver handles the rest.

**What needs to be ported from the current 1200-line game:**
- Physics body positions (walls, bumpers, curves) — same concept, different API syntax
- Collision categories/masks — Planck.js has `filterCategoryBits`/`filterMaskBits`, same concept
- Layer transition triggers — pure game logic, engine-independent
- Flipper system — REPLACED by RevoluteJoint (this is the whole point)
- Rendering — Canvas rendering is engine-independent
- Sound, scoring, attract mode, game flow — engine-independent
- Debug mode — needs rewriting for Planck.js body iteration

**Realistic port estimate:**
- Physics body creation: 2-3 hours (translating syntax, not concepts)
- Flipper replacement: 30 minutes (simpler in Planck.js than current hack)
- Collision filtering: 1 hour
- Debug overlay: 1-2 hours
- Testing and tuning: 2-3 hours
- **Total: 6-10 hours, or 3-4 sessions**

The comparator said "2-3 days minimum." With focused work and the official pinball demo as reference, it could be done in 2 solid sessions. The question is whether the time saved on NOT fighting Matter.js flipper physics makes up for the port cost.

**Key evidence:** The h4k1m0u developer explicitly switched FROM Matter.js TO Planck.js for their pinball game because of "tunneling happening during the collision between flipper & ball." This isn't a theoretical concern — someone already hit exactly this wall and switched.

## Challenge 5: What Would a Professional Game Developer Actually Do?

**Evidence-based answer from sources:**

1. **Ernest Adams (Gamasutra):** Focus on physics feel above everything. "The ball must behave exactly the way a real ball would." Don't over-complicate with features unavailable in physical machines.

2. **Lu1ky Pinball (Frank Force):** Skip the physics engine entirely. Custom physics with 65 circles per flipper, velocity from position delta, 9 substeps. Entire game in 1KB. A professional who knows physics can move faster without an engine's abstractions getting in the way.

3. **Pinball Wizard (5-day build with Matter.js):** The developer called flippers "the most difficult part." Built in 5 days, ~460 lines. Functional but not impressive-feeling.

4. **Amano Games (Devils on the Moon):** Built custom physics after failing with premade approaches. Took a week-long course. Said basic rigid body simulation "isn't particularly difficult."

**What a pro would actually do with 16 days and this specific project:**

A professional game developer would NOT use Matter.js for pinball. They would either:

**Option A: Planck.js (if physics accuracy matters)**
- Fork the official 60-line pinball demo
- Add their custom table geometry
- Layer the pre-rendered table image behind the physics canvas
- Spend most time on game feel, sound, and polish
- Time to playable: 2-3 days. Time to polished: 1 week.

**Option B: Phaser 3 + Matter.js plugin (if they want a framework)**
- Phaser wraps Matter.js but adds scene management, input handling, sprite rendering
- Multiple Phaser pinball repos exist as references
- Still has the Matter.js flipper problem underneath
- Time to playable: 3-5 days.

**Option C: Fake it (if time is the hard constraint)**
- Pre-defined ball paths with slight randomization
- Flipper "hit zones" that redirect the ball based on timing
- No real physics — just animation + hit detection
- Looks amazing if the art is good, feels hollow if you play more than 30 seconds
- Time to impressive demo: 1-2 days.
- This is what Game Boy-era pinball games did.

**Option D: Skip pinball, make the showcase incredible (pragmatic choice)**
- The showcase visualization already works and communicates Alicia's role
- Polish it to cinematic quality
- Add the pinball game only if time permits, as a "bonus"
- Time to wow: 4-6 sessions (8-12 hours)

## Counter-Narrative

The Round 1 comparator's conclusion — "Stay with Matter.js, keep static flippers, radically simplify scope, ship by Phase 5" — is built on a false premise: that the flipper problem is solved. It isn't. Static bodies in Matter.js don't transfer momentum. The manual impulse hack is a proximity-based force disconnected from collision geometry. It will never feel like real pinball.

The comparator was right about one thing: scope is the enemy. But the response to scope pressure shouldn't be "keep the broken foundation and build on it." It should be either:

1. Fix the foundation first (try `updateVelocity: true`, or switch to Planck.js), then build
2. Redirect effort entirely to showcase.html, which is already working

Building 5 phases on top of broken flippers produces a pinball game where everything works except the one thing that makes pinball pinball.

## Unverified Claims

- Claim: "`Body.setAngle(body, angle, true)` exists and enables velocity inference" — Evidence quality: **CONFIRMED.** Matter.js 0.20.0 docs: "Sets the angle of the body. By default angular velocity is unchanged. If `updateVelocity` is `true` then angular velocity is inferred from the change in angle." Same parameter exists on `setPosition`. This is the cheapest possible fix — one boolean parameter.
- Claim: "Planck.js port would take 6-10 hours" — Evidence quality: MODERATE. Based on API similarity analysis and the 60-line demo, but real ports always surface unexpected issues.
- Claim: "The attractor pattern instability was purely from wrong parameter values" — Evidence quality: MODERATE. Round 1 research says PADDLE_PULL was 45x too high, but other instability factors (compound body jitter, constraint fighting) may also be present.

## Unstated Assumptions

- The comparator assumes "flippers move" = "flippers work." Moving and launching are different things.
- The 5-phase plan assumes Phase 1 (physics tuning) is independent of the flipper system. It's not — substep changes will change how the manual impulse hack behaves.
- "Radically simplify scope" assumes the remaining scope is the source of risk. The biggest risk is in code that's already written — the flipper system.
- The plan assumes 16 days of available time. It's 16 days with a working adult who has other commitments. Realistic available hours may be 15-25.

## Confidence in Critique

**Confident.**

The static-body momentum transfer issue is well-documented in Matter.js's own issue tracker and confirmed by the engine maintainer's responses. The Phaser forum thread shows multiple developers hitting exactly this wall. The h4k1m0u developer switching to Planck.js for this exact reason is independent confirmation. The Lu1ky approach (velocity from position delta) shows the manual impulse approach CAN work but requires more sophistication than a simple proximity check.

The showcase.html pivot question is judgment, not evidence — but the risk-adjusted calculus strongly favors putting most effort there.

## Recommended Decision Tree

Given the findings, here is the fastest path to a decision:

**Step 1 (30 minutes):** In the current codebase, change `Body.setAngle(body, newAngle)` to `Body.setAngle(body, newAngle, true)` and `Body.setPosition(body, pos)` to `Body.setPosition(body, pos, true)`. Remove the manual impulse hack. Test whether flippers now launch the ball with proper momentum transfer.

**If Step 1 works:** The comparator's plan becomes viable. Proceed with Phases 1-5 on Matter.js. The flipper problem was one boolean parameter away from solved.

**If Step 1 doesn't work (static bodies still don't transfer momentum even with updateVelocity):**
- **Step 2a (2 hours):** Try switching flippers to dynamic bodies with the `updateVelocity` approach. If dynamic bodies + setAngle + updateVelocity works, proceed with Matter.js.
- **Step 2b (if 2a fails):** Make the Planck.js decision. Budget 2 solid sessions (6-10 hours) for the port. Start from the official 60-line pinball demo.
- **Step 2c (parallel with any above):** Begin polishing showcase.html regardless. It's the safe deliverable.

**The one thing NOT to do:** Continue building features on top of the current flipper hack. Every hour spent on scoring, slingshots, and image layering with broken flippers is an hour that might need to be redone.
