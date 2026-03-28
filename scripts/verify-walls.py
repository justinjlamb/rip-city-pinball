#!/usr/bin/env python3
"""
Render wall segments overlaid on the mask and table images for visual verification.

Usage: python3 scripts/verify-walls.py
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


def main():
    project_dir = Path(__file__).parent.parent
    data_path = project_dir / "wall-data.json"
    mask_path = project_dir / "table-mask.png"
    table_path = project_dir / "table-layer0.png"

    with open(data_path) as f:
        data = json.load(f)

    walls = data["walls"]
    vertices = data["vertices"]
    fl = data["flipperLeft"]
    fr = data["flipperRight"]
    ball = data["ballStart"]
    meta = data["meta"]

    print(f"Wall data: {meta['wallSegments']} segments, epsilon={meta['epsilon']}")

    # Render on mask
    mask_img = Image.open(mask_path).convert("RGB")
    draw_overlay(mask_img, walls, vertices, fl, fr, ball)
    mask_out = project_dir / "wall-overlay-mask.png"
    mask_img.save(mask_out)
    print(f"Saved: {mask_out}")

    # Render on table image
    table_img = Image.open(table_path).convert("RGB")
    draw_overlay(table_img, walls, vertices, fl, fr, ball)
    table_out = project_dir / "wall-overlay-table.png"
    table_img.save(table_out)
    print(f"Saved: {table_out}")


def draw_overlay(
    img: Image.Image,
    walls: list[list[int]],
    vertices: list[list[int]],
    fl: dict,
    fr: dict,
    ball: dict,
):
    draw = ImageDraw.Draw(img)

    # Draw wall segments as colored lines
    wall_color = (0, 255, 255)  # cyan
    wall_width = 3
    for x1, y1, x2, y2 in walls:
        draw.line([(x1, y1), (x2, y2)], fill=wall_color, width=wall_width)

    # Draw vertex circles (corner gap bodies)
    vertex_color = (255, 255, 0)  # yellow
    vertex_r = 5
    for x, y in vertices:
        draw.ellipse(
            [(x - vertex_r, y - vertex_r), (x + vertex_r, y + vertex_r)],
            fill=vertex_color,
            outline=vertex_color,
        )

    # Draw flipper positions
    flipper_color = (255, 0, 0)  # red
    flipper_r = 12
    for pos in [fl, fr]:
        x, y = pos["x"], pos["y"]
        draw.ellipse(
            [(x - flipper_r, y - flipper_r), (x + flipper_r, y + flipper_r)],
            fill=flipper_color,
            outline=(255, 255, 255),
            width=2,
        )
        label = "L" if pos == fl else "R"
        draw.text((x - 4, y - 8), label, fill=(255, 255, 255))

    # Draw ball start position
    ball_color = (255, 128, 0)  # orange
    ball_r = 15
    bx, by = ball["x"], ball["y"]
    draw.ellipse(
        [(bx - ball_r, by - ball_r), (bx + ball_r, by + ball_r)],
        outline=ball_color,
        width=3,
    )
    draw.text((bx - 12, by - 8), "BALL", fill=ball_color)


if __name__ == "__main__":
    main()
