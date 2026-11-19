import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

SIZE = 1080
TOP_BAR_H = 100
DARK_BG = (15, 23, 42)       # Slate 900
WHITE = (255, 255, 255)
ACCENT_ORANGE = (255, 107, 0) # Neon Orange
PRICE_GREEN = (16, 185, 129)  # Emerald 500
STRIKE_RED = (239, 68, 68)    # Red 500
MUTED_GRAY = (148, 163, 184)  # Slate 400

FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
)

LOGO_FILE = Path(__file__).parent / "assets" / "logo.png"


def _font(size: int):
    for path in FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _get_circular_logo(size: int = 200) -> Image.Image | None:
    if not LOGO_FILE.exists():
        return None
    try:
        im = Image.open(LOGO_FILE).convert("RGBA")
        mask = Image.new("L", im.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((6, 6, im.size[0] - 7, im.size[1] - 7), fill=255)
        im.putalpha(mask)
        im.thumbnail((size, size), Image.LANCZOS)
        return im
    except Exception:
        return None


def make_card(photo: bytes, price_before: str | None = None, price_after: str | None = None,
              channel_name: str = "MegaPromo") -> bytes:
    """
    Gera o cartão de imagem de acordo com as especificações do utilizador:
    - Foto do produto central e limpa.
    - Preço antes (riscado) e preço depois em destaque.
    - Logo do canal no canto inferior esquerdo.
    - Faixa no topo com lettering 'MegaPromo'.
    """
    try:
        product = Image.open(io.BytesIO(photo)).convert("RGB")
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError("imagem inválida") from e

    card = Image.new("RGB", (SIZE, SIZE), WHITE)

    # 1. Faixa Superior (Header)
    d = ImageDraw.Draw(card)
    d.rectangle((0, 0, SIZE, TOP_BAR_H), fill=DARK_BG)
    d.rectangle((0, TOP_BAR_H - 4, SIZE, TOP_BAR_H), fill=ACCENT_ORANGE)

    header_text = channel_name.upper()
    header_font = _font(46)
    bbox = d.textbbox((0, 0), header_text, font=header_font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    d.text(((SIZE - tw) // 2, (TOP_BAR_H - th) // 2 - 2), header_text, font=header_font, fill=WHITE)

    # 2. Imagem do Produto (Central)
    max_w = SIZE - 120
    max_h = SIZE - TOP_BAR_H - 260
    product.thumbnail((max_w, max_h), Image.LANCZOS)
    
    px = (SIZE - product.width) // 2
    py = TOP_BAR_H + 30 + (max_h - product.height) // 2
    card.paste(product, (px, py))

    # 3. Logo no Canto Inferior Esquerdo
    logo = _get_circular_logo(size=190)
    if logo:
        lx, ly = 45, SIZE - 225
        card.paste(logo, (lx, ly), mask=logo)

    # 4. Preço Antes e Depois no Canto Inferior Direito
    if price_after:
        box_w, box_h = 360, 140
        bx = SIZE - box_w - 45
        by = SIZE - box_h - 60

        d.rounded_rectangle((bx, by, bx + box_w, by + box_h), radius=20, fill=DARK_BG, outline=ACCENT_ORANGE, width=3)

        if price_before:
            before_str = f"De: {price_before}"
            before_font = _font(28)
            d.text((bx + 25, by + 18), before_str, font=before_font, fill=MUTED_GRAY)
            strike_bbox = d.textbbox((bx + 25, by + 18), before_str, font=before_font)
            line_y = (strike_bbox[1] + strike_bbox[3]) // 2
            d.line((strike_bbox[0], line_y, strike_bbox[2], line_y), fill=STRIKE_RED, width=3)

            after_font = _font(52)
            d.text((bx + 25, by + 56), price_after, font=after_font, fill=PRICE_GREEN)
        else:
            only_label = "OFERTA"
            d.text((bx + 25, by + 16), only_label, font=_font(26), fill=ACCENT_ORANGE)
            after_font = _font(52)
            d.text((bx + 25, by + 52), price_after, font=after_font, fill=PRICE_GREEN)

    out = io.BytesIO()
    card.save(out, "JPEG", quality=92)
    return out.getvalue()
