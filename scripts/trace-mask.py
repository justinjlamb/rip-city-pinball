#!/usr/bin/env python3
"""
Trace the black/white mask image to generate physics wall coordinates.

Reads table-mask.png (white=playable, black=wall), traces the boundary contour,
simplifies with Douglas-Peucker, smooths with Chaikin's corner-cutting,
and outputs wall-data.json.

Usage: python3 scripts/trace-mask.py [--epsilon 8] [--chaikin-passes 1]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage


# ── Moore Neighborhood Boundary Tracing ──────────────────────────

# 8-connected neighbors, clockwise starting from right
MOORE_DX = [1, 1, 0, -1, -1, -1, 0, 1]
MOORE_DY = [0, 1, 1, 1, 0, -1, -1, -1]


def moore_trace(mask: np.ndarray) -> list[tuple[int, int]]:
    """
    Trace the outer boundary of a binary mask using Moore neighborhood tracing.
    Returns ordered (x, y) boundary points, clockwise.
    """
    h, w = mask.shape

    # Find starting pixel: topmost, then leftmost white pixel
    for y in range(h):
        for x in range(w):
            if mask[y, x]:
                start = (x, y)
                break
        else:
            continue
        break
    else:
        return []

    contour = [start]
    current = start
    # Start searching from the left (direction 4) since we entered from above/left
    backtrack_dir = 4

    max_steps = h * w  # safety limit
    for _ in range(max_steps):
        # Search clockwise from the direction we came from
        search_start = (backtrack_dir + 1) % 8
        found = False

        for i in range(8):
            d = (search_start + i) % 8
            nx = current[0] + MOORE_DX[d]
            ny = current[1] + MOORE_DY[d]

            if 0 <= nx < w and 0 <= ny < h and mask[ny, nx]:
                if (nx, ny) == start and len(contour) > 2:
                    # Closed the loop
                    return contour

                current = (nx, ny)
                contour.append(current)
                # Backtrack direction is opposite of the direction we moved
                backtrack_dir = (d + 4) % 8
                found = True
                break

        if not found:
            break  # isolated pixel

    return contour


# ── Douglas-Peucker Simplification ───────────────────────────────

def douglas_peucker(points: list[tuple[int, int]], epsilon: float) -> list[tuple[int, int]]:
    """Simplify a polyline using Douglas-Peucker algorithm."""
    if len(points) <= 2:
        return list(points)

    # Find the point with maximum distance from the line (start → end)
    start = np.array(points[0], dtype=float)
    end = np.array(points[-1], dtype=float)
    line_vec = end - start
    line_len = np.linalg.norm(line_vec)

    if line_len < 1e-10:
        # Start and end are the same point — keep the farthest point
        max_dist = 0.0
        max_idx = 0
        for i in range(1, len(points) - 1):
            dist = np.linalg.norm(np.array(points[i], dtype=float) - start)
            if dist > max_dist:
                max_dist = dist
                max_idx = i
        if max_dist > epsilon:
            return [points[0], points[max_idx], points[-1]]
        return [points[0], points[-1]]

    line_unit = line_vec / line_len

    max_dist = 0.0
    max_idx = 0
    for i in range(1, len(points) - 1):
        pt = np.array(points[i], dtype=float)
        vec = pt - start
        proj = np.dot(vec, line_unit)
        proj = max(0.0, min(line_len, proj))
        closest = start + proj * line_unit
        dist = np.linalg.norm(pt - closest)
        if dist > max_dist:
            max_dist = dist
            max_idx = i

    if max_dist > epsilon:
        left = douglas_peucker(points[: max_idx + 1], epsilon)
        right = douglas_peucker(points[max_idx:], epsilon)
        return left[:-1] + right
    else:
        return [points[0], points[-1]]


# ── Chaikin's Corner-Cutting ─────────────────────────────────────

def chaikin_smooth(
    points: list[tuple[int, int]],
    passes: int = 1,
    protect_indices: set[int] | None = None,
) -> list[tuple[float, float]]:
    """
    Smooth a closed polyline using Chaikin's corner-cutting algorithm.
    Points at protect_indices are kept unchanged (e.g., drain gap vertices).
    """
    pts = [(float(x), float(y)) for x, y in points]

    for _ in range(passes):
        new_pts: list[tuple[float, float]] = []
        n = len(pts)
        for i in range(n):
            p0 = pts[i]
            p1 = pts[(i + 1) % n]

            if protect_indices and i in protect_indices:
                new_pts.append(p0)
            else:
                # Q = 3/4 * P_i + 1/4 * P_{i+1}
                q = (0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1])
                # R = 1/4 * P_i + 3/4 * P_{i+1}
                r = (0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1])
                new_pts.append(q)
                new_pts.append(r)

        pts = new_pts
        # After smoothing, protected indices shift — clear them for subsequent passes
        protect_indices = None

    return pts


# ── Feature Detection ────────────────────────────────────────────

def find_drain_gap(
    points: list[tuple[float, float]],
    paddle_len: float = 230.0,
    rest_angle: float = 0.5,
    target_drain_gap: float = 100.0,
) -> tuple[dict, dict]:
    """
    Find flipper hinge positions from the drain funnel shape.

    Strategy: find the bottommost point (drain center), then search upward
    along both sides of the contour for the y-level where the funnel width
    matches 2 * paddle_projection + target_drain_gap.
    """
    # Find bottommost point (drain center)
    bottom_idx = max(range(len(points)), key=lambda i: points[i][1])
    bottom_pt = points[bottom_idx]

    # Estimate center x from the horizontal midpoint of all points
    all_x = [p[0] for p in points]
    center_x = (min(all_x) + max(all_x)) / 2
    all_y = [p[1] for p in points]
    y_max = max(all_y)

    # Target funnel width for flipper placement
    paddle_proj = paddle_len * np.cos(rest_angle)
    target_width = 2 * paddle_proj + target_drain_gap

    # Collect bottom-area points, split by side of center
    y_threshold = y_max * 0.85  # bottom 15%
    left_side = [p for p in points if p[1] > y_threshold and p[0] < center_x]
    right_side = [p for p in points if p[1] > y_threshold and p[0] > center_x]

    # Find the pair at similar y-levels with width closest to target
    best_left = None
    best_right = None
    best_diff = float("inf")

    for lp in left_side:
        for rp in right_side:
            if abs(lp[1] - rp[1]) > 60:
                continue
            width = rp[0] - lp[0]
            if width < 200:  # too narrow, skip
                continue
            diff = abs(width - target_width)
            if diff < best_diff:
                best_diff = diff
                best_left = lp
                best_right = rp

    if best_left is None or best_right is None:
        # Fallback: pick the two points in the bottom area closest to target width
        best_left = (center_x - target_width / 2, y_max - 80)
        best_right = (center_x + target_width / 2, y_max - 80)

    return (
        {"x": round(best_left[0]), "y": round(best_left[1])},
        {"x": round(best_right[0]), "y": round(best_right[1])},
    )


def find_launcher_center(points: list[tuple[float, float]], mask_w: int) -> dict:
    """
    Find the ball start position in the launcher channel.
    The launcher is the rightmost passage in the middle heights.
    """
    # Find points where x > 70% of image width and y is in the middle 60%
    all_y = [p[1] for p in points]
    y_min, y_max = min(all_y), max(all_y)
    y_mid_low = y_min + (y_max - y_min) * 0.3
    y_mid_high = y_min + (y_max - y_min) * 0.7
    x_threshold = mask_w * 0.70

    right_points = [p for p in points if p[0] > x_threshold and y_mid_low < p[1] < y_mid_high]

    if not right_points:
        # Fallback
        return {"x": round(mask_w * 0.9), "y": round((y_min + y_max) / 2)}

    # The launcher channel center is the average x of rightmost points,
    # at the vertical midpoint
    avg_x = sum(p[0] for p in right_points) / len(right_points)
    avg_y = sum(p[1] for p in right_points) / len(right_points)

    return {"x": round(avg_x), "y": round(avg_y + (y_max - avg_y) * 0.3)}


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Trace mask to generate wall data")
    parser.add_argument("--epsilon", type=float, default=8.0, help="Douglas-Peucker epsilon (default: 8)")
    parser.add_argument("--chaikin-passes", type=int, default=1, help="Chaikin smoothing passes (default: 1)")
    parser.add_argument("--mask", type=str, default=None, help="Path to mask image")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    args = parser.parse_args()

    # Resolve paths
    project_dir = Path(__file__).parent.parent
    mask_path = Path(args.mask) if args.mask else project_dir / "table-mask.png"
    output_path = Path(args.output) if args.output else project_dir / "wall-data.json"

    # Load mask
    print(f"Loading mask: {mask_path}")
    img = Image.open(mask_path).convert("L")
    mask = np.array(img) > 128
    h, w = mask.shape
    print(f"  Size: {w}x{h}")
    print(f"  White pixels: {np.sum(mask):,}")

    # Trace contour
    print("Tracing boundary (Moore neighborhood)...")
    raw_contour = moore_trace(mask)
    print(f"  Raw boundary: {len(raw_contour):,} points")

    if len(raw_contour) < 10:
        print("ERROR: Contour too small. Check mask image.", file=sys.stderr)
        sys.exit(1)

    # Simplify
    print(f"Simplifying (Douglas-Peucker, epsilon={args.epsilon})...")
    sys.setrecursionlimit(max(sys.getrecursionlimit(), len(raw_contour) + 100))
    simplified = douglas_peucker(raw_contour, args.epsilon)
    print(f"  Simplified: {len(simplified)} points")

    # Find drain gap BEFORE smoothing (need sharp corners for detection)
    flipper_left, flipper_right = find_drain_gap([(float(x), float(y)) for x, y in simplified])
    print(f"  Drain gap: left=({flipper_left['x']}, {flipper_left['y']}), right=({flipper_right['x']}, {flipper_right['y']})")

    # Find indices of drain gap points to protect during smoothing
    protect = set()
    for i, (px, py) in enumerate(simplified):
        if (round(px) == flipper_left["x"] and round(py) == flipper_left["y"]) or (
            round(px) == flipper_right["x"] and round(py) == flipper_right["y"]
        ):
            protect.add(i)

    # Smooth
    print(f"Smoothing (Chaikin, {args.chaikin_passes} pass(es))...")
    smoothed = chaikin_smooth(simplified, passes=args.chaikin_passes, protect_indices=protect)
    print(f"  Smoothed: {len(smoothed)} points")

    # Find launcher center
    ball_start = find_launcher_center(smoothed, w)
    print(f"  Ball start: ({ball_start['x']}, {ball_start['y']})")

    # Generate wall segments (closed contour)
    walls = []
    n = len(smoothed)
    for i in range(n):
        x1, y1 = smoothed[i]
        x2, y2 = smoothed[(i + 1) % n]
        walls.append([round(x1), round(y1), round(x2), round(y2)])

    # Build output
    output = {
        "meta": {
            "source": str(mask_path.name),
            "dimensions": [w, h],
            "epsilon": args.epsilon,
            "chaikinPasses": args.chaikin_passes,
            "rawPoints": len(raw_contour),
            "simplifiedPoints": len(simplified),
            "smoothedPoints": len(smoothed),
            "wallSegments": len(walls),
        },
        "walls": walls,
        "vertices": [[round(x), round(y)] for x, y in smoothed],
        "flipperLeft": flipper_left,
        "flipperRight": flipper_right,
        "ballStart": ball_start,
    }

    # Write
    print(f"\nWriting {output_path}...")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"  {len(walls)} wall segments")
    print(f"  Flipper L: ({flipper_left['x']}, {flipper_left['y']})")
    print(f"  Flipper R: ({flipper_right['x']}, {flipper_right['y']})")
    print(f"  Ball start: ({ball_start['x']}, {ball_start['y']})")
    print("Done.")


if __name__ == "__main__":
    main()
