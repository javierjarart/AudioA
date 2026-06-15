#!/usr/bin/env python3
"""Generate AudioA icon — letter 'A' with sound waves."""

from PIL import Image, ImageDraw, ImageFont
import struct
import io

SIZE = 256
OUT_PNG = "resources/icon.png"
OUT_ICO = "resources/icon.ico"

FONT_SIZE = 140
COLORS = [
    (30, 60, 180),    # dark blue (top-left)
    (80, 40, 200),    # purple (center)
    (120, 30, 220),   # violet (bottom-right)
]


def _gradient_color(x, y):
    fx = x / SIZE
    fy = y / SIZE
    r = int(COLORS[0][0] * (1 - fx) * (1 - fy) + COLORS[1][0] * fx * (1 - fy) + COLORS[2][0] * fx * fy)
    g = int(COLORS[0][1] * (1 - fx) * (1 - fy) + COLORS[1][1] * fx * (1 - fy) + COLORS[2][1] * fx * fy)
    b = int(COLORS[0][2] * (1 - fx) * (1 - fy) + COLORS[1][2] * fx * (1 - fy) + COLORS[2][2] * fx * fy)
    return (r, g, b)


def create_icon():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # background circle with gradient
    cx = cy = SIZE // 2
    radius = SIZE // 2 - 8
    for y in range(SIZE):
        for x in range(SIZE):
            dx, dy = x - cx, y - cy
            if dx * dx + dy * dy <= radius * radius:
                color = _gradient_color(x, y)
                img.putpixel((x, y), (*color, 255))

    # letter "A"
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", FONT_SIZE)
    except (IOError, OSError):
        font = ImageFont.load_default()

    text = "A"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (SIZE - tw) // 2 - 15
    ty = (SIZE - th) // 2 - 5
    draw.text((tx, ty), text, fill="white", font=font)

    # sound waves (3 arcs on the right side of the A)
    wave_center_x = tx + tw + 10
    wave_center_y = ty + th // 2
    for i, (r_offset, width) in enumerate([(8, 6), (18, 5), (28, 4)]):
        r = r_offset + 10
        draw.arc(
            [
                wave_center_x - r,
                wave_center_y - r - 5,
                wave_center_x - r + 2 * r,
                wave_center_y - r - 5 + 2 * r,
            ],
            start=-60,
            end=60,
            fill=(255, 255, 255, 200 - i * 40),
            width=width,
        )

    img.save(OUT_PNG, "PNG")
    print(f"Saved {OUT_PNG}")

    # generate .ico with multiple sizes
    icon_sizes = [16, 32, 48, 64, 128, 256]
    img_resized = []
    for s in icon_sizes:
        resized = img.resize((s, s), Image.LANCZOS)
        # ensure RGBA
        if resized.mode != "RGBA":
            resized = resized.convert("RGBA")
        img_resized.append(resized)

    # save ico
    img.save(OUT_ICO, "ICO", sizes=[(s, s) for s in icon_sizes])
    print(f"Saved {OUT_ICO}")


if __name__ == "__main__":
    create_icon()
