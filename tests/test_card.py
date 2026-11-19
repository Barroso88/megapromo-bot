import io

from PIL import Image

from dealbot.card import make_card


def photo(w=300, h=200):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 30, 30)).save(buf, "JPEG")
    return buf.getvalue()


def test_card_is_square_jpeg_with_product_and_band():
    out = make_card(photo(), "Televisor TCL 4K de 55 polegadas com Fire TV e Alexa integrada", "Televisores", "@canal")
    img = Image.open(io.BytesIO(out))
    assert img.format == "JPEG" and img.size == (1080, 1080)
    assert img.getpixel((540, 300))[0] > 150          # produto visível na zona da foto
    assert sum(img.getpixel((20, 1070))) < 200         # faixa escura em baixo


def test_card_handles_tall_photo_and_empty_category():
    out = make_card(photo(100, 600), "x " * 300, "", "@canal")
    assert Image.open(io.BytesIO(out)).size == (1080, 1080)


def test_invalid_photo_raises_valueerror():
    import pytest
    with pytest.raises(ValueError):
        make_card(b"nao e imagem", "t", "c", "@canal")
