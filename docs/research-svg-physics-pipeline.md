# SVG Physics Pipeline Research
*Research scratchpad — Mar 21, 2026*

## Source Log

- [pinball-schminball src/services/svg-loader.ts](https://github.com/igorski/pinball-schminball/blob/master/src/services/svg-loader.ts) - Complete SVG-to-Matter.js pipeline. Uses `Matter.Svg.pathToVertices(path, 30)` + poly-decomp + pathseg polyfill. Caches parsed vertices. (credibility: high — working shipped game)
- [pinball-schminball src/model/physics/engine.ts](https://github.com/igorski/pinball-schminball/blob/master/src/model/physics/engine.ts) - Creates physics body from SVG vertices via `Matter.Bodies.fromVertices(centerX, centerY, vertices, { isStatic: true }, true)`. The `true` at end = flagInternal. Position uses `left + width/2, top + height/2` as center point. (credibility: high)
- [pinball-schminball table1.ts](https://github.com/igorski/pinball-schminball/blob/master/src/definitions/tables/table1.ts) - Table def schema with body SVG source + bounding box offsets (left/top/width/height). Table1 body has left: -101, top: -845 as offsets. (credibility: high)
- [Matter.Svg docs](https://brm.io/matter-js/docs/classes/Svg.html) - `pathToVertices(path, sampleLength=15)` only supports `<path>` elements. Complex paths with holes not fully supported. Needs pathseg polyfill. (credibility: high — official docs)
- [Matter.Bodies docs](https://brm.io/matter-js/docs/classes/Bodies.html) - `fromVertices(x, y, vertexSets, options, flagInternal, removeCollinear, minimumArea, removeDuplicatePoints)`. Needs poly-decomp via `Common.setDecomp()`. Falls back to convex hull without it. (credibility: high — official docs)
- [Coder's Block pinball tutorial](https://codersblock.com/blog/javascript-physics-with-matter-js/) - Used Illustrator to trace pinball boundaries. Export SVG, extract polygon points, feed to `Vertices.fromPath()` then `Bodies.fromVertices()`. Dome shape needed 20 edges. (credibility: high — shipped demo)
- [PhysicsEditor tutorial](https://www.codeandweb.com/physicseditor/tutorials/how-to-create-physics-shapes-for-phaser-3-and-matterjs) - Paid tool ($39.99). Auto-traces sprites. Exports JSON for Phaser/Matter.js. Has shape tracer. (credibility: medium — vendor docs)
- [poly-decomp npm](https://www.npmjs.com/package/poly-decomp) - Decomposes 2D concave polygons into convex pieces. Counter-clockwise winding required. Two algorithms: quickDecomp (fast) and decomp (optimal). (credibility: high — library docs)
- [matter-js issue #1007](https://github.com/liabru/matter-js/issues/1007) - Bodies.fromVertices reorients vertices around center of mass, not geometric center. Causes position offset for irregular polygons. Workaround: manual offset tuning or Body.setCentre. (credibility: high — library maintainer confirmed behavior)
- [matter-js issue #827](https://github.com/liabru/matter-js/issues/827) - Irregular polygon positioning drift. Shows Vertices.centre() calculates center of mass, not bounding box center. Includes code for geometric center calculation as alternative. (credibility: high — reproducible issue with code)

## Working Thesis

### How pinball-schminball's SVG Pipeline Works

**The complete chain:**

1. **SVG files** contain `<path>` elements with standard SVG path data (cubic beziers, lines, arcs — all standard `d=""` commands). The SVGs use the same pixel dimensions as the table (800x2441 for table1).

2. **pathseg polyfill** (`pathseg.js` v1.2.1) is loaded as a global script BEFORE any SVG parsing. It polyfills `SVGPathSeg` which modern browsers removed. Matter.Svg.pathToVertices internally uses `getTotalLength()` and `getPointAtLength()` on SVGPathElement, which need pathseg to work with path commands.

3. **svg-loader.ts** fetches the SVG file, parses it with DOMParser, queries all `<path>` elements, then maps each path through `Matter.Svg.pathToVertices(path, 30)`. The `30` is the sample length — it samples a point every 30 pixels along the path curve. Lower = more vertices = more precise but slower.

4. **poly-decomp** is registered via `Matter.Common.setDecomp(PolyDecomp)` at module load time. This enables `Bodies.fromVertices` to automatically decompose concave paths into convex sub-polygons.

5. **engine.ts** creates the body: `Matter.Bodies.fromVertices(left + width/2, top + height/2, bodyVertices, { isStatic: true }, true)`. The position is the CENTER of the bounding box, not the top-left. The `true` flag marks internal edges so they don't cause false collisions at decomposition seams.

6. **Positioning offsets**: The `body` property in the table definition has `left`, `top`, `width`, `height`. These act as a bounding box that positions the SVG body in world space. Table1's body has `left: -101, top: -845` — negative offsets mean the SVG's coordinate origin is offset from the table's (0,0). This is how you align the SVG collision shape with the background PNG.

### Table Definition Architecture

The `TableDef` type organizes a table into:
- `body: ShapeDef` — main table outline (walls, lanes, gutters) as ONE SVG file + position offset
- `reflectors: ShapeDef[]` — slingshot/reflector shapes, each its own SVG + position
- `rects: ObjectDef[]` — simple rectangular static bodies (walls, blockers, guide rails)
- `bumpers: ObjectDef[]` — circular bumper positions
- `flippers: FlipperDef[]` — flipper positions + angles
- `poppers: PopperDef[]` — ball launcher + kick mechanisms
- `triggerGroups: TriggerDef[]` — scoring zones (sensors + physical targets)

Key insight: **They use SVG only for complex curved shapes** (table outline, reflectors). Simple rectangular walls and blockers are still defined as `rects` with manual coordinates. This is practical — don't SVG-trace everything, only what needs curves.

### What Matter.Svg.pathToVertices Actually Supports

- Only `<path>` elements (not `<polygon>`, `<polyline>`, `<rect>`, `<circle>`, `<ellipse>`)
- Uses SVGPathElement's `getTotalLength()` and `getPointAtLength()` browser APIs
- Samples points at regular intervals along the path (controlled by sampleLength parameter)
- Works with all standard path commands (M, L, C, Q, A, Z etc.) because it uses the browser's native path API
- Does NOT support paths with holes (compound paths with multiple subpaths may produce unexpected results)
- The pathseg polyfill is REQUIRED — browsers removed SVGPathSeg API but Matter.js still depends on it

### Required Dependencies

```
npm install matter-js pathseg poly-decomp
```

- `matter-js` ^0.19.0 (pinball-schminball uses this)
- `pathseg` ^1.2.1 — polyfill for SVGPathSeg API
- `poly-decomp` ^0.3.0 — concave polygon decomposition

### Figma to Matter.js Workflow

1. Import `table.png` (1748x2432) as background in Figma
2. Create a new layer above it
3. Use the Pen tool to trace physics boundaries as paths
4. Keep all paths as `<path>` elements (Figma's default for pen tool)
5. The SVG viewBox should match your table dimensions (1748x2432)
6. Export as SVG — Figma puts origin at top-left by default, which matches Matter.js
7. IMPORTANT: Figma may use transforms on groups — flatten/outline strokes before export
8. Each distinct collision region can be a separate `<path>` in the same SVG
9. `pathToVertices` will be called on each `<path>` independently, then all are combined into one body via `fromVertices`

### PhysicsEditor Assessment

- Paid tool ($39.99 one-time)
- Auto-traces from transparency (good for sprites, less useful for our pre-rendered table)
- Exports JSON, not SVG — different pipeline
- Primarily designed for Phaser integration
- **Verdict: Not worth it for our use case.** We have a single large table image, not sprite sheets. Figma/Illustrator trace is more appropriate and free.

### Coordinate System Alignment

The critical alignment problem: SVG vertices are in SVG coordinate space, but `Bodies.fromVertices` positions the body at a CENTER point in world space.

Pinball-schminball's solution:
- SVG viewBox matches table pixel dimensions
- `body.left` and `body.top` are OFFSETS (can be negative)
- Body center = `(left + width/2, top + height/2)`
- The offsets compensate for any difference between SVG coordinate origin and table origin

For our table (1748x2432):
- SVG viewBox should be `0 0 1748 2432`
- If SVG paths trace exactly on top of the PNG at 1:1, then `left: 0, top: 0, width: 1748, height: 2432`
- Body center would be `(874, 1216)` — the middle of the table
- If alignment is off, adjust `left` and `top` offsets until physics match visuals

### CRITICAL GOTCHA: Center-of-Mass Offset

`Bodies.fromVertices(x, y, vertices)` does NOT place the body so that vertex coordinates map 1:1 to world coordinates. Matter.js internally reorients vertices around the center of mass (not the geometric/bounding-box center). For irregular shapes, this can shift the body several pixels from where you expect.

**Why pinball-schminball's approach works despite this:** They pass the bounding box center as x,y AND the negative left/top offsets compensate for any drift. The offsets in table1 (`left: -101, top: -845`) are suspiciously large for an 800px table, likely because they were manually tuned to correct for this exact center-of-mass shift.

**Our workaround options:**
1. **Manual offset tuning** (what pinball-schminball does) -- use the debug wireframe overlay, adjust left/top until alignment is pixel-perfect. Fastest for a single table.
2. **Programmatic correction** -- after creating the body, compute the offset between the requested position and `body.position`, then use `Body.setCentre(body, offset, true)` or `Body.setPosition` to correct.
3. **Pre-correct in SVG** -- if the SVG is traced at 1:1 scale on top of the PNG, the offset will be consistent and can be measured once.

**For static bodies (our case), option 1 is fine.** The body never moves, so tuning the offset once is sufficient. But know that the first attempt WILL be misaligned and you MUST use the wireframe debug overlay to correct it.

## Open Questions

- ~~How does the pathseg polyfill interact with modern bundlers (Vite)?~~ ANSWERED: pinball-schminball loads it via `tiny-script-loader` as a global script, not as an ES module import. This avoids bundler issues.
- ~~Does sampleLength of 30 give enough precision for our 1748px-wide table?~~ ANSWERED: Their table is 800px wide and uses 30. Our table is ~2.2x wider, so we should use ~15 for equivalent precision, or even 10 for tighter curves.
- ~~Center-of-mass offset causing alignment drift?~~ ANSWERED: Known Matter.js behavior. Manual offset tuning via wireframe overlay is the pragmatic fix for static bodies.
- What's the performance impact of many vertices on mobile? (Not critical for MVP)
- Should we split into multiple SVGs (walls, ramps, gutters) or one big SVG? Pinball-schminball uses one SVG for the main body + separate SVGs for reflectors. We should follow this pattern.

## Confidence

**Confident.** All core questions answered with primary source code reading + official documentation. The pipeline is well-proven by pinball-schminball (shipped game using exact same architecture as ours).

---

## Complete Pipeline Guide: table.png to Matter.js Physics Bodies

### Step 0: Install Dependencies

```bash
npm install pathseg poly-decomp
# matter-js should already be installed
```

### Step 1: Trace Boundaries in Figma

1. Create a new Figma file at 1748x2432 pixels (matching table.png)
2. Import `table.png` as a background layer, locked
3. Create a new layer called "Physics"
4. Use the **Pen tool** to trace the main table outline:
   - Left wall, right wall, bottom drain, launch lane
   - Follow the inner edges where the ball actually bounces
   - Close each path (critical — open paths produce weird physics)
5. Trace additional shapes separately:
   - Each ramp entrance/exit as its own path
   - Slingshot triangles as their own paths
   - Any curved guides or rails
6. DO NOT trace: bumpers (use circles), flippers (use rectangles), straight walls (use rectangles)
7. Only use `<path>` elements — no rectangles, circles, or other SVG primitives

### Step 2: Export SVG from Figma

1. Select only the "Physics" layer contents
2. File > Export > SVG
3. Settings:
   - Include "id" attribute: ON (helps debugging)
   - Outline text: ON (if any)
   - Flatten transforms: ON (critical — removes nested transforms)
4. Open the exported SVG and verify:
   - `viewBox="0 0 1748 2432"` matches table dimensions
   - All shapes are `<path>` elements
   - No `<g transform="...">` wrapping the paths (flatten if present)
   - No `<clipPath>` or `<mask>` elements

### Step 3: Set Up SVG Loader (Adapted from pinball-schminball)

```javascript
import Matter from 'matter-js';
import 'pathseg';  // polyfill — must load before SVG parsing
import decomp from 'poly-decomp';

// Register poly-decomp for concave shape handling
Matter.Common.setDecomp(decomp);

// Cache parsed vertices
const vertexCache = new Map();

export async function loadVertices(svgUrl) {
  if (vertexCache.has(svgUrl)) {
    return vertexCache.get(svgUrl);
  }

  const response = await fetch(svgUrl);
  const svgText = await response.text();
  const parser = new DOMParser();
  const svgDoc = parser.parseFromString(svgText, 'image/svg+xml');

  // Extract all <path> elements and convert to vertices
  const paths = Array.from(svgDoc.querySelectorAll('path'));
  const vertices = paths.map(path =>
    Matter.Svg.pathToVertices(path, 15)  // 15 = sample every 15px (good for 1748px table)
  );

  vertexCache.set(svgUrl, vertices);
  return vertices;
}
```

### Step 4: Create Physics Body from Vertices

```javascript
export async function createTableBody(engine, svgUrl, bounds) {
  const vertices = await loadVertices(svgUrl);

  // Position at center of bounding box
  const centerX = bounds.left + bounds.width / 2;
  const centerY = bounds.top + bounds.height / 2;

  const body = Matter.Bodies.fromVertices(
    centerX, centerY,
    vertices,
    {
      isStatic: true,
      friction: 0,
      restitution: 0.3,  // outer walls: low bounce
      render: {
        visible: false,     // hide in production (SVG = invisible collision)
        // visible: true,   // show wireframe for debugging
        strokeStyle: '#00ff00',
        lineWidth: 1
      }
    },
    true,   // flagInternal — prevents false collisions at decomposition seams
    0.01,   // removeCollinear threshold
    10,     // minimumArea — removes tiny decomposition artifacts
    0.01    // removeDuplicatePoints threshold
  );

  Matter.Composite.add(engine.world, body);
  return body;
}

// Usage:
const tableBody = await createTableBody(engine, '/assets/table-outline.svg', {
  left: 0,    // adjust these offsets if SVG doesn't align with PNG
  top: 0,
  width: 1748,
  height: 2432
});
```

### Step 5: Debug Alignment

```javascript
// Enable Matter.js debug renderer overlaid on your canvas
const render = Matter.Render.create({
  element: document.body,
  engine: engine,
  options: {
    width: 1748,
    height: 2432,
    wireframes: true,
    showAngleIndicator: true,
    showCollisions: true,
    background: 'transparent'  // see through to PNG below
  }
});

// Position the debug canvas exactly over your table image
Object.assign(render.canvas.style, {
  position: 'absolute',
  top: '0',
  left: '0',
  opacity: '0.5',      // semi-transparent to see both
  pointerEvents: 'none', // don't block input
  zIndex: '999'
});

Matter.Render.run(render);
```

### Step 6: Iterate on Alignment

If the physics wireframe doesn't line up with the PNG:
1. Adjust `bounds.left` and `bounds.top` (negative values shift the body left/up)
2. Check if Figma added transforms — flatten them
3. Verify the SVG viewBox matches 1748x2432
4. Try different `sampleLength` values (lower = more precise curves, higher = fewer vertices)

### Step 7: Integrate with Existing Game

Replace the manually-positioned rectangles from the drag-and-drop editor with the SVG body. Keep simple rectangular walls as `Matter.Bodies.rectangle()` — only use SVG for complex curved shapes.

```javascript
// Table definition (adapted from pinball-schminball pattern)
const TABLE = {
  width: 1748,
  height: 2432,
  background: '/assets/table.png',
  body: {
    source: '/assets/table-outline.svg',
    left: 0,
    top: 0,
    width: 1748,
    height: 2432
  },
  // Keep these as simple shapes (no SVG needed)
  rects: [
    { left: 0, top: 0, width: 1748, height: 20, visible: false },      // top wall
    { left: -20, top: 0, width: 40, height: 2432, visible: false },     // left wall
    { left: 1728, top: 0, width: 40, height: 2432, visible: false },    // right wall
  ],
  flippers: [ /* ... */ ],
  bumpers: [ /* ... */ ],
  // ... etc
};
```

### Gotchas and Tips

1. **pathseg MUST load before any SVG parsing.** Load it as a side-effect import at the top of your entry file, or via a script tag in index.html.

2. **poly-decomp MUST be registered before `fromVertices`.** Call `Matter.Common.setDecomp(decomp)` once at startup. Without it, concave shapes silently fall back to convex hull (ball clips through concave areas).

3. **Close all paths.** An open path (no Z command at end) may not create a valid collision body. In Figma, always close paths by clicking back on the starting point.

4. **One SVG, multiple paths = one compound body.** All `<path>` elements in a single SVG become vertex sets in one body. This is correct for the main table outline. Use separate SVGs only for things that need separate physics properties (like reflectors with different restitution).

5. **sampleLength tuning:** Start with 15 for a 1748px table. If curves feel jaggy, try 10. If performance suffers (many vertices), try 20. The Coder's Block pinball used ~1 for very smooth curves, but that creates many more vertices.

6. **Negative offsets are normal.** If your SVG has whitespace or its coordinate origin doesn't match the table origin, use negative `left`/`top` values. Pinball-schminball table1 uses `left: -101, top: -845`.

7. **Debug with wireframe overlay.** Always verify alignment visually before removing the debug renderer. A 5px misalignment is invisible in code but obvious when the ball clips through a wall.

8. **flagInternal = true.** Always pass this when creating compound bodies from decomposed concave shapes. It prevents internal edges (where convex sub-polygons meet) from triggering false collisions.

9. **CENTER-OF-MASS OFFSET.** `Bodies.fromVertices` internally reorients vertices around the center of mass, NOT the geometric center. Your first attempt WILL be misaligned. Use the wireframe debug overlay (Step 5) and adjust `bounds.left`/`bounds.top` until the green wireframe lines up with the PNG edges. This is a known Matter.js behavior (GitHub issues #1007, #827), not a bug in your SVG. For static bodies, manual offset tuning is the simplest fix.

10. **Winding direction matters for poly-decomp.** poly-decomp requires counter-clockwise winding. If decomposition fails silently (body falls back to convex hull), try reversing the path direction in Figma (right-click path > Reverse path direction) or programmatically reverse the vertices array.
