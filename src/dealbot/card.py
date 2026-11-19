"""Cartão de imagem para o canal: foto do produto + faixa com categoria, título e nome do canal."""
import io
import textwrap

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

SIZE, PHOTO_H = 1080, 740
NAVY, ACCENT, WHITE = (16, 24, 48), (255, 153, 0), (255, 255, 255)
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


def make_card(photo: bytes, title: str, category: str, handle: str) -> bytes:
    try:
        product = Image.open(io.BytesIO(photo)).convert("RGB")
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError("imagem inválida") from e
    card = Image.new("RGB", (SIZE, SIZE), WHITE)
    box = (SIZE - 80, PHOTO_H - 60)
    product.thumbnail(box, Image.LANCZOS)
    card.paste(product, ((SIZE - product.width) // 2, 30 + (box[1] - product.height) // 2))

    d = ImageDraw.Draw(card)
    d.rectangle((0, PHOTO_H, SIZE, SIZE), fill=NAVY)
    d.rectangle((0, PHOTO_H, SIZE, PHOTO_H + 8), fill=ACCENT)
    y = PHOTO_H + 36
    if category:
        d.text((50, y), category.upper()[:30], font=_font(30), fill=ACCENT)
        y += 54
    lines = textwrap.wrap(title, 34)[:3]
    if len(textwrap.wrap(title, 34)) > 3:
        lines[-1] = lines[-1][:31].rstrip() + "…"
    for line in lines:
        d.text((50, y), line, font=_font(46), fill=WHITE)
        y += 58
    d.text((50, SIZE - 60), handle, font=_font(32), fill=ACCENT)
    out = io.BytesIO()
    card.save(out, "JPEG", quality=90)
    return out.getvalue()
