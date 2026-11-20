import asyncio
import io
import shutil
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image, ImageDraw

from dealbot.card import _font, discount
from dealbot.config import ListenerConfig
from dealbot.listener import process_incoming_message
from dealbot.price_extractor import extract_prices, extract_prices_from_image
from dealbot.state import State

needs_ocr = pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract não instalado")


def banner(old="25,40€", new="17,77€", strike=True) -> bytes:
    """Imagem tipo post de outro canal: preço antigo riscado a cinzento e preço atual branco sobre laranja."""
    im = Image.new("RGB", (572, 349), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.ellipse((150, 40, 420, 200), fill=(40, 40, 50))                       # "produto"
    d.text((300, 232), old, font=_font(26), fill=(70, 70, 70))
    if strike:
        d.line((296, 247, 380, 247), fill=(30, 30, 30), width=2)
    d.rounded_rectangle((250, 268, 440, 322), radius=10, fill=(240, 100, 20))
    d.text((275, 275), new, font=_font(34), fill=(255, 255, 255))
    out = io.BytesIO()
    im.save(out, "JPEG")
    return out.getvalue()


@needs_ocr
def test_ocr_reads_struck_old_price_and_current_price():
    assert extract_prices_from_image(banner()) == ("25,40€", "17,77€")


@needs_ocr
def test_ocr_order_is_by_value_not_position():
    assert extract_prices_from_image(banner(old="79,99€", new="59,99€")) == ("79,99€", "59,99€")


@needs_ocr
def test_ocr_with_a_single_price_returns_nothing():
    im = Image.new("RGB", (400, 200), (255, 255, 255))
    ImageDraw.Draw(im).text((50, 80), "25,40€", font=_font(40), fill=(0, 0, 0))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    assert extract_prices_from_image(buf.getvalue()) == (None, None)


def test_garbage_image_returns_nothing():
    assert extract_prices_from_image(b"nao e imagem") == (None, None)


def test_single_text_price_is_never_returned_as_current_price():
    assert extract_prices("Gafas Hawkers 25,40€ superoferta") == (None, None)
    assert extract_prices("❌ Antes: 507,25€ ✅ Agora: 284,80€") == ("507,25€", "284,80€")


@needs_ocr
def test_image_prices_win_over_a_lone_text_price():
    assert extract_prices("Gafas 25,40€", photo_bytes=banner()) == ("25,40€", "17,77€")


@needs_ocr
def test_image_prices_that_contradict_the_stated_discount_are_discarded():
    # texto diz 50%, mas os preços da imagem dão 30%: não se mostra nada em vez de arriscar um erro
    assert extract_prices("🔥 50%! Excelente preço!", photo_bytes=banner()) == (None, None)
    assert extract_prices("🔥 30%! Excelente preço!", photo_bytes=banner()) == ("25,40€", "17,77€")


def test_thousands_separator_prices_are_parsed():
    from dealbot.price_extractor import PRICE_TOKEN
    assert [m.groups() for m in PRICE_TOKEN.finditer("1.249,00€ e 899,99€")] == [("1.249", "00"), ("899", "99")]


def test_discount_is_computed_from_the_two_prices():
    assert discount("17,77€", "25,40€") == 30


@needs_ocr
def test_listener_card_shows_discount_badge_computed_from_image_prices(tmp_path):
    async def _test():
        client = MagicMock()
        client.send_file, client.send_message = AsyncMock(), AsyncMock()
        cfg = ListenerConfig(api_id=1, api_hash="h", amazon_tag="t-21", source_channels=["@f"],
                             target_channel="@meucanal", session_path=str(tmp_path / "s"), audit_chat="")
        state, sf = State(published=[]), tmp_path / "state.json"
        state.save(sf)
        msg = SimpleNamespace(text="🔥 30%! Excelente preço!\nGafas Hawkers polarizadas\nhttps://www.amazon.es/dp/B09NYDLHYZ",
                              message=None, photo=object(), media=object(), reply_markup=None,
                              download_media=AsyncMock(return_value=banner()))
        await process_incoming_message(client, msg, cfg, state, sf)
        return client.send_file.call_args.args[1].getvalue()

    card = Image.open(io.BytesIO(asyncio.run(_test())))
    gold = sum(1 for x in range(400, 700, 4) for y in range(820, 1000, 4)
               if (lambda p: p[0] > 230 and 190 < p[1] < 230 and p[2] < 60)(card.getpixel((x, y))))
    assert gold > 30                                        # selo amarelo de desconto presente
    assert sum(card.getpixel((1000, 1060))) < 120           # bloco preto de preço presente


class _FakeTesseract:
    """Tesseract falso que devolve, por ordem, as leituras (ou um erro) de uma lista."""

    class TesseractError(Exception):
        pass

    def __init__(self, outputs):
        self.outputs, self.calls = list(outputs), 0

    def image_to_string(self, image, config=""):
        out = self.outputs[self.calls] if self.calls < len(self.outputs) else ""
        self.calls += 1
        if out == "ERRO":
            raise self.TesseractError("Image too small to scale!! (2x36 vs min width of 3) Line cannot be recognized!!")
        return out


def _run_with_fake(monkeypatch, outputs):
    from dealbot import price_extractor as pe
    fake = _FakeTesseract(outputs)
    monkeypatch.setattr(pe, "pytesseract", fake)
    return pe.extract_prices_from_image(banner()), fake


# Leituras reais do contentor (Tesseract 5.5.0) na foto do drone @cupoes: 9 variantes x (psm 11, psm 7).
CONTAINER_TRANSCRIPT = [
    "152,47€ 71,14€", "", "", "", "152,47€", "", "", "ERRO", "", "", "152,47€ 71,14€", "",
    "1,14€", "", "1,14€", "", "71,14€", "",
]


def test_one_failing_ocr_call_does_not_throw_away_the_good_readings(monkeypatch):
    result, fake = _run_with_fake(monkeypatch, CONTAINER_TRANSCRIPT)
    assert result == ("152,47€", "71,14€")
    assert fake.calls == 18                                    # leu todas as variantes, apesar do erro


def test_a_misread_number_with_many_votes_does_not_hide_the_real_pair(monkeypatch):
    outputs = ["152,47€ 71,14€", "1,14€", "152,47€ 71,14€", "1,14€", "152,47€", "1,14€", "1,14€", "71,14€"]
    result, _ = _run_with_fake(monkeypatch, outputs)
    assert result == ("152,47€", "71,14€")                      # 1,14 tem 4 votos mas dá um desconto impossível


def test_all_calls_failing_returns_nothing_without_raising(monkeypatch):
    result, _ = _run_with_fake(monkeypatch, ["ERRO"] * 20)
    assert result == (None, None)
