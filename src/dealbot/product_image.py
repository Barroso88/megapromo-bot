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


def _brand_bar_bottom(im: Image.Image) -> int | None:
    """Fundo de uma barra de marca colorida e larga no topo (ex: a faixa azul do canal de origem), se existir."""
    w, h = im.size
    up = im.crop((0, 0, w, int(h * 0.35)))
    _, sat, val = up.convert("HSV").split()
    mask = ImageChops.multiply(sat.point(lambda p: 255 if p > 110 else 0), val.point(lambda p: 255 if p > 100 else 0))
    k = max(3, (w // 60) | 1)
    box = mask.filter(ImageFilter.MinFilter(k)).getbbox()
    if not box:
        return None
    box = (max(box[0] - k // 2, 0), max(box[1] - k // 2, 0), min(box[2] + k // 2, w), min(box[3] + k // 2, up.height))
    bw, bh = box[2] - box[0], box[3] - box[1]
    if bw < 0.5 * w or bh > 0.25 * h or box[1] > 0.1 * h:      # uma barra de marca está mesmo no topo
        return None
    fill = mask.crop(box).histogram()[255] / (bw * bh)
    flush_banner = box[1] <= 2 and bw >= 0.9 * w              # barra de lado a lado encostada ao topo, mesmo com logótipo
    if fill < (0.45 if flush_banner else 0.6):                # preenchida, não um produto colorido
        return None
    return box[3] + 2


def _fade_bottom(img: Image.Image, y_end: int, length: int) -> Image.Image:
    """Esbate para branco as últimas `length` linhas do produto (até y_end): disfarça o corte seco."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    start = max(0, y_end - length)
    for y in range(start, h):
        alpha = 255 if y >= y_end else int(255 * (y - start) / max(1, length))
        mask.paste(alpha, (0, y, w, y + 1))
    out = img.copy()
    out.paste(Image.new("RGB", (w, h), (255, 255, 255)), (0, 0), mask)
    return out


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


def _main_rows(mask: Image.Image) -> tuple[int, int]:
    """Intervalo vertical do produto: o maior bloco de conteúdo, mais os blocos grandes ligados a ele.

    Restos pequenos separados por um espaço em branco (o preço antigo riscado acima da faixa, um título)
    ficam de fora.
    """
    h = mask.height
    rows = list(mask.resize((1, h), Image.BOX).tobytes())
    ink = [v > 2 for v in rows]
    gap_min = max(6, int(0.04 * h))
    segs, start, blank = [], None, 0
    for y, has in enumerate(ink):
        if has:
            if start is None:
                start = y
            blank, last = 0, y
        elif start is not None:
            blank += 1
            if blank >= gap_min:
                segs.append((start, last))
                start = None
    if start is not None:
        segs.append((start, last))
    if len(segs) < 2:
        return 0, h
    mass = [sum(rows[a:b + 1]) for a, b in segs]
    biggest = max(mass)
    keep = [seg for seg, m in zip(segs, mass) if m >= 0.3 * biggest]
    return keep[0][0], keep[-1][1] + 1


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
    bar = _brand_bar_bottom(im)
    if bar is not None:
        top = max(top, bar)
    overlay_found = top > 0 or bottom < h
    cut_below = bottom < h
    if bottom - top < MIN_KEEP * h:
        return photo
    region = im.crop((0, top, w, bottom))

    # Aperta ao conteúdo (tudo o que não é fundo branco); sem fundo branco não há nada a apertar.
    r, g, b = region.split()
    mask = ImageChops.darker(ImageChops.darker(r, g), b).point(lambda p: 255 if p < WHITE_LIMIT else 0)
    ink = mask.histogram()[255] / (region.width * region.height)
    if ink > 0.85:
        return _encode(region) if overlay_found else photo
    y0, y1 = _main_rows(mask)
    mask = mask.crop((0, y0, mask.width, y1))
    region = region.crop((0, y0, region.width, y1))
    box = mask.filter(ImageFilter.MinFilter(3)).getbbox()
    if not box or (box[2] - box[0]) * (box[3] - box[1]) < 0.04 * region.width * region.height:
        return _encode(region) if overlay_found else photo
    ink_box = box
    # Se o produto acaba numa linha reta e larga, foi a faixa de preço que o tapou: esbate em vez de deixar o corte seco.
    flat_cut = cut_below and mask.crop((box[0], box[3] - 3, box[2], box[3])).histogram()[255] >= 1.5 * (box[2] - box[0])
    pad = int(0.06 * max(box[2] - box[0], box[3] - box[1]))
    box = (max(box[0] - pad, 0), max(box[1] - pad, 0), min(box[2] + pad, region.width), min(box[3] + pad, region.height))
    out = region.crop(box)
    if flat_cut:
        out = _fade_bottom(out, ink_box[3] - box[1], max(12, int(0.14 * (ink_box[3] - ink_box[1]))))
    return _encode(out)
