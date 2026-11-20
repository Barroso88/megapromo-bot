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


def has_blue(im: Image.Image) -> bool:
    raw = im.convert("RGB").resize((120, max(1, int(120 * im.height / im.width)))).tobytes()
    return any(raw[i + 2] > 180 and raw[i] < 120 and raw[i + 1] < 120 for i in range(0, len(raw), 3))


@needs_ocr
def test_brand_bar_at_the_top_of_the_photo_is_removed():
    # Como o "dezcontos": barra azul do canal de origem no topo, produto por baixo, faixa de preço em baixo.
    im = Image.new("RGB", (600, 500), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle((30, 20, 570, 60), fill=(60, 60, 240))
    d.ellipse((170, 110, 430, 290), fill=(30, 40, 60))
    d.polygon([(0, 500), (0, 360), (300, 345), (600, 335), (600, 500)], fill=(244, 244, 247))
    d.rounded_rectangle((300, 390, 600, 460), radius=24, fill=(240, 100, 20))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=95)
    out = Image.open(io.BytesIO(isolate_product(buf.getvalue())))
    assert not has_blue(out) and not has_orange(out)
    assert dark_ratio(out) > 0.3


@needs_ocr
def test_product_cut_by_the_price_band_fades_out_instead_of_a_hard_edge():
    im = Image.new("RGB", (600, 400), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle((150, 30, 450, 330), fill=(30, 40, 60))          # produto que continua por baixo da faixa
    d.rectangle((0, 262, 600, 400), fill=(244, 244, 247))        # faixa de preço tapa a parte de baixo
    d.rounded_rectangle((300, 300, 600, 380), radius=24, fill=(240, 100, 20))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=95)
    out = Image.open(io.BytesIO(isolate_product(buf.getvalue()))).convert("L")
    col = [out.getpixel((out.width // 2, y)) for y in range(out.height)]
    lower_half = col[len(col) // 2:]
    assert max(abs(a - b) for a, b in zip(lower_half, lower_half[1:])) < 60     # sem corte seco: passa a branco aos poucos
    assert min(lower_half) < 100 and lower_half[-1] > 235                       # mas o produto continua lá em cima


@needs_ocr
def test_full_width_brand_bar_flush_with_the_top_and_with_a_logo_is_removed():
    # Como a barra "dezcontos" real: azul de lado a lado, encostada ao topo, com logótipo branco (preenchimento ~50 %).
    im = Image.new("RGB", (600, 500), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 600, 60), fill=(66, 65, 243))
    d.rectangle((30, 8, 300, 52), fill=(255, 255, 255))
    d.rectangle((350, 8, 450, 52), fill=(255, 255, 255))
    d.ellipse((150, 110, 430, 290), fill=(30, 40, 60))
    d.polygon([(0, 500), (0, 360), (300, 345), (600, 335), (600, 500)], fill=(244, 244, 247))
    d.rounded_rectangle((300, 390, 600, 460), radius=24, fill=(240, 100, 20))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=95)
    out = Image.open(io.BytesIO(isolate_product(buf.getvalue())))
    assert not has_blue(out) and not has_orange(out)


@needs_ocr
def test_a_saturated_product_near_the_top_is_not_mistaken_for_a_brand_bar():
    im = Image.new("RGB", (600, 500), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle((80, 80, 520, 160), fill=(40, 40, 230))          # produto azul largo, mas longe do topo
    d.rectangle((80, 160, 520, 300), fill=(30, 40, 60))
    d.polygon([(0, 500), (0, 360), (300, 345), (600, 335), (600, 500)], fill=(244, 244, 247))
    d.rounded_rectangle((300, 390, 600, 460), radius=24, fill=(240, 100, 20))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=95)
    out = Image.open(io.BytesIO(isolate_product(buf.getvalue())))
    assert has_blue(out)                                         # o produto azul fica


def test_trim_background_crops_white_margins_of_an_amazon_style_image():
    from dealbot.product_image import trim_background
    im = Image.new("RGB", (500, 500), (255, 255, 255))
    ImageDraw.Draw(im).rectangle((200, 150, 300, 350), fill=(120, 60, 20))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=95)
    out = Image.open(io.BytesIO(trim_background(buf.getvalue())))
    assert out.width < 160 and out.height < 260 and dark_ratio(out) > 0.25      # só o produto, com margem pequena


def test_trim_background_leaves_full_images_blank_images_and_garbage_alone():
    from dealbot.product_image import trim_background
    full = Image.new("RGB", (300, 300), (90, 120, 60))
    buf = io.BytesIO()
    full.save(buf, "PNG")
    assert trim_background(buf.getvalue()) == buf.getvalue()                    # sem fundo branco: não corta
    white = io.BytesIO()
    Image.new("RGB", (300, 300), (255, 255, 255)).save(white, "PNG")
    assert trim_background(white.getvalue()) == white.getvalue()                # nada a recortar
    assert trim_background(b"nao e imagem") == b"nao e imagem"


def test_trim_background_keeps_most_of_an_image_that_already_fills_the_frame():
    from dealbot.product_image import trim_background
    im = Image.new("RGB", (400, 400), (255, 255, 255))
    ImageDraw.Draw(im).rectangle((10, 10, 390, 390), fill=(30, 40, 60))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    assert trim_background(buf.getvalue()) == buf.getvalue()                    # já ocupa >85 %: igual
