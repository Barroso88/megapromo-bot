"""Cartão de imagem do canal: barra MEGAPROMO, foto do produto, logótipo, título e (opcional) preços."""
import io
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, UnidentifiedImageError

S = 1080
NAVY, ORANGE, WHITE = (16, 24, 48), (255, 122, 0), (255, 255, 255)
BLUE, BLACK_L, BLACK_R, GREY_BG, GREY_TXT, RED, GOLD = (0, 112, 206), (62, 64, 70), (6, 6, 8), (244, 245, 248), (100, 112, 135), (200, 30, 60), (255, 215, 0)
HEADER_H, BAND_TOP = 100, 760
LOGO = Path(__file__).parent / "assets" / "logo.png"
FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)


def _font(size: int):
    for path in FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _num(text: str) -> float | None:
    try:
        return float(text.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def discount(price: str, old_price: str) -> int | None:
    new, old = _num(price), _num(old_price)
    if not new or not old or old <= new:
        return None
    return round((1 - new / old) * 100)


def _band(d: ImageDraw.ImageDraw) -> None:
    """Faixa cinzenta inferior com topo ligeiramente inclinado e curvo."""
    pts = [(0, S), (0, BAND_TOP + 70)]
    for x in range(0, S + 1, 40):
        t = x / S
        pts.append((x, BAND_TOP + 70 - 70 * (t ** 0.7)))
    pts.append((S, S))
    d.polygon(pts, fill=GREY_BG)


def _starburst(card, cx, cy, r, pct):
    import math
    pts = []
    for i in range(32):
        ang = math.pi * 2 * i / 32 + 0.1
        rr = r if i % 2 == 0 else r * 0.86
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    shadow = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon([(x + 5, y + 9) for x, y in pts], fill=(0, 0, 0, 110))
    card.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(7))) if card.mode == "RGBA" else None
    return pts


def _price_block(card: Image.Image, price: str, old_price: str | None) -> Image.Image:
    """Bloco do preço: degradê preto, canto superior-esquerdo bem arredondado, selo de desconto com sombra."""
    card = card.convert("RGBA")
    x0, y0, w, h = 540, S - 150, S - 540, 190
    grad = Image.new("RGB", (w, h))
    gd = ImageDraw.Draw(grad)
    for x in range(w):
        t = (x / w) ** 1.3
        gd.line((x, 0, x, h), fill=tuple(int(BLACK_L[i] + (BLACK_R[i] - BLACK_L[i]) * t) for i in range(3)))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w + 60, h + 60), radius=95, fill=255)
    card.paste(grad, (x0, y0), mask)

    d = ImageDraw.Draw(card)
    fp = _font(80)
    pt = f"{price}€"
    d.text((S - 40 - d.textlength(pt, font=fp), S - 135), pt, font=fp, fill=WHITE)
    if old_price:
        fo = _font(46)
        ot = f"{old_price}€"
        ox = S - 60 - d.textlength(ot, font=fo)
        d.text((ox, S - 218), ot, font=fo, fill=GREY_TXT)
        d.line((ox - 8, S - 194, S - 52, S - 194), fill=RED, width=5)
        pct = discount(price, old_price)
        if pct:
            pts = _starburst(card, 470, S - 98, 70, pct)
            d = ImageDraw.Draw(card)
            d.polygon(pts, fill=GOLD)
            f = _font(40)
            tx = f"-{pct}%"
            d.text((470 - d.textlength(tx, font=f) / 2, S - 98 - 24), tx, font=f, fill=(190, 20, 20))
    return card.convert("RGB")


def make_card(photo: bytes, title: str, category: str, handle: str,
              price: str | None = None, old_price: str | None = None) -> bytes:
    try:
        product = Image.open(io.BytesIO(photo)).convert("RGB")
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError("imagem inválida") from e
    card = Image.new("RGB", (S, S), WHITE)
    d = ImageDraw.Draw(card)

    box = (S - 120, BAND_TOP - HEADER_H - 10)
    product.thumbnail(box, Image.LANCZOS)
    card.paste(product, ((S - product.width) // 2, HEADER_H + 15 + (box[1] - product.height) // 2))

    _band(d)
    d.rectangle((0, 0, S, HEADER_H), fill=NAVY)
    d.rectangle((0, HEADER_H, S, HEADER_H + 8), fill=ORANGE)
    f = _font(50)
    d.text(((S - d.textlength("MEGAPROMO", font=f)) / 2, 22), "MEGAPROMO", font=f, fill=WHITE)

    if LOGO.exists():
        logo = Image.open(LOGO).convert("RGBA").resize((200, 200), Image.LANCZOS)
        card.paste(logo, (50, S - 250), logo)

    lines = textwrap.wrap(title, 30 if not price else 34)
    max_lines = 2 if price else 3
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: len(lines[-1]) - 1].rstrip() + "…"
    y = BAND_TOP + 40
    if category and not price:
        d.text((290, y), category.upper()[:28], font=_font(28), fill=ORANGE)
        y += 46
    fs = 36 if price else 42
    for line in lines:
        d.text((290, y), line, font=_font(fs), fill=NAVY)
        y += fs + 12

    if price:
        card = _price_block(card, price, old_price)
    else:
        fh = _font(34)
        d.text((S - 50 - d.textlength(handle, font=fh), S - 70), handle, font=fh, fill=BLUE)

    out = io.BytesIO()
    card.save(out, "JPEG", quality=90)
    return out.getvalue()
