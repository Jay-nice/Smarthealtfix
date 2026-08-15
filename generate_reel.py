"""
Reel-afbeelding generator — bouwt het "did you know" sjabloon na
(donker groen/slate accent, witte achtergrond, bold keywords in de tekst).

Gebruik:
    python3 generate_reel.py

Pas de CONFIG hieronder aan (of importeer render_slide() vanuit een ander script
dat de content automatisch genereert, bijv. via de Claude API).
"""

import os
import re
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# CONFIG — kleuren en fonts gebaseerd op het aangeleverde voorbeeld
# ---------------------------------------------------------------------------

CANVAS_W, CANVAS_H = 1080, 1920
BG_COLOR = (249, 250, 248)        # bijna-wit
DARK = (65, 72, 78)               # donker leisteen (titel/tekst/footer-bar)
ACCENT_GREEN = (150, 172, 138)    # sage groen (accentwoord + handle)
WHITE = (255, 255, 255)

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FONT_BOLD = f"{FONT_DIR}/Poppins-Bold.ttf"
FONT_SEMIBOLD = f"{FONT_DIR}/Poppins-SemiBold.ttf"
FONT_REGULAR = f"{FONT_DIR}/Poppins-Regular.ttf"

MARGIN_X = 72
MUSIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music")
REEL_DURATION_SECONDS = 5

# ---------------------------------------------------------------------------
# Content — pas dit aan per reel. **woord** = vetgedrukt, {{woord}} in de titel
# = groen accentwoord.
# ---------------------------------------------------------------------------

CONFIG = {
    "handle": "@smarthealthfix",
    "title": "SURPRISING {{FOOD}} FACTS: NUTRIENT-PACKED FOODS YOU DIDN'T EXPECT",
    "facts": [
        "Did you know that a cup of **red bell peppers** has almost 3 times more **vitamin C** than **an orange**?",
        "Did you know that a serving of **pumpkin seeds** has more **magnesium** than **a banana**?",
        "Did you know that a cup of **raspberries** has more **fiber** than **a bowl of oatmeal**?",
        "Did you know that **a sweet potato** has more **potassium** than **a banana**?",
        "Did you know that **mushrooms** exposed to sunlight contain more **vitamin D** than **fortified milk**?",
        "Did you know that **dark chocolate** contains more **antioxidants** than **green tea**?",
        "Did you know that **collard greens** have more **vitamin K** per cup than **kale**?",
        "Did you know that eating **beets** can support **healthy blood pressure** thanks to their natural **nitrates**?",
        "Did you know that a single **Brazil nut** provides more than your **daily requirement of selenium**?",
    ],
    "footer_cta": "Save & Share let's get healthier together!",
}

# ---------------------------------------------------------------------------
# Tekst-helpers: parsen van **bold** runs en woord-voor-woord wrappen met
# gemengde fonts (regular/bold) op één regel.
# ---------------------------------------------------------------------------

def parse_bold_runs(text):
    """Splits 'a **b** c' in [('a ', False), ('b', True), (' c', False)]."""
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    runs = []
    for p in parts:
        if not p:
            continue
        if p.startswith("**") and p.endswith("**"):
            runs.append((p[2:-2], True))
        else:
            runs.append((p, False))
    return runs


def runs_to_words(runs):
    """Zet runs om in losse (woord, is_bold) tokens, spaties worden weggegooid
    (worden apart weer toegevoegd bij het tekenen)."""
    words = []
    for text, is_bold in runs:
        for w in text.split(" "):
            if w:
                words.append((w, is_bold))
    return words


