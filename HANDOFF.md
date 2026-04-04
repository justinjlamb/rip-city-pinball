# Rip City Pinball — Session Handoff (Updated Mar 21, 2026)

## Who This Is For

**Alicia Lamb** — Justin's daughter. She's an intern at **Rip City Management** (the event management company that runs the **Moda Center** in Portland). She works in the **Booking & Events** department under her manager. The showcase is **April 7, 2026**.

## What She Does

Alicia processes every event that happens in the building — from the moment it's confirmed to the final settlement. She is NOT a Blazers employee. She works for the event management company that operates the venue.

**Critical framing** (she's sensitive about this): She does NOT book the big events (concerts, Blazer games). She processes the documentation, manages the calendar, and communicates information to all departments. She DOES book smaller events. The accurate framing: "I process every event that happens in this building."

**Her workflow:**
- Information flows in (booking requests, new show announcements, documents, add-on events, details forms, research)
- She enters it into **Momentus** (their internal event management system)
- She produces: Arena Calendar (Excel → Slack, 1st & 15th of month), Event Alerts (yellow = pending, green = confirmed), Internal Announcements, Department Notifications
- Post-event: she collects department info, compiles settlements, sends to Finance
- Booking & Events is the beginning AND end of the event lifecycle

**Event types she handles:** Concerts, Winterhawks games, Blazer games, conferences, internal meetings, camps, tours, private/external meetings, non-ticketed events (graduations, festivals, charity walks)

**Departments she communicates with (ALL of them, every time):** Guest Experience, Security, ESS/Conversions, Catering (Levy), Production, Box Office, Environmental Services (housekeeping), Facility Operations/Engineers

**Venues:** Moda Center, VMC (Veterans Memorial Coliseum), Weight Room

**Tools:** Momentus, Excel, Outlook, Slack, Word, Pollstar

**Her catchphrase / inside joke:** She constantly hounds people for "Details Forms"

## The Showcase Goal

She wants people to:
1. Learn what she does WHILE having fun (not be preached at)
2. Not be bored
3. Walk away understanding that nothing happens in the building without passing through her

She does NOT want:
- People doing her job (rejected the "event router" game concept)
- Overly Blazers-themed content (she works for the venue, not the team)
- Anything that overstates what she does

## What We're Building — TWO Things

### 1. Showcase Visualization (`showcase.html` — MOSTLY DONE)
An animated experience showing her as the central coordination point. Events flow in from the left, through her, out to all 8 departments on the right. Particles stream showing information flow. Runs continuously (no restart loop). Interactive — hover to highlight connections.

**Status:** Working well. Orbiting orbs removed. Runs infinitely. Lightweight enough to run all day on a laptop.

**Remaining:** Fine-tuning only.

### 2. Pinball Game (`index.html` — ACTIVE DEVELOPMENT)
A playable pinball game themed around the Moda Center. Uses pre-rendered Gemini image as the table background with invisible Matter.js physics bodies overlaid.

**Architecture:**
- Gemini-generated PNG = the table art (`table.png`, 1748×2432)
- Matter.js = physics engine
- Canvas = renders ONLY: ball, flippers, particles, score overlay
- Everything else is invisible physics aligned to the image
- Collision layer system for ramps (playfield, left_ramp, right_ramp, launcher)

**Current state (end of Apr 3 session):**
- Gemini-generated table art with themed elements: "BOOKING REQUESTS" red translucent ramp, "EVENT DETAILS FORM" marquee (multiball scoop), Slack/Excel/Outlook/Momentus bumpers ✓
- All visual overlays hidden (ramp, bumpers, scoop) — table image provides visuals, physics bodies are invisible ✓
- Bumper radius increased to 60px to match table art ✓
- Element positions aligned via element-editor.html to match new table art ✓
- Flippers, multiball, ramp animation, scoring all functional ✓
- Sound effects, attract mode, touch controls, debug mode all working ✓

**What needs fine-tuning next:**
1. **Image layering (depth illusion)** — Split table into background + foreground transparency so ball visually goes under the ramp during normal play (see "Next Up" section)
2. **Flipper positions** — May need minor adjustments to overlay the image flippers
3. **Physics body alignment** — Walls/curves need testing with gameplay
4. **Game over screen** — Currently plain white text
5. **Attract screen polish** — No Moda Center branding yet

### 3. Physics Editor (`physics-editor.html` — TOOL)
Drag-and-drop visual editor for positioning physics bodies on the table image. Supports walls, bumpers, targets, curves (bezier with 3 control points), and flippers. "Copy Code" exports coordinates as JS.

## Flipper System (IMPORTANT — hard-won)

The flipper system was rewritten from scratch after the attractor-based system proved unstable. **DO NOT go back to attractors/compound bodies/constraints.**

Current working system:
- Each flipper is a single `Bodies.rectangle`, marked `isStatic: true`
- `updateFlippers()` runs in the Matter.js `beforeUpdate` event
- Each frame, the flipper angle moves toward target (rest or active) at defined speed
- `positionFlipper(body, hinge, angle)` sets both angle AND position around the hinge point
- Left flipper: angle applied directly. Rest = 0.55 rad (5 o'clock), Active = -0.55 rad (1 o'clock)
- Right flipper: actual angle = `Math.PI - flipAngle` (mirrored). Rest = 7 o'clock, Active = 11 o'clock
- Ball gets a small upward impulse when flipper is actively swinging and ball is nearby

Constants to adjust:
```javascript
const FLIP_REST = 0.55;      // rest angle
const FLIP_ACTIVE = -0.55;   // active angle
const FLIP_UP_SPEED = 0.22;  // how fast flipper activates
const FLIP_DN_SPEED = 0.10;  // how fast flipper returns to rest
const LEFT_HINGE  = { x: 560,  y: 2200 };
const RIGHT_HINGE = { x: 1120, y: 2200 };
const PADDLE_LEN = 280;
const PADDLE_WIDTH = 32;
```

## Layer System

5 collision categories. Ball's mask changes when it enters trigger zones.

| Layer | Category | Color (debug) | What's on it |
|---|---|---|---|
| always | 0x0002 | cyan | Lower playfield walls, bowls, slings, outlanes, left ramp rails (double as playfield boundaries) |
| playfield | 0x0004 | yellow | Bumpers, Moda Center walls (112/113/126), Top Dome, Curve 124 |
| left_ramp | 0x0008 | orange | (no exclusive walls — left ramp rails are "always" since they double as playfield boundaries) |
| right_ramp | 0x0010 | pink | All "Right side ramp" curves and walls (elevated chrome rail) |
| launcher | 0x0020 | green | Launcher Inner/Outer walls and curves |

Ball masks:
- `playfield`: ALWAYS + PLAYFIELD (collides with everything except ramp-only and launcher-only walls)
- `left_ramp`: ALWAYS only (passes through bumpers and playfield-only walls)
- `right_ramp`: ALWAYS + RIGHT_RAMP (collides with ramp rails + lower playfield walls)
- `launcher`: ALWAYS + LAUNCHER

## Ramp Layer Map (from user's description)

### Left Ramp (Details Form)
**Left rail:** Wall 111 (entry) → Curve 108 → Wall 109 → Curve 115 (exit/dumps out)
**Right rail:** Wall 110 (entry) → Curve 106 → Curve 105 → Wall 107 → Curve 114 (exit/dumps out)
**Note:** These walls are layer "always" because they also serve as the left boundary of the playfield.

### Right Ramp
**Outer rail:** RR Outer Entry → RR Outer Top → RR Outer Mid → RR Outer Exit
**Inner rail:** RR Inner Entry → RR Inner Top → RR Inner Mid → RR Inner Exit
**Note:** These are layer "right_ramp" — elevated chrome rails, ball passes under them on playfield.

### Moda Center
**Entrance:** Between Wall 112 (Moda L) and Wall 113 (Moda R) — a scoop
**Boundary:** Wall 126 (Moda Outer) + Curve 124 (Moda Arc)
**Trigger:** Ball entering scoop → multiball (2 extra balls) → ejects onto right ramp

### Launcher
**Walls:** Launcher Inner + Launcher Outer (straight) + Launcher Inner Curve + Launcher Outer Curve
**One-way gate:** Ball switches from launcher to playfield when y < 400

## Debug Mode

**Shift+D** toggles debug overlay showing:
- All physics bodies with labels and layer tags
- Color-coded by layer (cyan/yellow/orange/pink/green)
- Trigger zones as dashed white rectangles with from→to labels
- Ball position, velocity, and current layer
- Layer legend with key bindings

**Layer filtering (while debug is on):**
- 1 = show only "always" layer
- 2 = show only "playfield" layer
- 3 = show only "left_ramp" layer
- 4 = show only "right_ramp" layer
- 5 = show only "launcher" layer
- 0 = show all layers

## Files

```
~/Developer/rip-city-pinball/
├── index.html          # Pinball game (Matter.js + table image overlay)
├── showcase.html       # Animated role visualization (mostly done)
├── alicia-role-map.html # Interactive force graph (earlier iteration)
├── physics-editor.html # Drag-and-drop physics body editor
├── table.png           # Current table image (copy of table-v2.png)
├── table-v1.png        # First Gemini table image (1728×2420)
├── table-v2.png        # Second Gemini table image (1748×2432, current)
└── HANDOFF.md          # This file
```

## Build Playbook

**THE definitive guide is at `docs/BUILD-PLAYBOOK.md`** — compiled from 2 rounds of deep research (14 agents). Follow it phase by phase. It has every code snippet, every tuning value, and the exact fix for the flipper impulse problem.

Quick summary: `Body.setAngle(body, angle, true)` — the `updateVelocity=true` parameter is the one-line fix that makes static flippers transfer real momentum to the ball. Then: positionIterations=100, ball restitution=0, speed clamp at 45, slingshots as triangle sensors, combo scoring, image layer splitting, ship after Phase 5.

## Next Up

1. **Image Layering (depth illusion)** — Split table into background (Layer 0) and foreground transparency (Layer 1, ramp only). Render order: background → ball → ramp overlay. When ball is in ramp animation, draw ball AFTER overlay so it appears on top. This makes the ball visually go under the chrome ramp during normal play. Need to generate a transparent PNG (1694×2376) with just the ramp isolated. Code change is small — sandwich the ball between two canvas drawImage calls, flip order when `rampAnimating` is true.

2. **Marquee sign** — "EVENT DETAILS FORM" retro theater marquee for the scoop area. In progress via Gemini image gen.

3. **Game over screen** — Currently plain white text. Could show final score more prominently, invite replay.

4. **Attract screen polish** — Plain white text on dark overlay. No Moda Center branding or showcase personality yet.

## Key Lessons

1. **Don't draw photorealistic surfaces with Canvas 2D** — use pre-rendered images
2. **The attractor-based flipper system is unstable** — use direct angle control with `Body.setAngle()` + `Body.setPosition()`. Static bodies repositioned each frame.
3. **Negative trapezoid slope in Matter.js causes instability** — don't use it
4. **Right flipper mirroring:** actual angle = `Math.PI - flipAngle`, NOT `-flipAngle`
5. **She is NOT a Blazers employee** — don't over-theme with Blazers branding
6. **"Add an event"** is a task/workflow, not an event type
7. **Image-based table art + invisible physics overlay = the professional approach**
8. **Layer system for ramps:** walls that serve as BOTH playfield boundaries AND ramp rails get category "always" so the ball collides with them regardless of layer state

## Pop Culture References (Aug 2025 → Mar 2026, her tenure)

Linkin Park (Sep 19), Stevie Nicks (Oct 1), Playboi Carti (Oct 5), Sleep Token (Oct 8), Lorde (Oct 21), Trans-Siberian Orchestra (Nov 23), Dave Chappelle (Dec 5), John Legend (Dec 7), John Mulaney NYE (Dec 31), Ghost (Feb 17), Cardi B (Feb 19), Monster Jam (Feb 27-Mar 1), Brandi Carlile (Mar 4), WWE (Mar 6), NCAA March Madness (Mar 19-21).

Bird on podium at Bernie Sanders rally (Mar 25, 2016, Moda Center) — "Put a Bird on It" campaign/meme.
