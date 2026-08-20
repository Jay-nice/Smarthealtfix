"""
generate_cover.py — maakt de vierkante cover-afbeelding voor op je profielgrid
(los van de reel-inhoud zelf). Bewust simpel gehouden: altijd de vlakke
versie met titel + een klein Instagram-icoontje + je handle — geen externe
fotodienst, dus niets dat kan falen door een ontbrekende API-key of quotum.

De achtergrondkleur wisselt automatisch af tussen het merk-groen en (bijna-)
wit bij elke nieuwe cover (groen, wit, groen, wit, ...), zodat je profielgrid
een net, afwisselend patroon krijgt. De laatst gebruikte kleur wordt onthouden
in output/cover_state.json - dat bestand wordt (net als output/history.json)
automatisch door de workflow gecommit, dus de afwisseling blijft ook over
losse runs/dagen heen kloppen.

Wordt gerenderd als 1080x1080 (vierkant), precies zoals Instagram 'm toch al
bijsnijdt op het grid via de cover_url-parameter.
"""

import os
from PIL import Image, ImageDraw, ImageFont

from cover_state import peek_next_bg  # bewust in een apart, Pillow-vrij bestand (zie cover_state.py)

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
FONT_BOLD = f"{FONT_DIR}/Poppins-Bold.ttf"

SIZE = 1080
BRAND_GREEN = (183, 204, 171)
BG_LIGHT = (249, 250, 248)     # zelfde bijna-wit als de achtergrond van de reel-afbeelding zelf
TEXT_DARK = (65, 72, 78)       # zelfde donkere kleur als de reel-tekst (DARK in generate_reel.py)
TEXT_LIGHT = (255, 255, 255)


def draw_ig_icon(draw, x, y, size, color):
    """
    Tekent een heel klein, monochroom Instagram-achtig camera-icoontje
    (afgeronde vierkant-omtrek + cirkel + stipje rechtsboven) in dezelfde
    kleur als de tekst ernaast - geen extern logo-bestand nodig.
    (x, y) = linkerbovenhoek van het icoon.
    """
    stroke_width = max(2, round(size * 0.09))
    draw.rounded_rectangle(
        [x, y, x + size, y + size],
        radius=round(size * 0.28), outline=color, width=stroke_width,
    )
    circle_d = round(size * 0.5)
    circle_x = x + (size - circle_d) / 2
    circle_y = y + (size - circle_d) / 2
    draw.ellipse(
        [circle_x, circle_y, circle_x + circle_d, circle_y + circle_d],
        outline=color, width=stroke_width,
    )
    dot_r = max(2, round(size * 0.07))
    dot_cx = x + size - size * 0.2
    dot_cy = y + size * 0.2
    draw.ellipse(
        [dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r],
        fill=color,
    )


# --- Vaste layout-posities (i.p.v. positie die meebeweegt met titel-lengte) ---
# Titel begint ALTIJD op dezelfde hoogte (TITLE_TOP), ongeacht of 'm 1 of 4
# regels wordt - hij groeit dus naar ONDEREN toe, nooit rond het midden heen.
# De handle staat ALTIJD op dezelfde hoogte (HANDLE_ROW_Y), volledig los van
# hoe lang de titel is. Het lettertype van de titel is een VASTE, bewust
# gematigde grootte (niet meer een bereik dat soms groot, soms klein uitpakt)
# - alleen bij een uitzonderlijk lange titel (>4 regels) verkleint 'm als
# noodgreep, zodat niks ooit buiten beeld valt of de handle raakt.
TITLE_TOP = 400
TITLE_FONT_SIZE = 54
TITLE_MIN_FONT_SIZE = 40
HANDLE_ROW_Y = 760


def render_cover_flat(title, handle_text, out_path, bg_color=BRAND_GREEN):
    img = Image.new("RGB", (SIZE, SIZE), bg_color)
    draw = ImageDraw.Draw(img)

    # Op een lichte achtergrond moet de tekst donker zijn, op de groene
    # achtergrond blijft 'm wit (zoals voorheen).
    text_color = TEXT_DARK if bg_color == BG_LIGHT else TEXT_LIGHT

    # Belangrijk: Instagram toont deze cover soms vierkant (profielgrid), maar
    # soms ook uitgerekt over het volledige verticale scherm (bij het openen
    # van de reel) — daarbij snijdt Instagram links/rechts ongeveer 22% van
    # het vierkant weg om het te laten passen. Daarom houden we de tekst
    # binnen een smallere "veilige kolom" in het midden, zodat 'm nooit wordt
    # afgesneden, in geen van beide weergaven.
    max_width = 560

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
        return font, lines, line_height

    # Vaste grootte is de norm; alleen als een titel zelfs dan niet in 4
    # regels past (zeer ongebruikelijk lang), knijpen we 'm iets kleiner -
    # puur als noodgreep, niet als normale gang van zaken.
    title_font, lines, line_height = wrap_at_size(TITLE_FONT_SIZE)
    font_size = TITLE_FONT_SIZE
    while len(lines) > 4 and font_size > TITLE_MIN_FONT_SIZE:
        font_size -= 2
        title_font, lines, line_height = wrap_at_size(font_size)

    y = TITLE_TOP
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        w = bbox[2] - bbox[0]
        draw.text((SIZE / 2 - w / 2, y), line, font=title_font, fill=text_color)
        y += line_height

    # --- Instagram-icoontje + handle (i.p.v. de vorige roze badge) ---
    # Vaste hoogte (HANDLE_ROW_Y), NIET afhankelijk van waar de titel eindigt.
    handle_font = ImageFont.truetype(FONT_BOLD, 30)
    bbox = draw.textbbox((0, 0), handle_text, font=handle_font)
    htext_w, htext_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    icon_size = round(htext_h * 1.2)
    gap = 14
    group_w = icon_size + gap + htext_w
    row_y = HANDLE_ROW_Y

    icon_x = SIZE / 2 - group_w / 2
    icon_y = row_y + (htext_h - icon_size) / 2 - bbox[1]
    draw_ig_icon(draw, icon_x, icon_y, icon_size, text_color)

    text_x = icon_x + icon_size + gap
    draw.text((text_x, row_y), handle_text, font=handle_font, fill=text_color)

    img.save(out_path)
    return out_path


def make_cover_for_topic(title, handle_text, out_path):
    """
    Bepaalt welke achtergrondkleur (groen/wit, afwisselend) deze cover zou
    moeten krijgen en rendert daarmee de cover. Geeft (out_path, bg_choice)
    terug - bg_choice moet je bewaren (zie run_pipeline.py -> last_run.json)
    en pas met confirm_bg_used() vastleggen zodra publiceren ook echt lukt.
    """
    bg_choice = peek_next_bg()
    bg_color = BRAND_GREEN if bg_choice == "green" else BG_LIGHT
    path = render_cover_flat(title, handle_text, out_path, bg_color=bg_color)
    return path, bg_choice


if __name__ == "__main__":
    render_cover_flat("FOOD FACTS THAT WILL SHOCK YOU", "@smarthealthfix",
                       "/home/claude/pipeline/output/cover_flat_test_green.png",
                       bg_color=BRAND_GREEN)
    render_cover_flat("FOOD FACTS THAT WILL SHOCK YOU", "@smarthealthfix",
                       "/home/claude/pipeline/output/cover_flat_test_white.png",
                       bg_color=BG_LIGHT)
    print("Klaar: cover_flat_test_green.png / cover_flat_test_white.png")