def text_width(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def wrap_words(draw, words, font_regular, font_bold, max_width):
    """Groepeert (woord, is_bold) tokens in regels die binnen max_width passen."""
    space_w = text_width(draw, " ", font_regular)
    lines = []
    current = []
    current_w = 0
    for word, is_bold in words:
        f = font_bold if is_bold else font_regular
        w = text_width(draw, word, f)
        extra = (space_w if current else 0) + w
        if current and current_w + extra > max_width:
            lines.append(current)
            current = [(word, is_bold)]
            current_w = w
        else:
            current.append((word, is_bold))
            current_w += extra
    if current:
        lines.append(current)
    return lines


def draw_wrapped_line(draw, line, font_regular, font_bold, x_center, y, align="center", left_x=None, color=DARK):
    """Tekent één regel (lijst van (woord, is_bold)) gecentreerd of links uitgelijnd."""
    space_w = text_width(draw, " ", font_regular)
    widths = []
    for word, is_bold in line:
        f = font_bold if is_bold else font_regular
        widths.append(text_width(draw, word, f))
    total_w = sum(widths) + space_w * (len(line) - 1 if line else 0)

    if align == "center":
        x = x_center - total_w / 2
    else:
        x = left_x

    for (word, is_bold), w in zip(line, widths):
        f = font_bold if is_bold else font_regular
        draw.text((x, y), word, font=f, fill=color)
        x += w + space_w


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render_slide(config, out_path):
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # --- Handle rechtsboven ---
    handle_font = ImageFont.truetype(FONT_BOLD, 30)
    handle = config["handle"]
    hw = text_width(draw, handle, handle_font)
    draw.text((CANVAS_W - MARGIN_X - hw, 60), handle, font=handle_font, fill=ACCENT_GREEN)

    # --- Titel ---
    title_font = ImageFont.truetype(FONT_BOLD, 62)
    title_max_w = CANVAS_W - 2 * MARGIN_X

    # parse {{highlight}} in de titel -> los als bold-run met groene kleur
    raw_title = config["title"].upper()
    title_runs = []
    for part in re.split(r"(\{\{[^}]+\}\})", raw_title):
        if not part:
            continue
        if part.startswith("{{") and part.endswith("}}"):
            title_runs.append((part[2:-2], "accent"))
        else:
            title_runs.append((part, "normal"))

    title_words = []
    for text, kind in title_runs:
        for w in text.split(" "):
            if w:
                title_words.append((w, kind))

    # wrap (zelfde logica, kleur ipv bold voor de highlight)
    space_w = text_width(draw, " ", title_font)
    lines, current, current_w = [], [], 0
    for word, kind in title_words:
        w = text_width(draw, word, title_font)
        extra = (space_w if current else 0) + w
        if current and current_w + extra > title_max_w:
            lines.append(current)
            current, current_w = [(word, kind)], w
        else:
            current.append((word, kind))
            current_w += extra
    if current:
        lines.append(current)

    title_line_height = 76
    title_y = 170
    x_center = CANVAS_W / 2
    for line in lines:
        widths = [text_width(draw, w, title_font) for w, _ in line]
        total_w = sum(widths) + space_w * (len(line) - 1 if line else 0)
        x = x_center - total_w / 2
        for (word, kind), w in zip(line, widths):
            color = ACCENT_GREEN if kind == "accent" else DARK
            draw.text((x, title_y), word, font=title_font, fill=color)
            x += w + space_w
        title_y += title_line_height

    # --- Feiten-lijst: auto-fit ---
    # Beschikbare ruimte tussen titel en footer-CTA bepalen, en de grootst
    # mogelijke tekstgrootte zoeken die alle feiten laat passen (zoals
    # "auto-fit tekst" in Canva/PowerPoint).
    footer_bar_h = 130
    cta_font_size = 30
    cta_reserved_h = 80  # ruimte voor de CTA-regel boven de footer-bar
    list_max_w = CANVAS_W - 2 * MARGIN_X
    list_top = title_y + 50
    list_bottom_limit = CANVAS_H - footer_bar_h - cta_reserved_h - 20
    available_h = list_bottom_limit - list_top

    # Sommige vormen zijn een genummerde lijst (zie "numbered" in
    # TEMPLATE_SHAPES/content_generator.py) - net als bij de concurrentie
    # ("1. Baking Soda removes...", ..., "9. Follow this page...") zetten we
    # dan zelf een schoon "1. ", "2. ", ... nummer voor elk item, inclusief de
    # laatste follow-oproep. Dit doen we hier in de renderer (niet aan het
    # model overlaten) zodat de nummering altijd 100% consistent is, ongeacht
    # of het model het zelf ook had toegevoegd (een eventueel dubbel nummer
    # van het model wordt eerst gestript).
    if config.get("numbered"):
        strip_num_re = re.compile(r"^\s*\d+[\.\)]\s*")
        config["facts"] = [
            f"{i + 1}. {strip_num_re.sub('', fact)}"
            for i, fact in enumerate(config["facts"])
        ]

    # Het LAATSTE item in "facts" is standaard de follow-oproep (zie
    # content_generator.py) - die laten we opvallen door 'm helemaal vet te
    # zetten (zelfde kleur als de rest, alleen dikker).
    num_facts = len(config["facts"])
    last_fact_index = num_facts - 1

    def measure_list_height(font_size, line_height, paragraph_gap):
        f_reg = ImageFont.truetype(FONT_REGULAR, font_size)
        f_bold = ImageFont.truetype(FONT_SEMIBOLD, font_size)
        total = 0
        per_fact_lines = []
        for idx, fact in enumerate(config["facts"]):
            runs = parse_bold_runs(fact)
            if idx == last_fact_index:
                runs = [(text, True) for text, _ in runs]  # alles vet voor de CTA
            words = runs_to_words(runs)
            wlines = wrap_words(draw, words, f_reg, f_bold, list_max_w)
            per_fact_lines.append(wlines)
            total += len(wlines) * line_height
        total += paragraph_gap * (len(config["facts"]) - 1)
        return total, per_fact_lines, f_reg, f_bold

    # Groter startpunt en een veel hoger plafond dan voorheen (was 46): de
    # concurrentie (@mentorofwellness, @holistichealthplanet e.d.) gebruikt
    # fors grotere tekst en zet items DIRECT onder elkaar, zonder enige
    # tussenruimte - het nummer ervoor is genoeg om aan te geven waar het
    # volgende item begint. paragraph_gap is daarom 0: geen ruimte tussen
    # items, alleen line_height tussen regels (ook binnen hetzelfde item).
    font_size = 100          # startpunt: zoekt vanaf hier naar beneden de grootste maat die past
    min_font_size = 22
    max_font_size = 100
    paragraph_gap = 0
    chosen = None
    while font_size >= min_font_size:
        line_height = round(font_size * 1.12)       # krap binnen 1 item (was 1.27)
        total_h, per_fact_lines, f_reg, f_bold = measure_list_height(
            font_size, line_height, paragraph_gap)
        if total_h <= available_h:
            chosen = (font_size, line_height, per_fact_lines, f_reg, f_bold, total_h)
            break
        font_size -= 1
    if chosen is None:
        # niets paste zelfs op de kleinste toegestane grootte: gebruik 'm toch
        line_height = round(min_font_size * 1.12)
        total_h, per_fact_lines, f_reg, f_bold = measure_list_height(
            min_font_size, line_height, paragraph_gap)
        chosen = (min_font_size, line_height, per_fact_lines, f_reg, f_bold, total_h)

    font_size, line_height, per_fact_lines, fact_font, fact_font_bold, total_h = chosen

    # --- Restruimte opvullen ---
    # De zoeklus hierboven kiest al de GROOTSTE tekstgrootte die past, dus
    # normaal is er weinig restruimte. Wat er nog overblijft (bijv. bij
    # weinig items) gaat NIET naar extra tussenruimte (die willen we juist op
    # 0 houden, net als het voorbeeld-account), maar puur naar het verticaal
    # centreren van het hele blok tussen titel en footer.
    list_top_adjusted = list_top + max(available_h - total_h, 0) / 2

    list_y = list_top_adjusted
    for wlines in per_fact_lines:
        for wline in wlines:
            draw_wrapped_line(draw, wline, fact_font, fact_font_bold,
                               x_center=None, y=list_y, align="left",
                               left_x=MARGIN_X, color=DARK)
            list_y += line_height
        list_y += paragraph_gap

    # --- Footer CTA tekst ---
    cta_font = ImageFont.truetype(FONT_SEMIBOLD, cta_font_size)
    cta_text = config["footer_cta"]
    cta_w = text_width(draw, cta_text, cta_font)
    cta_y = CANVAS_H - footer_bar_h - 60
    draw.text((x_center - cta_w / 2, cta_y), cta_text, font=cta_font, fill=DARK)

    # --- Footer bar ---
    draw.rectangle([0, CANVAS_H - footer_bar_h, CANVAS_W, CANVAS_H], fill=DARK)
    footer_handle_font = ImageFont.truetype(FONT_BOLD, 36)
    fh_w = text_width(draw, config["handle"], footer_handle_font)
    draw.text((x_center - fh_w / 2, CANVAS_H - footer_bar_h / 2 - 22),
               config["handle"], font=footer_handle_font, fill=WHITE)

    img.save(out_path)
    return out_path


def pick_random_track(music_dir=MUSIC_DIR):
    """Kiest willekeurig een audiobestand uit jouw muziekmap."""
    import os, random
    if not os.path.isdir(music_dir):
        return None
    tracks = [f for f in os.listdir(music_dir) if f.lower().endswith((".mp3", ".m4a", ".wav", ".aac"))]
    if not tracks:
        return None
    return os.path.join(music_dir, random.choice(tracks))


def image_to_reel_video(image_path, video_path, duration_seconds=REEL_DURATION_SECONDS,
                         audio_path="__auto__"):
    """Zet de statische afbeelding om in een MP4 van vaste lengte, met automatisch
    een willekeurige track uit MUSIC_DIR eronder gemixt (tenzij audio_path=None
    wordt meegegeven, dan blijft de reel stil)."""
    import subprocess

    if audio_path == "__auto__":
        audio_path = pick_random_track()

    # Kwaliteitsinstellingen: Instagram's Content Publishing API heeft GEEN
    # "beste kwaliteit"-schuifje zoals de app dat wel heeft bij handmatig
    # uploaden - de enige hendel die wij hebben is hoe goed het bronbestand
    # zelf is dat we aanleveren. -crf 18 is visueel zo goed als lossless
    # (standaard is 23, hoger getal = meer compressie/kwaliteitsverlies).
    # -maxrate/-bufsize houdt 'm binnen Instagram's aanbevolen max van 5 Mbps
    # voor Reels, -profile:v high voor de beste H.264-encodingkwaliteit.
    video_quality_flags = [
        "-c:v", "libx264", "-crf", "18", "-profile:v", "high", "-level", "4.0",
        "-maxrate", "5M", "-bufsize", "10M", "-r", "30",
    ]

    if audio_path:
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", image_path,
            "-i", audio_path,
            "-t", str(duration_seconds),
            "-vf", "scale=1080:1920,format=yuv420p",
            *video_quality_flags,
            "-c:a", "aac", "-b:a", "128k",
            "-shortest", "-movflags", "+faststart",
            video_path,
        ]
        used_track = audio_path
    else:
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", image_path,
            "-t", str(duration_seconds),
            "-vf", "scale=1080:1920,format=yuv420p",
            *video_quality_flags,
            "-movflags", "+faststart",
            video_path,
        ]
        used_track = None

    subprocess.run(cmd, check=True, capture_output=True)
    return video_path, used_track


if __name__ == "__main__":
    import os as _os
    _os.makedirs("output", exist_ok=True)
    png_path = render_slide(CONFIG, "output/test_slide.png")
    print(f"Afbeelding klaar: {png_path}")
    mp4_path, track = image_to_reel_video(png_path, "output/test_reel.mp4")
    print(f"Reel-video klaar: {mp4_path}")
    print(f"Gebruikte muziektrack: {track}")
