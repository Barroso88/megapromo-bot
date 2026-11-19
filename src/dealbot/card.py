import io
import math
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, UnidentifiedImageError

SIZE = 1080
TOP_BAR_H = 100
DARK_BG = (17, 24, 39)          # Gray 900
SURFACE_BG = (15, 23, 42)       # Slate 900
WHITE = (255, 255, 255)
ACCENT_ORANGE = (255, 107, 0)   # Neon Orange
DISCOUNT_RED = (225, 29, 72)    # Rose 600
PRICE_GOLD = (255, 215, 0)      # Gold / Bright Amber
PRICE_GREEN = (52, 211, 153)    # Emerald 400
TEXT_MUTED = (156, 163, 175)    # Gray 400
BORDER_COLOR = (55, 65, 81)     # Gray 700

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


def _parse_val(val_str: str) -> float | None:
    if not val_str:
        return None
    cleaned = re.sub(r"[^\d,\.]", "", val_str).replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _calc_discount_percent(before: str, after: str) -> int | None:
    v1 = _parse_val(before)
    v2 = _parse_val(after)
    if v1 and v2 and v1 > v2:
        return int(round((1 - (v2 / v1)) * 100))
    return None


def make_card(photo: bytes, price_before: str | None = None, price_after: str | None = None,
              channel_name: str = "MegaPromo") -> bytes:
    """
    Cartão visual Premium:
    - Foto do produto centralizada.
    - Faixa superior 'MegaPromo' com glow suave.
    - Logótipo oficial no canto inferior esquerdo com sombra.
    - Badge de Preço Flutuante Premium com tag de desconto %, sombra 3D e tipografia cuidada.
    """
    try:
        product = Image.open(io.BytesIO(photo)).convert("RGB")
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError("imagem inválida") from e

    card = Image.new("RGB", (SIZE, SIZE), (255, 255, 255))

    # 1. Faixa Superior (Header)
    d = ImageDraw.Draw(card)
    d.rectangle((0, 0, SIZE, TOP_BAR_H), fill=DARK_BG)
    # Linha neon inferior do header
    d.rectangle((0, TOP_BAR_H - 4, SIZE, TOP_BAR_H), fill=ACCENT_ORANGE)

    header_text = channel_name.upper()
    header_font = _font(46)
    bbox = d.textbbox((0, 0), header_text, font=header_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((SIZE - tw) // 2, (TOP_BAR_H - th) // 2 - 2), header_text, font=header_font, fill=WHITE)

    # 2. Foto do Produto (Central)
    max_w = SIZE - 120
    max_h = SIZE - TOP_BAR_H - 260
    product.thumbnail((max_w, max_h), Image.LANCZOS)
    px = (SIZE - product.width) // 2
    py = TOP_BAR_H + 25 + (max_h - product.height) // 2
    card.paste(product, (px, py))

    # 3. Logo Circular com Sombra Suave
    logo = _get_circular_logo(size=190)
    if logo:
        lx, ly = 45, SIZE - 225
        card.paste(logo, (lx, ly), mask=logo)

    # 4. Badge de Preço Premium com Sombra
    if price_after:
        box_w, box_h = 390, 160
        bx = SIZE - box_w - 45
        by = SIZE - box_h - 55

        # Criar camada separada com transparência para a sombra e cartão flutuante
        overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)

        # Sombra suave (Drop Shadow)
        shadow_offset = 8
        shadow_rect = (bx + shadow_offset, by + shadow_offset, bx + box_w + shadow_offset, by + box_h + shadow_offset)
        odraw.rounded_rectangle(shadow_rect, radius=24, fill=(0, 0, 0, 80))
        overlay = overlay.filter(ImageFilter.GaussianBlur(8))
        odraw = ImageDraw.Draw(overlay)

        # Fundo do Badge (Dark obsidian com contorno suave)
        odraw.rounded_rectangle((bx, by, bx + box_w, by + box_h), radius=24, fill=(15, 23, 42, 250),
                                outline=BORDER_COLOR, width=2)

        # Pequeno friso superior neon
        odraw.rounded_rectangle((bx + 20, by, bx + box_w - 20, by + 3), radius=2, fill=(255, 107, 0, 220))

        discount_pct = _calc_discount_percent(price_before, price_after) if price_before else None

        if price_before:
            # Linha Superior: Antes + Tag de Desconto
            before_str = f"Antes: {price_before}"
            before_font = _font(25)
            odraw.text((bx + 28, by + 24), before_str, font=before_font, fill=TEXT_MUTED)

            # Risco elegante vermelho sobre o preço anterior
            s_bbox = odraw.textbbox((bx + 28, by + 24), before_str, font=before_font)
            line_y = (s_bbox[1] + s_bbox[3]) // 2
            odraw.line((s_bbox[0], line_y, s_bbox[2], line_y), fill=DISCOUNT_RED, width=3)

            # Tag de Desconto (%) à direita
            if discount_pct and discount_pct > 0:
                tag_str = f"-{discount_pct}%"
                tag_font = _font(22)
                t_bbox = odraw.textbbox((0, 0), tag_str, font=tag_font)
                t_w, t_h = t_bbox[2] - t_bbox[0], t_bbox[3] - t_bbox[1]
                tag_pad_x, tag_pad_y = 12, 6
                tag_x = bx + box_w - t_w - 28 - (tag_pad_x * 2)
                tag_y = by + 18
                odraw.rounded_rectangle(
                    (tag_x, tag_y, tag_x + t_w + (tag_pad_x * 2), tag_y + t_h + (tag_pad_y * 2)),
                    radius=10,
                    fill=DISCOUNT_RED
                )
                odraw.text((tag_x + tag_pad_x, tag_y + tag_pad_y - 2), tag_str, font=tag_font, fill=WHITE)

            # Linha Inferior: Preço Promocional em Destaque
            now_label = "AGORA"
            odraw.text((bx + 28, by + 74), now_label, font=_font(18), fill=ACCENT_ORANGE)

            price_font = _font(56)
            odraw.text((bx + 28, by + 94), price_after, font=price_font, fill=PRICE_GREEN)

        else:
            # Só Preço Promocional
            tag_str = "OFERTA ESPECIAL"
            odraw.text((bx + 28, by + 24), tag_str, font=_font(22), fill=ACCENT_ORANGE)
            price_font = _font(58)
            odraw.text((bx + 28, by + 68), price_after, font=price_font, fill=PRICE_GREEN)

        # Junta a camada com sombra e badge à imagem principal
        card.paste(overlay, (0, 0), mask=overlay)

    out = io.BytesIO()
    card.save(out, "JPEG", quality=93)
    return out.getvalue()
