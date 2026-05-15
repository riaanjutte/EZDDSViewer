"""Generate icon.ico for EZ DDS Viewer."""
from PIL import Image, ImageDraw
import math


def create_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    r = max(3, size // 6)
    pad = max(1, size // 20)

    # Background — dark charcoal
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=(38, 38, 44, 255))

    # Four inner quadrants, inset from edges
    inner_pad = max(2, size // 8)
    x0, y0 = inner_pad, inner_pad
    x1, y1 = size - inner_pad, size - inner_pad
    mid_x = (x0 + x1) // 2
    mid_y = (y0 + y1) // 2
    gap = max(1, size // 40)

    # Top-left: warm red-orange (aircraft livery)
    _draw_quad(draw, x0, y0, mid_x - gap, mid_y - gap,
               [(196, 80,  54), (220, 110, 60)], size, "tl")

    # Top-right: steel blue (sky / shadow)
    _draw_quad(draw, mid_x + gap, y0, x1, mid_y - gap,
               [(54, 110, 196), (80, 150, 220)], size, "tr")

    # Bottom-left: olive green (camo)
    _draw_quad(draw, x0, mid_y + gap, mid_x - gap, y1,
               [(72, 128, 72), (100, 160, 80)], size, "bl")

    # Bottom-right: checkerboard (transparency / alpha)
    _draw_checker(draw, mid_x + gap, mid_y + gap, x1, y1)

    # Outer glow border — bright cyan
    bw = max(1, size // 40)
    draw.rounded_rectangle([0, 0, size - 1, size - 1],
                            radius=r, outline=(64, 200, 255, 255), width=bw)

    # Inner thin border — slightly lighter bg
    draw.rounded_rectangle([bw, bw, size - 1 - bw, size - 1 - bw],
                            radius=max(1, r - bw),
                            outline=(60, 62, 72, 255), width=max(1, bw // 2))

    return img


def _draw_quad(draw, x0, y0, x1, y1, colors, size, corner):
    """Fill a quadrant with a simple two-tone diagonal gradient."""
    c0 = colors[0]
    c1 = colors[1]
    w = x1 - x0
    h = y1 - y0
    if w <= 0 or h <= 0:
        return
    # Draw as gradient by scanline (approximate with rectangles at larger sizes)
    steps = max(2, min(h, 32))
    for i in range(steps):
        t = i / (steps - 1)
        r = int(c0[0] + t * (c1[0] - c0[0]))
        g = int(c0[1] + t * (c1[1] - c0[1]))
        b = int(c0[2] + t * (c1[2] - c0[2]))
        sy = y0 + i * h // steps
        ey = y0 + (i + 1) * h // steps
        draw.rectangle([x0, sy, x1, ey], fill=(r, g, b, 255))


def _draw_checker(draw, x0, y0, x1, y1):
    """Draw a checkerboard pattern in the given rect."""
    w = x1 - x0
    h = y1 - y0
    if w <= 0 or h <= 0:
        return
    cols = max(2, min(8, w // 4))
    rows = max(2, min(8, h // 4))
    cs_w = w / cols
    cs_h = h / rows
    light = (200, 200, 200, 255)
    dark  = (130, 130, 130, 255)
    for row in range(rows):
        for col in range(cols):
            color = light if (row + col) % 2 == 0 else dark
            rx0 = x0 + int(col * cs_w)
            ry0 = y0 + int(row * cs_h)
            rx1 = x0 + int((col + 1) * cs_w) - 1
            ry1 = y0 + int((row + 1) * cs_h) - 1
            draw.rectangle([rx0, ry0, rx1, ry1], fill=color)


if __name__ == "__main__":
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [create_icon(s) for s in sizes]
    images[0].save(
        "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    images[-1].save("icon_preview.png")
    print("icon.ico and icon_preview.png written")
