import io
import itertools
import logging
import re
from pathlib import Path
from PIL import Image, ImageChops, ImageFilter, ImageOps

logger = logging.getLogger("dealbot.ocr")

try:
    import pytesseract
except ImportError:
    pytesseract = None


def extract_prices_from_text(text: str) -> tuple[str | None, str | None]:
    """Extrai (preco_antes, preco_depois) de textos típicos de promoções."""
    if not text:
        return None, None

    # Normaliza
    clean_text = text.replace("€", " € ")

    # Padrão: De X por Y ou Antes X Agora Y ou ❌ X ✅ Y
    pattern_both = re.search(
        r"(?:de|antes|❌|~~|~)\s*:?\s*(\d+[\.,]\d{1,2}\s*€?|\d+\s*€)\s*(?:por|para|agora|✅|->|➔|➜|-|>)\s*:?\s*(\d+[\.,]\d{1,2}\s*€?|\d+\s*€)",
        clean_text,
        re.IGNORECASE,
    )
    if pattern_both:
        p1, p2 = pattern_both.group(1).strip(), pattern_both.group(2).strip()
        p1 = p1 if "€" in p1 else f"{p1}€"
        p2 = p2 if "€" in p2 else f"{p2}€"
        return p1.replace(" ", ""), p2.replace(" ", "")

    # Procura valores em euros (€)
    euros = re.findall(r"(\d+[\.,]\d{1,2}\s*€|\d+\s*€)", clean_text)
    euros = [e.replace(" ", "") for e in euros]
    if len(euros) >= 2:
        return euros[0], euros[1]
    elif len(euros) == 1:
        return None, euros[0]

    return None, None


PRICE_TOKEN = re.compile(r"(?<![\d,.])(\d{1,3}(?:\.\d{3})+|\d{1,5})[.,](\d{2})(?!\d)")
OCR_CONFIG = "--psm 11 -c tessedit_char_whitelist=0123456789,.€"
SCALE = 3
MIN_VOTES = 2


def _ocr_variants(im: Image.Image):
    """Imagens a ler: o preço riscado (texto escuro) e o preço branco dentro de um bloco colorido."""
    im = im.convert("RGB")
    big = im.resize((im.width * SCALE, im.height * SCALE), Image.LANCZOS)
    gray = big.convert("L")
    w, h = gray.size
    bottom = (0, int(h * 0.55), w, h)
    yield gray.crop(bottom)
    # A mediana apaga linhas finas (o risco do preço antigo) mantendo os traços grossos dos algarismos.
    nostrike = im.convert("L").filter(ImageFilter.MedianFilter(5)).resize((w, h), Image.LANCZOS)
    yield nostrike.crop(bottom)
    yield nostrike.point(lambda p: 255 if p > 130 else 0).crop(bottom)
    for t in (90, 130):
        yield gray.point(lambda p, t=t: 255 if p > t else 0).crop(bottom)
    yield gray
    yield from _colored_block_variants(big)


def _colored_block_variants(big: Image.Image):
    """Localiza o bloco colorido de preço (zona saturada na metade de baixo) e isola o texto branco."""
    w, h = big.size
    y0 = int(h * 0.5)
    low = big.crop((0, y0, w, h))
    _, sat, val = low.convert("HSV").split()
    mask = ImageChops.multiply(sat.point(lambda p: 255 if p > 110 else 0), val.point(lambda p: 255 if p > 100 else 0))
    box = mask.filter(ImageFilter.MinFilter(9)).getbbox()
    if not box:
        return
    pad = 6
    box = (max(box[0] - pad, 0), max(box[1] - pad, 0), min(box[2] + pad, w), min(box[3] + pad, h - y0))
    r, g, b = low.crop(box).split()
    min_ch = ImageChops.darker(ImageChops.darker(r, g), b)                      # min(R,G,B): branco = alto
    for t in (150, 185, 220):
        text = min_ch.point(lambda p, t=t: 0 if p > t else 255)                 # texto preto sobre branco
        yield ImageOps.expand(text, border=30, fill=255)


def _fmt(value: float) -> str:
    return f"{value:.2f}".replace(".", ",") + "€"


PRICE_TOKEN_STRICT = re.compile(r"(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})")
DIGITS_CONFIG = "--psm 7 -c tessedit_char_whitelist=0123456789,."


def _value(match) -> float:
    return float(f"{match.group(1).replace('.', '')}.{match.group(2)}")


def _discount_pct(old: float, new: float) -> float:
    return (1 - new / old) * 100


