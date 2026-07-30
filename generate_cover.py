"""
generate_cover.py — maakt de vierkante cover-afbeelding voor op je profielgrid
(los van de reel-inhoud zelf). Bewust simpel gehouden: altijd de vlakke,
groene versie met titel + badge — geen externe fotodienst, dus niets dat kan
falen door een ontbrekende API-key of quotum.

Wordt gerenderd als 1080x1080 (vierkant), precies zoals Instagram 'm toch al
bijsnijdt op het grid via de cover_url-parameter.
"""

import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
FONT_BOLD = f"{FONT_DIR}/Poppins-Bold.ttf"

SIZE = 1080
BRAND_GREEN = (183, 204, 171)   # zelfde groen als je reel-template
BADGE_PINK = (250, 210, 227)
BADGE_TEXT_DARK = (65, 72, 78)
WHITE = (255, 255, 255)


def render_cover_flat(title, badge_text, out_path, bg_color=BRAND_GREEN):
    img = Image.new("RGB", (SIZE, SIZE), bg_color)
    draw = ImageDraw.Draw(img)

    title_font = ImageFont.truetype(FONT_BOLD, 76)
    max_width = SIZE - 160

    # woord-voor-woord wrap (zelfde aanpak als in generate_reel.py)
    words = title.upper().split(" ")
    lines, current = [], []
    for w in words:
        test = " ".join(current + [w])
        bbox = draw.textbbox((0, 0), test, font=title_font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(" ".join(current))
            current = [w]
        else:
            current.append(w)
    if current:
        lines.append(" ".join(current))

    line_height = 90
    total_h = line_height * len(lines)
    y = SIZE / 2 - total_h / 2 - 40  # iets boven het midden, ruimte voor badge eronder

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        w = bbox[2] - bbox[0]
        draw.text((SIZE / 2 - w / 2, y), line, font=title_font, fill=WHITE)
        y += line_height

    # badge eronder
    badge_font = ImageFont.truetype(FONT_BOLD, 30)
    bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 34, 16
    badge_y = y + 30
    draw.rounded_rectangle(
        [SIZE / 2 - bw / 2 - pad_x, badge_y,
         SIZE / 2 + bw / 2 + pad_x, badge_y + bh + pad_y * 2],
        radius=(bh + pad_y * 2) / 2, fill=BADGE_PINK,
    )
    draw.text((SIZE / 2 - bw / 2, badge_y + pad_y - 4), badge_text,
               font=badge_font, fill=BADGE_TEXT_DARK)

    img.save(out_path)
    return out_path


def make_cover_for_topic(title, badge_text, out_path):
    """Simpel gehouden: altijd de vlakke groene versie."""
    return render_cover_flat(title, badge_text, out_path)


if __name__ == "__main__":
    render_cover_flat("FOOD FACTS THAT WILL SHOCK YOU", "Smart Health Fix",
                       "/home/claude/pipeline/output/cover_flat_test.png")
    print("Klaar: output/cover_flat_test.png")
