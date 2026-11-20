import io
import shutil

import pytest
from PIL import Image, ImageDraw

from dealbot.card import _font
from dealbot.product_image import isolate_product

needs_ocr = pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract não instalado")


def post_image(overlay=True, w=600, h=400) -> bytes:
    """Foto de produto sobre fundo branco; opcionalmente com a faixa de preço de outro canal por baixo."""
    im = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.ellipse((170, 40, 430, 200), fill=(30, 40, 60))                      # produto escuro
    d.ellipse((190, 190, 410, 215), fill=(225, 225, 225))                  # sombra
    if overlay:
        d.polygon([(0, 400), (0, 270), (300, 255), (600, 240), (600, 400)], fill=(244, 244, 247))
        d.text((30, 310), "disponível na", font=_font(16), fill=(60, 60, 60))
        d.text((30, 335), "amazon", font=_font(30), fill=(20, 20, 20))
        d.text((330, 262), "25,40€", font=_font(26), fill=(80, 80, 80))
        d.rounded_rectangle((300, 300, 600, 370), radius=24, fill=(240, 100, 20))
        d.text((360, 312), "17,77€", font=_font(40), fill=(255, 255, 255))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=95)
    return out.getvalue()


def has_orange(im: Image.Image) -> bool:
    raw = im.convert("RGB").resize((120, max(1, int(120 * im.height / im.width)))).tobytes()
    return any(raw[i] > 200 and 60 < raw[i + 1] < 140 and raw[i + 2] < 80 for i in range(0, len(raw), 3))


def dark_ratio(im: Image.Image) -> float:
    hist = im.convert("L").histogram()
    return sum(hist[:80]) / sum(hist)


@needs_ocr
def test_overlay_band_is_removed_and_product_kept():
    out = Image.open(io.BytesIO(isolate_product(post_image())))
    assert not has_orange(out)                       # bloco laranja do preço fora
    assert out.height < 260                          # faixa de baixo cortada
    assert dark_ratio(out) > 0.2                     # o produto (escuro) ocupa boa parte do recorte


@needs_ocr
def test_nothing_of_the_band_below_the_product_is_left():
    out = Image.open(io.BytesIO(isolate_product(post_image())))
    assert out.height < 215                          # produto+sombra ~175 px de altura mais margem; o resto foi cortado


def test_image_without_overlay_is_cropped_tight_around_product():
    out = Image.open(io.BytesIO(isolate_product(post_image(overlay=False))))
    assert out.width < 600 and out.height < 400
    assert dark_ratio(out) > 0.25


def test_full_bleed_photo_is_returned_unchanged():
    im = Image.new("RGB", (300, 200), (90, 120, 60))
    ImageDraw.Draw(im).ellipse((50, 30, 250, 170), fill=(40, 60, 30))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    assert isolate_product(buf.getvalue()) == buf.getvalue()


def test_invalid_bytes_are_returned_unchanged():
    assert isolate_product(b"nao e imagem") == b"nao e imagem"


@needs_ocr
def test_overlay_covering_most_of_the_image_falls_back_to_original():
    im = Image.new("RGB", (300, 300), (240, 100, 20))
    ImageDraw.Draw(im).text((30, 120), "17,77€", font=_font(50), fill=(255, 255, 255))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    assert isolate_product(buf.getvalue()) == buf.getvalue()


@needs_ocr
def test_price_text_above_the_colored_block_is_cut_even_if_ocr_cannot_read_it():
    # Como no post real: o preço antigo riscado fica acima do bloco, separado do produto por um espaço em branco.
    im = Image.new("RGB", (600, 400), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.ellipse((170, 40, 430, 200), fill=(30, 40, 60))
    d.polygon([(0, 400), (0, 262), (300, 250), (600, 240), (600, 400)], fill=(244, 244, 247))
    d.rectangle((420, 252, 560, 282), fill=(110, 110, 110))                    # "preço riscado" ilegível
    d.rounded_rectangle((300, 300, 600, 370), radius=24, fill=(240, 100, 20))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=95)
    out = Image.open(io.BytesIO(isolate_product(buf.getvalue())))
    assert out.height < 215                       # o retângulo cinzento (preço) já não está no recorte
    assert not has_orange(out)
