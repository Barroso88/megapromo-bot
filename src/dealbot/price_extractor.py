import re
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io
from pathlib import Path

LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"

def circular_crop(im: Image.Image) -> Image.Image:
    """Recorta uma imagem num círculo perfeito com transparência (RGBA)."""
    im = im.convert("RGBA")
    size = im.size
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((4, 4, size[0] - 5, size[1] - 5), fill=255)
    output = ImageOps.fit(im, mask.size, centering=(0.5, 0.5))
    output.putalpha(mask)
    return output

def extract_prices_from_text(text: str) -> tuple[str | None, str | None]:
    """Extrai (preco_antes, preco_depois) de textos típicos de promoções."""
    if not text:
        return None, None
        
    # Padrão: De X por Y ou Antes X Agora Y ou ❌ X ✅ Y
    pattern_both = re.search(
        r"(?:de|antes|❌|~~|~)\s*:?\s*(\d+[\.,]\d{1,2}\s*€?|\d+\s*€)\s*(?:por|para|agora|✅|->|➔|➜|-|>)\s*:?\s*(\d+[\.,]\d{1,2}\s*€?|\d+\s*€)",
        text,
        re.IGNORECASE
    )
    if pattern_both:
        p1, p2 = pattern_both.group(1).strip(), pattern_both.group(2).strip()
        p1 = p1 if "€" in p1 else f"{p1}€"
        p2 = p2 if "€" in p2 else f"{p2}€"
        return p1, p2

    # Padrão: busca todos os valores em euros (€)
    euros = re.findall(r"(\d+[\.,]\d{1,2}\s*€|\d+\s*€|€\s*\d+[\.,]?\d*)", text)
    if len(euros) >= 2:
        return euros[0].strip(), euros[1].strip()
    elif len(euros) == 1:
        return None, euros[0].strip()

    return None, None
