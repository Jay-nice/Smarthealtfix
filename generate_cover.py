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
BRAND_GREEN = (183, 204, 171)
BADGE_PINK = (250, 210, 227)
BADGE_TEXT_DARK = (65, 72, 78)
WHITE = (255, 255, 255)


def render_cover_flat(title, badge_text, out_path, bg_color=BRAND_GREEN):
    img = Image.new("RGB", (SIZE, SIZE), bg_color)
    draw = ImageDraw.Draw(img)

    # Belangrijk: Instagram toont deze cover soms vierkant (profielgrid), maar
    # soms ook uitgerekt over het volledige verticale scherm (bij het openen
    # van de reel) — daarbij snijdt Instagram links/rechts ongeveer 22% van
    # het vierkant weg om het te laten passen. Daarom houden we de tekst
    # binnen een smallere "veilige kolom" in het midden, zodat 'm nooit wordt
    # afgesneden, in geen van beide weergaven.
    max_width = 560
    available_title_height = 620

    def wrap_at_size(font_size):
        font = ImageFont.truetype(FONT_BOLD, font_size)
        words = title.upper().split(" ")
        lines, current = [], []
        for w in words:
            test = " ".join(current + [w])
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] > max_width and current:
                lines.append(" ".join(current))
                current = [w]
            else:
                current.append(w)
        if current:
            lines.append(" ".join(current))
        line_height = round(font_size * 1.18)
        return font, lines, line_height, line_height * len(lines)

    font_size = 76
    min_font_size = 38
    while font_size > min_font_size:
        title_font, lines, line_height, total_h = wrap_at_size(font_size)
        if total_h <= available_title_height and len(lines) <= 4:
            break
        font_size -= 4
    else:
        title_font, lines, line_height, total_h = wrap_at_size(min_font_size)

    y = SIZE / 2 - total_h / 2 - 40

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        w = bbox[2] - bbox[0]
        draw.text((SIZE / 2 - w / 2, y), line, font=title_font, fill=WHITE)
        y += line_height

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
