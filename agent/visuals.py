import io

# fribidi-0.dll (needed for Telugu shaping) is put on PATH in agent/__init__.py.
from PIL import Image, ImageDraw, ImageFont, features
from pygments import highlight
from pygments.formatters import ImageFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.util import ClassNotFound

WIDTH, HEIGHT = 1920, 1080
BG_COLOR = (18, 18, 24)
CODE_BG = (30, 30, 36)
ACCENT = (99, 179, 237)
TEXT_COLOR = (240, 240, 245)
CAPTION_BG = (10, 10, 14)
CAPTION_TEXT = (255, 255, 255)


def _needs_indic_font(text: str) -> bool:
    return any("ऀ" <= ch <= "෿" for ch in text)  # Devanagari..Sinhala, incl. Telugu


def _load_font(size: int, bold: bool = False, text: str = "") -> ImageFont.FreeTypeFont:
    if _needs_indic_font(text):
        if not features.check("raqm"):
            raise RuntimeError(
                "Rendering Telugu needs Pillow's raqm text shaping, which needs fribidi-0.dll "
                "in vendor/ - without it the script renders as broken glyphs."
            )
        # Nirmala UI (ships with Windows) covers Telugu and Latin, so mixed
        # Telugu/English captions use one consistent font.
        candidates = ["NirmalaB.ttf", "Gautami.ttf"] if bold else ["Nirmala.ttf", "Gautami.ttf"]
    else:
        candidates = ["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text(text: str, font, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_title_slide(text: str, topic: str) -> Image.Image:
    """A clean text-focused slide for narration-only scenes (intro, recap, etc.)."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    label_font = _load_font(36, bold=True, text=topic)
    draw.text((60, 50), topic.upper(), font=label_font, fill=ACCENT)
    draw.line([(60, 100), (WIDTH - 60, 100)], fill=ACCENT, width=2)

    body_font = _load_font(52, text=text)
    lines = _wrap_text(text, body_font, WIDTH - 240, draw)
    line_height = 70
    total_h = len(lines) * line_height
    y = (HEIGHT - total_h) // 2
    for line in lines:
        w = draw.textlength(line, font=body_font)
        draw.text(((WIDTH - w) / 2, y), line, font=body_font, fill=TEXT_COLOR)
        y += line_height
    return img


def render_code_slide(code: str, language: str) -> Image.Image:
    """A syntax-highlighted rendering of a code example, centered on a fixed canvas."""
    try:
        lexer = get_lexer_by_name(language, stripall=False)
    except ClassNotFound:
        try:
            lexer = guess_lexer(code)
        except ClassNotFound:
            lexer = get_lexer_by_name("text")

    formatter = ImageFormatter(font_size=34, line_numbers=True, style="monokai", image_pad=60, line_pad=10)
    png_bytes = highlight(code, lexer, formatter)
    code_img = Image.open(io.BytesIO(png_bytes)).convert("RGB")

    canvas = Image.new("RGB", (WIDTH, HEIGHT), CODE_BG)
    cw, ch = code_img.size
    # Fit to the frame in both directions - scale up short snippets to fill the
    # space (capped to avoid blur) as well as scaling down long ones.
    scale = min((WIDTH - 160) / cw, (HEIGHT - 160) / ch, 2.5)
    if scale != 1.0:
        code_img = code_img.resize((max(1, int(cw * scale)), max(1, int(ch * scale))))
        cw, ch = code_img.size
    canvas.paste(code_img, ((WIDTH - cw) // 2, (HEIGHT - ch) // 2))
    return canvas


def add_caption(img: Image.Image, caption: str) -> Image.Image:
    """Burn a bottom-bar caption onto a copy of img."""
    img = img.copy()
    draw = ImageDraw.Draw(img)
    font = _load_font(34, text=caption)
    max_width = WIDTH - 160
    lines = _wrap_text(caption, font, max_width, draw)[:3]  # cap to avoid overflowing the frame

    line_height = 44
    bar_h = 40 + len(lines) * line_height
    draw.rectangle([(0, HEIGHT - bar_h), (WIDTH, HEIGHT)], fill=CAPTION_BG)

    y = HEIGHT - bar_h + 20
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text(((WIDTH - w) / 2, y), line, font=font, fill=CAPTION_TEXT)
        y += line_height
    return img


YT_RED = (230, 33, 23)


def render_cta_slide(channel: str, topic: str, labels: dict) -> Image.Image:
    """Branded intro slide: channel name plus LIKE / SHARE / SUBSCRIBE buttons.
    labels holds the (possibly translated) welcome line and button captions."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    welcome_font = _load_font(48, text=labels["welcome"])
    w = draw.textlength(labels["welcome"], font=welcome_font)
    draw.text(((WIDTH - w) / 2, 200), labels["welcome"], font=welcome_font, fill=TEXT_COLOR)

    channel_font = _load_font(150, bold=True, text=channel)
    w = draw.textlength(channel, font=channel_font)
    draw.text(((WIDTH - w) / 2, 280), channel, font=channel_font, fill=ACCENT)

    topic_font = _load_font(44, text=topic)
    w = draw.textlength(topic, font=topic_font)
    draw.text(((WIDTH - w) / 2, 490), topic, font=topic_font, fill=(170, 170, 185))

    buttons = [labels["like"], labels["share"], labels["subscribe"]]
    button_font = _load_font(52, bold=True, text="".join(buttons))
    button_w, button_h, gap = 440, 120, 60
    x = (WIDTH - (3 * button_w + 2 * gap)) // 2
    y = 660
    for i, text in enumerate(buttons):
        is_subscribe = i == len(buttons) - 1
        box = [(x, y), (x + button_w, y + button_h)]
        if is_subscribe:
            draw.rounded_rectangle(box, radius=24, fill=YT_RED)
        else:
            draw.rounded_rectangle(box, radius=24, outline=TEXT_COLOR, width=4)
        tw = draw.textlength(text, font=button_font)
        bbox = draw.textbbox((0, 0), text, font=button_font)
        th = bbox[3] - bbox[1]
        draw.text((x + (button_w - tw) / 2, y + (button_h - th) / 2 - bbox[1]), text, font=button_font, fill=TEXT_COLOR)
        x += button_w + gap
    return img
