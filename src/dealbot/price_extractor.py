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


def extract_prices_from_image(photo_bytes: bytes) -> tuple[str | None, str | None]:
    """Lê por OCR os preços gravados na imagem: devolve (antigo/riscado, atual).

    Só devolve alguma coisa quando encontra dois valores distintos e plausíveis; o maior é o antigo,
    o menor o atual. Um valor isolado não diz o que é, por isso nunca é devolvido.
    """
    if not pytesseract or not photo_bytes:
        return None, None
    try:
        im = Image.open(io.BytesIO(photo_bytes))
        im.load()
    except Exception:
        return None, None
    votes: dict[float, int] = {}
    try:
        variants = list(_ocr_variants(im))
    except Exception as e:
        logger.warning("OCR: não foi possível preparar a imagem: %s: %s", type(e).__name__, e)
        return None, None
    failures = 0
    for variant in variants:
        for psm in ("11", "7"):
            try:
                text = pytesseract.image_to_string(variant, config=OCR_CONFIG.replace("11", psm))
            except Exception as e:           # uma variante que falha (ex: 'Image too small to scale') não anula as outras
                failures += 1
                logger.debug("OCR: leitura falhou (psm %s): %s: %s", psm, type(e).__name__, e)
                continue
            for m in PRICE_TOKEN.finditer(text):
                value = float(f"{m.group(1).replace('.', '')}.{m.group(2)}")
                if 0.5 <= value <= 20000:
                    votes[value] = votes.get(value, 0) + 1
    if failures:
        logger.info("OCR: %d leituras falharam e foram ignoradas", failures)
    # Cada preço tem de ter sido lido em pelo menos 2 variantes: leituras soltas costumam ser enganos do OCR.
    reliable = sorted((v for v, n in votes.items() if n >= MIN_VOTES), key=lambda v: (-votes[v], -v))
    # Primeiro par plausível (desconto 3-90 %): um número lido por engano não esconde o par verdadeiro.
    for a, b in itertools.combinations(reliable, 2):
        new, old = min(a, b), max(a, b)
        if 3 <= (1 - new / old) * 100 <= 90:
            return _fmt(old), _fmt(new)
    return None, None


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
        before, after = extract_prices_from_image(photo_bytes)
        if before and after and _agrees_with_text(before, after, text):
            return before, after
    before, after = extract_prices_from_text(text)
    if before and after:
        return before, after
    return None, None