def _price_block_box(im: Image.Image):
    """Bloco do preço atual: zona LARANJA/vermelha e saturada na metade de baixo (não confunde com produtos azuis)."""
    w, h = im.size
    low = im.crop((0, h // 2, w, h))
    hue, sat, val = low.convert("HSV").split()
    orange = hue.point(lambda p: 255 if (p <= 30 or p >= 240) else 0)
    mask = ImageChops.multiply(ImageChops.multiply(orange, sat.point(lambda p: 255 if p > 110 else 0)),
                               val.point(lambda p: 255 if p > 100 else 0))
    k = max(3, (w // 60) | 1)
    box = mask.filter(ImageFilter.MinFilter(k)).getbbox()
    if not box or (box[2] - box[0]) * (box[3] - box[1]) < 0.004 * w * h:
        return None
    return (box[0], box[1] + h // 2, box[2], box[3] + h // 2)


def _tight(bw: Image.Image, target_h: int = 130, border: int = 12):
    """Recorte justo do texto (preto sobre branco), ampliado para ~target_h de altura."""
    bb = ImageOps.invert(bw).getbbox()
    if not bb:
        return None
    crop = bw.crop(bb)
    scale = max(1.0, target_h / max(1, crop.height))
    crop = ImageOps.expand(crop, border=border, fill=255)
    return crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.LANCZOS)


def _inpaint_strike(bw: Image.Image) -> Image.Image:
    """Reconstrói o risco do preço antigo: a faixa de linhas quase todas escuras fica escura só onde por cima e por baixo também é."""
    w, h = bw.size
    px = bw.load()
    rows = [y for y in range(h) if sum(1 for x in range(w) if px[x, y] == 0) > 0.5 * w]
    if not rows:
        return bw
    top, bottom = min(rows), max(rows)
    if bottom - top > h * 0.35:
        return bw
    above, below = max(top - 1, 0), min(bottom + 1, h - 1)
    for y in range(top, bottom + 1):
        for x in range(w):
            px[x, y] = 0 if (px[x, above] == 0 and px[x, below] == 0) else 255
    return bw


def _drop_last_glyph(bw: Image.Image) -> Image.Image:
    """Corta o último símbolo (o €), que o OCR de dígitos lê como números soltos."""
    w, h = bw.size
    px = bw.load()
    cols = [any(px[x, y] == 0 for y in range(h)) for x in range(w)] + [False]
    runs, start = [], None
    for x, dark in enumerate(cols):
        if dark and start is None:
            start = x
        elif not dark and start is not None:
            runs.append((start, x))
            start = None
    return bw.crop((0, 0, max(runs[-1][0] - 2, 1), h)) if len(runs) >= 5 else bw


def _read_digits(img: Image.Image) -> float | None:
    try:
        text = pytesseract.image_to_string(img, config=DIGITS_CONFIG)
    except Exception as e:
        logger.debug("OCR: leitura por recorte falhou: %s: %s", type(e).__name__, e)
        return None
    m = PRICE_TOKEN_STRICT.search(text)
    return _value(m) if m else None


def _block_new_votes(im: Image.Image, box) -> dict[float, int]:
    """Preço atual: texto branco dentro do bloco laranja, lido em recorte justo e só com dígitos."""
    r, g, b = im.crop(box).split()
    white = ImageChops.darker(ImageChops.darker(r, g), b)
    votes: dict[float, int] = {}
    for t in (170, 200, 225):
        crop = _tight(white.point(lambda p, t=t: 0 if p > t else 255), target_h=110, border=20)
        value = _read_digits(crop) if crop else None
        if value and 0.5 <= value <= 20000:
            votes[value] = votes.get(value, 0) + 1
    return votes


def _old_price_votes(im: Image.Image, box) -> dict[float, int]:
    """Preço antigo (riscado): zona logo acima do bloco, com o risco reconstruído e sem o símbolo €."""
    height = box[3] - box[1]
    y1 = box[1] - 4
    y0 = max(0, y1 - int(height * 0.6))
    region = im.crop((box[0], y0, im.width, y1)).convert("L")
    votes: dict[float, int] = {}
    for t in (90, 110, 130, 150):
        bw = _drop_last_glyph(_inpaint_strike(region.point(lambda p, t=t: 0 if p < t else 255)))
        crop = _tight(bw)
        value = _read_digits(crop) if crop else None
        if value and 0.5 <= value <= 20000:
            votes[value] = votes.get(value, 0) + 1
    return votes


def choose_pair(block_new, block_old, global_votes, stated_pct):
    """Escolhe (antigo, atual) a partir dos votos das várias leituras.

    O preço atual vem do recorte do bloco laranja; o antigo vota-se entre as leituras do recorte e as globais.
    Se o texto do post diz a percentagem ("-55%"), só serve um antigo cujo desconto bata (±1,5): é o árbitro
    independente que corrige enganos como 127,07 lido como 427,07. Sem percentagem exige-se 2 votos.
    """
    def plausible(old, new):
        return 3 <= _discount_pct(old, new) <= 90

    # O valor do bloco só é aceite se as 3 leituras concordarem ou se pelo menos 2 leituras globais o confirmarem:
    # um bloco mal lido (ex: 99,99 em vez de 59,99) não pode sobrepor-se às leituras globais.
    news = [v for v, n in block_new.items() if n >= 3 or (n >= 2 and global_votes.get(v, 0) >= 2)]
    if news:
        new = max(news, key=lambda v: (block_new[v] + global_votes.get(v, 0), -v))
        pool: dict[float, int] = dict(block_old)
        for v, n in global_votes.items():
            if v > new:
                pool[v] = pool.get(v, 0) + n
        cands = [v for v in pool if plausible(v, new)]
        if stated_pct is not None:
            near = [v for v in cands if abs(_discount_pct(v, new) - stated_pct) <= 1.5]
            if not near:
                return None
            best = max(near, key=lambda v: (pool[v], -abs(_discount_pct(v, new) - stated_pct)))
            return _fmt(best), _fmt(new)
        reliable = [v for v in cands if pool[v] >= MIN_VOTES]
        if not reliable:
            return None
        best = max(reliable, key=lambda v: (pool[v], v))
        return _fmt(best), _fmt(new)

    # Sem bloco legível: pares entre as leituras globais (2+ votos), o primeiro plausível; com % do texto, o que bater.
    reliable = sorted((v for v, n in global_votes.items() if n >= MIN_VOTES), key=lambda v: (-global_votes[v], -v))
    for a, b in itertools.combinations(reliable, 2):
        new, old = min(a, b), max(a, b)
        if plausible(old, new) and (stated_pct is None or abs(_discount_pct(old, new) - stated_pct) <= 1.5):
            return _fmt(old), _fmt(new)
    return None


def extract_prices_from_image(photo_bytes: bytes, stated_pct: int | None = None) -> tuple[str | None, str | None]:
    """Lê por OCR os preços gravados na imagem: devolve (antigo/riscado, atual).

    Só devolve alguma coisa quando encontra dois valores distintos e plausíveis; o maior é o antigo,
    o menor o atual. Um valor isolado não diz o que é, por isso nunca é devolvido.
    `stated_pct` é o desconto escrito no texto do post (se houver) e serve de árbitro entre leituras.
    """
    if not pytesseract or not photo_bytes:
        return None, None
    try:
        im = Image.open(io.BytesIO(photo_bytes))
        im.load()
        im = im.convert("RGB")
    except Exception:
        return None, None

    block_new: dict[float, int] = {}
    block_old: dict[float, int] = {}
    try:
        box = _price_block_box(im)
        if box:
            block_new = _block_new_votes(im, box)
            block_old = _old_price_votes(im, box)
    except Exception as e:
        logger.warning("OCR por recorte falhou: %s: %s", type(e).__name__, e)

    global_votes = _global_votes(im)
    pair = choose_pair(block_new, block_old, global_votes, stated_pct)
    return pair if pair else (None, None)


def _global_votes(im: Image.Image) -> dict[float, int]:
    """Leituras da imagem toda, em várias variantes; cada leitura que falha é ignorada, não anula as outras."""
    votes: dict[float, int] = {}
    try:
        variants = list(_ocr_variants(im))
    except Exception as e:
        logger.warning("OCR: não foi possível preparar a imagem: %s: %s", type(e).__name__, e)
        return votes
    failures = 0
    for variant in variants:
        for psm in ("11", "7"):
            try:
                text = pytesseract.image_to_string(variant, config=OCR_CONFIG.replace("11", psm))
            except Exception as e:           # ex: 'Image too small to scale' no Tesseract 5.5.0 do contentor
                failures += 1
                logger.debug("OCR: leitura falhou (psm %s): %s: %s", psm, type(e).__name__, e)
                continue
            for m in PRICE_TOKEN.finditer(text):
                value = float(f"{m.group(1).replace('.', '')}.{m.group(2)}")
                if 0.5 <= value <= 20000:
                    votes[value] = votes.get(value, 0) + 1
    if failures:
        logger.info("OCR: %d leituras falharam e foram ignoradas", failures)
    return votes


def extract_discount_pct(text: str) -> int | None:
    """Percentagem de desconto escrita no texto (ex: '30%!'); só valores plausíveis (5-90)."""
    for m in re.finditer(r"(?<![\d,.])(\d{1,2})\s*%", text or ""):
        if 5 <= int(m.group(1)) <= 90:
            return int(m.group(1))
    return None


def _agrees_with_text(before: str, after: str, text: str) -> bool:
    """Se o texto diz '30%', o desconto calculado pelos preços lidos tem de bater (±4 pontos)."""
    stated = extract_discount_pct(text)
    if stated is None:
        return True
    old, new = (float(p.replace("€", "").replace(".", "").replace(",", ".")) for p in (before, after))
    return abs((1 - new / old) * 100 - stated) <= 4


def extract_prices(text: str, photo_bytes: bytes | None = None) -> tuple[str | None, str | None]:
    """(preço antigo, preço atual). Os preços lidos na imagem têm prioridade; depois o par do texto.

    Um preço isolado nunca é devolvido: não se sabe se é o antigo ou o atual.
    """
    if photo_bytes:
        before, after = extract_prices_from_image(photo_bytes, stated_pct=extract_discount_pct(text))
        if before and after and _agrees_with_text(before, after, text):
            return before, after
    before, after = extract_prices_from_text(text)
    if before and after:
        return before, after
    return None, None
