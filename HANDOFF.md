# Rip City Pinball — Handoff

## Showcase: April 7, 2026

**Live at:** https://rip-city-pinball.vercel.app
**Auto-deploys** on push to main via Vercel (Justin's personal account).

## Collaborators

- **Justin Lamb** (justinjlamb) — owner
- **Alicia VanderVoort-Walters** (aliciawalters101) — creator, GitHub collaborator with push access

## What This Is

A playable pinball game themed around the Moda Center, built for Alicia's intern showcase at Rip City Management. Uses a pre-rendered Gemini image as the table background with invisible Matter.js physics bodies overlaid.

## Who Alicia Is

Intern at **Rip City Management** (the event management company that runs the Moda Center). She works in the **Booking & Events** department. She is NOT a Blazers employee — she works for the venue, not the team.

**Her role:** She processes every event that happens in the building — from confirmation to final settlement. She enters events into Momentus, produces the Arena Calendar, sends Event Alerts and Department Notifications to all 8 departments.

**Her catchphrase:** She constantly hounds people for "Details Forms."

## Game Features

- Themed bumpers (Slack, Excel, Outlook, Momentus)
- Drop targets for 6 venue rooms (PDR, Rose Room, SCR, GP, Fountain, Weyerhaeuser)
- "Make It Rain" storm mode — triggers when all 6 rooms are booked (x2 multiplier, 20s, rain + spotlights + multiball)
- Multiball via "Event Details Form" scoop
- Ramp animation
- Leaderboard via Supabase (RLS enabled — anon key can read + insert only)
- Mobile support with touch flippers
- QR code on desktop left panel

## Files

```
v2.html              — THE game file (Vercel serves this via rewrite)
showcase.html        — Animated role visualization (runs on loop)
wall-data.json       — Physics wall coordinates
table-layer0.png     — Table background image
RipCityPinball-*.png — Bumper glow + drop target overlay assets
vercel.json          — Routing config
```

## Key Rules

1. **v2.html is the working file.** Not index.html.
2. **Must use localhost, not file://.** It fetches `wall-data.json` which fails on file:// (CORS). Use `http://localhost:8080/v2.html`.
3. **Backup before editing.** Copy to `v2-YYYY-MM-DD-pre-{change}.html` before touching.
4. **Verify after editing.** Open on localhost and confirm the game works before pushing.

## Leaderboard

- Supabase project: `damhvnkyfqsreevppfkf`
- Table: `pinball_scores`
- RLS enabled: SELECT + INSERT only via anon key. No delete/update from client.
- Clear leaderboard requires Supabase dashboard or service_role key.

## Flipper System (DO NOT CHANGE APPROACH)

Static `Bodies.rectangle` with `Body.setAngle()` + `Body.setPosition()` each frame. The `updateVelocity=true` parameter transfers momentum to the ball. Do NOT go back to attractors/compound bodies/constraints — that was tried and failed.

## Layer System

5 collision categories for ramps, playfield, and launcher. Ball's collision mask changes when entering trigger zones. See code comments for details.
