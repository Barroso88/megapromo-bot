import io
import re
from pathlib import Path
from PIL import Image

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


def extract_prices_from_image(photo_bytes: bytes) -> tuple[str | None, str | None]:
    """Usa OCR para extrair preços gravados diretamente na imagem do produto/banner."""
    if not pytesseract or not photo_bytes:
        return None, None
    try:
        im = Image.open(io.BytesIO(photo_bytes))
        # Executa OCR no modo bloco de texto e modo sparse
        ocr_text = pytesseract.image_to_string(im)
        p_before, p_after = extract_prices_from_text(ocr_text)
        if p_after:
            return p_before, p_after

        # Tenta com configuração PSM 11 (procurar o máximo de texto possível)
        ocr_text_alt = pytesseract.image_to_string(im, config="--psm 11")
        return extract_prices_from_text(ocr_text_alt)
    except Exception:
        return None, None


def extract_prices(text: str, photo_bytes: bytes | None = None) -> tuple[str | None, str | None]:
    """
    Tenta extrair do texto da mensagem. Se não encontrar,
    analisa a imagem com OCR para capturar os preços gravados no banner!
    """
    p_before, p_after = extract_prices_from_text(text)
    if p_after:
        return p_before, p_after

    if photo_bytes:
        return extract_prices_from_image(photo_bytes)

    return None, None
