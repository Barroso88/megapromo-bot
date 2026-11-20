"""Isola a foto do produto numa imagem de outro canal, sem faixa de preço, logótipo da Amazon nem marca do canal."""
import io
import re

from PIL import Image, ImageChops, ImageFilter

try:
    import pytesseract
except ImportError:
    pytesseract = None

# Texto típico das faixas: preços, "disponível na amazon", handles e nomes de canais, percentagens.
OVERLAY_RE = re.compile(
    r"(€|\d+[.,]\d{2}|amazon|dispon|t\.me|@|desconto|oferta|promo|cup[oõ]es|canal|www|\.com|\.pt|%)", re.I
)
MIN_KEEP = 0.30       # se o produto ficaria com menos de 30 % da altura, não se recorta
WHITE_LIMIT = 215     # pixels com min(R,G,B) abaixo disto contam como "conteúdo" (não fundo branco)


def _colored_block_top(im: Image.Image) -> int | None:
    """Topo do bloco colorido de preço (zona saturada na metade de baixo), se existir."""
    w, h = im.size
    low = im.crop((0, h // 2, w, h))
    _, sat, val = low.convert("HSV").split()
    mask = ImageChops.multiply(sat.point(lambda p: 255 if p > 110 else 0), val.point(lambda p: 255 if p > 100 else 0))
    k = max(3, (w // 60) | 1)
    box = mask.filter(ImageFilter.MinFilter(k)).getbbox()
    if not box or (box[2] - box[0]) * (box[3] - box[1]) < 0.005 * w * h:
        return None
    if box[0] <= 1 and box[1] <= 1 and box[2] >= w - 1:
        return None                                   # cobre a largura toda e começa no topo: é o fundo, não um bloco
    return h // 2 + box[1]


def _overlay_text_limits(im: Image.Image) -> tuple[int, int]:
    """(topo, base) da zona útil, segundo o texto de sobreposição lido por OCR (palavras na faixa de cima/baixo)."""
    w, h = im.size
    top, bottom = 0, h
    if not pytesseract:
        return top, bottom
    scale = max(1, round(1200 / w))
    big = im.convert("L").resize((w * scale, h * scale), Image.LANCZOS)
    try:
        data = pytesseract.image_to_data(big, config="--psm 11", output_type=pytesseract.Output.DICT)
    except Exception:
        return top, bottom
    for text, conf, y, hh in zip(data["text"], data["conf"], data["top"], data["height"]):
        try:
            if not text.strip() or float(conf) < 40 or not OVERLAY_RE.search(text):
                continue
        except ValueError:
            continue
        y0, y1 = y / scale, (y + hh) / scale
        if y0 >= 0.45 * h:
            bottom = min(bottom, int(y0))
        elif y1 <= 0.2 * h:
            top = max(top, int(y1))
    return top, bottom


def _encode(im: Image.Image) -> bytes:
    out = io.BytesIO()
    im.convert("RGB").save(out, "JPEG", quality=92)
    return out.getvalue()


def isolate_product(photo: bytes) -> bytes:
    """Devolve a foto cortada só ao produto; se não der para isolar com segurança, devolve a original."""
    try:
        im = Image.open(io.BytesIO(photo))
        im.load()
        im = im.convert("RGB")
    except Exception:
        return photo
    w, h = im.size
    top, bottom = _overlay_text_limits(im)
    block = _colored_block_top(im)
    if block is not None:
        bottom = min(bottom, block)
    overlay_found = top > 0 or bottom < h
    if bottom - top < MIN_KEEP * h:
        return photo
    region = im.crop((0, top, w, bottom))

    # Aperta ao conteúdo (tudo o que não é fundo branco); sem fundo branco não há nada a apertar.
    r, g, b = region.split()
    mask = ImageChops.darker(ImageChops.darker(r, g), b).point(lambda p: 255 if p < WHITE_LIMIT else 0)
    ink = mask.histogram()[255] / (region.width * region.height)
    if ink > 0.85:
        return _encode(region) if overlay_found else photo
    box = mask.filter(ImageFilter.MinFilter(3)).getbbox()
    if not box or (box[2] - box[0]) * (box[3] - box[1]) < 0.04 * region.width * region.height:
        return _encode(region) if overlay_found else photo
    pad = int(0.06 * max(box[2] - box[0], box[3] - box[1]))
    box = (max(box[0] - pad, 0), max(box[1] - pad, 0), min(box[2] + pad, region.width), min(box[3] + pad, region.height))
    return _encode(region.crop(box))
