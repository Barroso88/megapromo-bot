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
    assert sum(img.getpixel((20, 20))) < 200           # barra escura no topo


def test_card_handles_tall_photo_and_empty_category():
    out = make_card(photo(100, 600), "x " * 300, "", "@canal")
    assert Image.open(io.BytesIO(out)).size == (1080, 1080)


def test_invalid_photo_raises_valueerror():
    import pytest
    with pytest.raises(ValueError):
        make_card(b"nao e imagem", "t", "c", "@canal")


def test_card_with_prices_has_black_price_block():
    out = make_card(photo(), "Televisor TCL 55", "Televisores", "@canal", price="284,80", old_price="507,25")
    img = Image.open(io.BytesIO(out))
    assert img.size == (1080, 1080)
    assert sum(img.getpixel((1000, 1060))) < 120     # bloco preto do preço


def test_card_without_prices_has_black_block_with_oferta():
    img = Image.open(io.BytesIO(make_card(photo(), "Televisor", "", "@canal")))
    assert img.size == (1080, 1080)
    # O bloco de preço existe sempre garantindo o formato da referência
    assert sum(img.getpixel((1000, 1060))) < 120


def test_discount_percent():
    from dealbot.card import discount
    assert discount("284,80", "507,25") == 44
    assert discount("1.299,00", "1.499,00") == 13
    assert discount("10,00", "10,00") is None and discount("x", "y") is None


def test_prices_with_euro_sign_are_accepted_without_doubling():
    out = make_card(photo(), "x", "", "@canal", price="284,80€", old_price=" 507,25 € ")
    assert Image.open(io.BytesIO(out)).size == (1080, 1080)
    from dealbot.card import discount
    assert discount("284,80€", "507,25€") == 44
