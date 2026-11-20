"""Cartão de imagem do canal: barra MEGAPROMO, foto do produto, logótipo e (opcional) preços. O título vai na legenda."""
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, UnidentifiedImageError

S = 1080
NAVY, ORANGE, WHITE = (16, 24, 48), (255, 122, 0), (255, 255, 255)
BLUE, BLACK_L, BLACK_R, GREY_BG, GREY_TXT, RED, GOLD = (0, 112, 206), (74, 76, 82), (0, 0, 0), (244, 245, 248), (100, 112, 135), (200, 30, 60), (255, 215, 0)
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


def _badge(card: Image.Image, cx: int, cy: int, r: int, pct: int, angle: float = 12) -> None:
    """Selo amarelo de desconto, inclinado na diagonal, com sombra."""
    import math
    n = 2 * r + 80
    layer = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    c = n / 2
    pts = []
    for i in range(32):
        ang = math.pi * 2 * i / 32 + 0.1
        rr = r if i % 2 == 0 else r * 0.86
        pts.append((c + rr * math.cos(ang), c + rr * math.sin(ang)))
    shadow = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon([(x + 5, y + 9) for x, y in pts], fill=(0, 0, 0, 110))
    layer.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(7)))
    d = ImageDraw.Draw(layer)
    d.polygon(pts, fill=GOLD)
    f, tx = _font(42), f"-{pct}%"
    d.text((c - d.textlength(tx, font=f) / 2, c - 25), tx, font=f, fill=(190, 20, 20))
    layer = layer.rotate(angle, resample=Image.BICUBIC)
    card.alpha_composite(layer, (int(cx - c), int(cy - c)))


def _price_block(card: Image.Image, price: str, old_price: str | None) -> Image.Image:
    """Bloco do preço: degradê preto, canto superior-esquerdo bem arredondado, selo de desconto com sombra."""
    card = card.convert("RGBA")
    x0, y0 = 553, 919
    w, h = S - x0, S - y0
    grad = Image.new("RGB", (w, h))
    gd = ImageDraw.Draw(grad)
    for x in range(w):
        t = x / w
        gd.line((x, 0, x, h), fill=tuple(int(BLACK_L[i] + (BLACK_R[i] - BLACK_L[i]) * t) for i in range(3)))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w + 120, h - 1), radius=88, fill=255)
    card.paste(grad, (x0, y0), mask)

    d = ImageDraw.Draw(card)
    fp = _font(84)
    pt = f"{price}€"
    d.text((S - 45 - d.textlength(pt, font=fp), y0 + (h - 84) // 2 - 6), pt, font=fp, fill=WHITE)
    if old_price:
        fo = _font(58)
        ot = f"{old_price}€"
        ox = S - 65 - d.textlength(ot, font=fo)
        d.text((ox, 826), ot, font=fo, fill=GREY_TXT)
        d.line((ox - 8, 861, S - 57, 861), fill=RED, width=6)
        pct = discount(price, old_price)
        if pct:
            _badge(card, 537, 905, 76, pct)
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

    if price:
        card = _price_block(card, price, old_price)
    else:
        fh = _font(52)
        d.text((290, S - 190), handle, font=fh, fill=NAVY)
        if category:
            d.text((290, S - 120), category.upper()[:28], font=_font(32), fill=ORANGE)

    out = io.BytesIO()
    card.save(out, "JPEG", quality=90)
    return out.getvalue()
