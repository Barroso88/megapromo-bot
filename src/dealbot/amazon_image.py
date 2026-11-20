"""Imagem principal do produto pelo ASIN (servidor de imagens da Amazon).

Uso por conta e risco do dono: este endereço não consta, pelo que se leu, do Acordo de Associados da Amazon.es
como fonte autorizada de imagens (a fonte documentada é a API). Pode ser desligado com AMAZON_IMAGES=0.
"""
import io
import re
import urllib.request

from PIL import Image

ASIN_RE = re.compile(r"[A-Z0-9]{10}")
URL = "https://images-eu.ssl-images-amazon.com/images/P/{asin}.01.LZZZZZZZ.jpg"
USER_AGENT = "MegaPromoDealBot/1.0 (automated bot; Amazon Associates deals channel)"   # robô declarado como tal
MAX_BYTES = 5 * 1024 * 1024
MIN_SIDE, MIN_LONG = 200, 300      # rejeita o GIF vazio de 1x1 que a Amazon devolve quando não há imagem


def fetch_amazon_image(asin: str, opener=urllib.request.urlopen) -> bytes | None:
    """Bytes da imagem principal do produto, ou None se não existir, for pequena demais ou o pedido falhar."""
    if not ASIN_RE.fullmatch(asin or ""):
        return None
    req = urllib.request.Request(URL.format(asin=asin), headers={"User-Agent": USER_AGENT})
    try:
        with opener(req, timeout=15) as resp:
            if getattr(resp, "status", 200) != 200:
                return None
            if not str(resp.headers.get("Content-Type", "")).startswith("image/"):
                return None
            data = resp.read(MAX_BYTES + 1)
    except Exception:
        return None
    if not data or len(data) > MAX_BYTES:
        return None
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return None
    w, h = im.size
    if min(w, h) < MIN_SIDE or max(w, h) < MIN_LONG:
        return None
    return data
