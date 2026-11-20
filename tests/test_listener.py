import asyncio
from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace
from dealbot.config import ListenerConfig
from dealbot.state import State
from dealbot.listener import process_incoming_message


def test_process_incoming_message_ignores_duplicate(tmp_path):
    async def _test():
        client = MagicMock()
        client.send_file = AsyncMock()
        client.send_message = AsyncMock()

        cfg = ListenerConfig(
            api_id=12345,
            api_hash="hash",
            amazon_tag="minhatag-21",
            source_channels=["@canal_fonte"],
            target_channel="@meucanal",
            session_path=str(tmp_path / "session"),
            audit_chat="",
        )

        state = State(published=["B0DWDH32M8"])
        state_file = tmp_path / "state.json"
        state.save(state_file)

        msg = SimpleNamespace(
            text="Super promoção https://www.amazon.es/dp/B0DWDH32M8",
            message=None,
            photo=None,
            media=None,
            reply_markup=None,
        )

        await process_incoming_message(client, msg, cfg, state, state_file)

        # Não deve ter chamado envio de mensagem
        client.send_file.assert_not_called()
        client.send_message.assert_not_called()

    asyncio.run(_test())


def test_process_incoming_message_publishes_new_deal(tmp_path):
    async def _test():
        client = MagicMock()
        client.send_file = AsyncMock()
        client.send_message = AsyncMock()

        cfg = ListenerConfig(
            api_id=12345,
            api_hash="hash",
            amazon_tag="minhatag-21",
            source_channels=["@canal_fonte"],
            target_channel="@meucanal",
            session_path=str(tmp_path / "session"),
            audit_chat="",
        )

        state = State(published=[])
        state_file = tmp_path / "state.json"
        state.save(state_file)

        msg = SimpleNamespace(
            text="Aspirador sem fios Xiaomi em desconto!\n❌ Antes: 129€\n✅ Agora: 89€\nhttps://www.amazon.es/dp/B0DWDH32M8",
            message=None,
            photo=None,
            media=None,
            reply_markup=None,
        )

        await process_incoming_message(client, msg, cfg, state, state_file)

        # Deve ter enviado mensagem
        client.send_message.assert_called_once()
        args, kwargs = client.send_message.call_args
        assert args[0] == "@meucanal"
        caption = args[1]
        assert "🔥 <b>Aspirador sem fios Xiaomi em desconto!</b>" in caption
        assert "💥 Link: https://www.amazon.es/dp/B0DWDH32M8?tag=minhatag-21" in caption
        assert "B0DWDH32M8" in state.published

    asyncio.run(_test())



def test_message_with_photo_publishes_real_card_with_prices(tmp_path):
    import io
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (300, 200), (200, 30, 30)).save(buf, "JPEG")

    async def _test():
        client = MagicMock()
        client.send_file = AsyncMock()
        client.send_message = AsyncMock()
        cfg = ListenerConfig(api_id=1, api_hash="h", amazon_tag="minhatag-21", source_channels=["@f"],
                             target_channel="@meucanal", session_path=str(tmp_path / "s"), audit_chat="")
        state, state_file = State(published=[]), tmp_path / "state.json"
        state.save(state_file)
        msg = SimpleNamespace(
            text="Televisor TCL 55\n❌ Antes: 507,25€\n✅ Agora: 284,80€\nhttps://www.amazon.es/dp/B0DWDH32M8",
            message=None, photo=object(), media=object(), reply_markup=None,
            download_media=AsyncMock(return_value=buf.getvalue()),
        )
        await process_incoming_message(client, msg, cfg, state, state_file)

        client.send_file.assert_called_once()
        file_obj = client.send_file.call_args.args[1]
        assert hasattr(file_obj, "read"), "devia enviar o cartão gerado, não a mídia original"
        card = Image.open(io.BytesIO(file_obj.getvalue()))
        assert card.size == (1080, 1080)
        assert sum(card.getpixel((1000, 1060))) < 120   # bloco preto do preço presente

    asyncio.run(_test())


def test_card_receives_only_the_product_photo_while_prices_come_from_the_original(tmp_path, monkeypatch):
    import io
    import shutil
    import pytest
    from PIL import Image
    if shutil.which("tesseract") is None:
        pytest.skip("tesseract não instalado")
    import dealbot.listener as listener
    from test_price_ocr import banner

    original = banner()
    seen = {}

    def fake_card(photo, title, category, handle, price=None, old_price=None, **kw):
        seen.update(photo=photo, price=price, old=old_price)
        return b"CARD"

    monkeypatch.setattr(listener, "make_card", fake_card)

    async def _test():
        client = MagicMock()
        client.send_file, client.send_message = AsyncMock(), AsyncMock()
        cfg = ListenerConfig(api_id=1, api_hash="h", amazon_tag="t-21", source_channels=["@f"],
                             target_channel="@meucanal", session_path=str(tmp_path / "s"), audit_chat="")
        state, sf = State(published=[]), tmp_path / "state.json"
        state.save(sf)
        msg = SimpleNamespace(text="Gafas Hawkers\nhttps://www.amazon.es/dp/B09NYDLHYZ", message=None,
                              photo=object(), media=object(), reply_markup=None,
                              download_media=AsyncMock(return_value=original))
        await process_incoming_message(client, msg, cfg, state, sf)

    asyncio.run(_test())
    assert (seen["old"], seen["price"]) == ("25,40€", "17,77€")          # preços lidos da imagem original
    cropped = Image.open(io.BytesIO(seen["photo"]))
    assert cropped.height < Image.open(io.BytesIO(original)).height - 60   # faixa de preço removida da foto do cartão


def _discard_case(tmp_path, text, photo_bytes=None, audit="@auditoria"):
    async def _test():
        client = MagicMock()
        client.send_file, client.send_message = AsyncMock(), AsyncMock()
        cfg = ListenerConfig(api_id=1, api_hash="h", amazon_tag="t-21", source_channels=["@f"],
                             target_channel="@meucanal", session_path=str(tmp_path / "s"), audit_chat=audit)
        state, sf = State(published=[]), tmp_path / "state.json"
        state.save(sf)
        msg = SimpleNamespace(text=text, message=None, photo=object() if photo_bytes else None,
                              media=object() if photo_bytes else None, reply_markup=None,
                              download_media=AsyncMock(return_value=photo_bytes))
        await process_incoming_message(client, msg, cfg, state, sf)
        return client, state

    return asyncio.run(_test())


def test_post_without_prices_is_not_published_but_reported_in_audit(tmp_path):
    client, state = _discard_case(tmp_path, "Gafas Hawkers polarizadas\nhttps://www.amazon.es/dp/B09NYDLHYZ")
    published_to_channel = [c for c in client.send_message.call_args_list + client.send_file.call_args_list
                            if c.args and c.args[0] == "@meucanal"]
    assert published_to_channel == []
    assert "B09NYDLHYZ" not in state.published
    assert client.send_message.call_args.args[0] == "@auditoria"
    assert "preços" in client.send_message.call_args.args[1].lower()


def test_post_with_a_single_price_is_not_published(tmp_path):
    client, state = _discard_case(tmp_path, "Gafas Hawkers 25,40€\nhttps://www.amazon.es/dp/B09NYDLHYZ")
    assert not any(c.args and c.args[0] == "@meucanal" for c in client.send_message.call_args_list)
    assert client.send_file.call_count == 0 and "B09NYDLHYZ" not in state.published


def test_photo_with_unreadable_prices_is_not_published(tmp_path):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), (200, 30, 30)).save(buf, "JPEG")
    client, state = _discard_case(tmp_path, "Gafas\nhttps://www.amazon.es/dp/B09NYDLHYZ", buf.getvalue())
    assert not any(c.args and c.args[0] == "@meucanal" for c in client.send_file.call_args_list)
    assert "B09NYDLHYZ" not in state.published


def test_discarded_offer_is_recorded_for_the_dashboard(tmp_path):
    import json
    _discard_case(tmp_path, "Gafas Hawkers 25,40€\nhttps://www.amazon.es/dp/B09NYDLHYZ", audit="")
    items = json.loads((tmp_path / "discarded.json").read_text())
    assert items[0]["asin"] == "B09NYDLHYZ" and "preços" in items[0]["reason"]
    assert items[0]["title"].startswith("Gafas Hawkers")


def test_post_without_a_product_name_is_not_published(tmp_path):
    import json
    client, state = _discard_case(
        tmp_path, "🤯 -48%! MEGA preço! Mínimo histórico!\n❌ Antes: 60,98€\n✅ Agora: 32,00€\nhttps://www.amazon.es/dp/B0BLJSTSGT")
    assert not any(c.args and c.args[0] == "@meucanal" for c in client.send_message.call_args_list)
    assert "B0BLJSTSGT" not in state.published
    assert "nome" in json.loads((tmp_path / "discarded.json").read_text())[0]["reason"]


def _photo_case(tmp_path, monkeypatch, amazon, amazon_images=True):
    """Corre um post com foto de origem (faixa de preço) e devolve o que chegou ao make_card."""
    import io
    import shutil
    import pytest
    if shutil.which("tesseract") is None:
        pytest.skip("tesseract não instalado")
    import dealbot.listener as listener
    from test_price_ocr import banner

    original, seen, calls = banner(), {}, []

    def fake_card(photo, title, category, handle, price=None, old_price=None, **kw):
        seen.update(photo=photo, price=price, old=old_price)
        return b"CARD"

    def fake_amazon(asin, *a, **k):
        calls.append(asin)
        return amazon

    monkeypatch.setattr(listener, "make_card", fake_card)
    monkeypatch.setattr(listener, "fetch_amazon_image", fake_amazon)

    async def _test():
        client = MagicMock()
        client.send_file, client.send_message = AsyncMock(), AsyncMock()
        cfg = ListenerConfig(api_id=1, api_hash="h", amazon_tag="t-21", source_channels=["@f"],
                             target_channel="@meucanal", session_path=str(tmp_path / "s"), audit_chat="",
                             amazon_images=amazon_images)
        state, sf = State(published=[]), tmp_path / "state.json"
        state.save(sf)
        msg = SimpleNamespace(text="Gafas Hawkers\nhttps://www.amazon.es/dp/B09NYDLHYZ", message=None,
                              photo=object(), media=object(), reply_markup=None,
                              download_media=AsyncMock(return_value=original))
        await process_incoming_message(client, msg, cfg, state, sf)

    asyncio.run(_test())
    return original, seen, calls


def test_amazon_image_is_used_when_available_and_prices_still_come_from_the_source(tmp_path, monkeypatch):
    from test_amazon_image import jpeg
    amazon = jpeg(500, 500, (10, 120, 10))
    original, seen, calls = _photo_case(tmp_path, monkeypatch, amazon)
    assert seen["photo"] == amazon and calls == ["B09NYDLHYZ"]
    assert (seen["old"], seen["price"]) == ("25,40€", "17,77€")


def test_source_photo_is_cropped_when_the_amazon_image_is_missing(tmp_path, monkeypatch):
    import io
    from PIL import Image
    original, seen, calls = _photo_case(tmp_path, monkeypatch, amazon=None)
    assert calls == ["B09NYDLHYZ"]
    assert Image.open(io.BytesIO(seen["photo"])).height < Image.open(io.BytesIO(original)).height - 60
    assert (seen["old"], seen["price"]) == ("25,40€", "17,77€")


def test_amazon_images_can_be_switched_off(tmp_path, monkeypatch):
    import io
    from PIL import Image
    from test_amazon_image import jpeg
    original, seen, calls = _photo_case(tmp_path, monkeypatch, jpeg(500, 500), amazon_images=False)
    assert calls == []
    assert Image.open(io.BytesIO(seen["photo"])).height < Image.open(io.BytesIO(original)).height - 60


def _link_case(tmp_path, monkeypatch, text, final_url=None):
    import dealbot.links as links
    if final_url:
        monkeypatch.setattr(links, "_follow", lambda url, max_hops=5: final_url)

    async def _test():
        client = MagicMock()
        client.send_file, client.send_message = AsyncMock(), AsyncMock()
        cfg = ListenerConfig(api_id=1, api_hash="h", amazon_tag="t-21", source_channels=["@f"],
                             target_channel="@meucanal", session_path=str(tmp_path / "s"), audit_chat="")
        state, sf = State(published=[]), tmp_path / "state.json"
        state.save(sf)
        msg = SimpleNamespace(text=text, message=None, photo=None, media=None, reply_markup=None)
        await process_incoming_message(client, msg, cfg, state, sf)
        return client, state

    return asyncio.run(_test())


def test_title_comes_from_the_url_slug_of_a_short_link_when_text_has_no_name(tmp_path, monkeypatch):
    final = "https://www.amazon.es/Marvels-Guardians-Galaxy-Nintendo-Switch/dp/B0HJH8BB6Y?th=1"
    client, state = _link_case(
        tmp_path, monkeypatch, "🔥 Preço mínimo histórico!\n❌ Antes: 40,65€\n✅ Agora: 33,53€\nhttps://amzn.to/3xyz", final)
    client.send_message.assert_called()
    caption = [c.args[1] for c in client.send_message.call_args_list if c.args[0] == "@meucanal"][0]
    assert "Marvels Guardians Galaxy Nintendo Switch" in caption
    assert "B0HJH8BB6Y" in state.published


def test_slug_title_is_translated_and_wins_over_a_noisy_text_line(tmp_path, monkeypatch):
    import dealbot.listener as listener
    monkeypatch.setattr(listener, "to_pt", lambda t: f"PT[{t}]")
    final = "https://www.amazon.es/Cecotec-Freidora-Cecofry/dp/B0B5VPLXRB"
    client, _ = _link_case(
        tmp_path, monkeypatch, "Linha qualquer do texto\n❌ Antes: 90€\n✅ Agora: 60€\nhttps://amzn.to/3xyz", final)
    caption = [c.args[1] for c in client.send_message.call_args_list if c.args[0] == "@meucanal"][0]
    assert "PT[Cecotec Freidora Cecofry]" in caption and "Linha qualquer" not in caption


def test_link_without_slug_falls_back_to_the_text_name(tmp_path, monkeypatch):
    final = "https://www.amazon.es/dp/B0B5VPLXRB?th=1"
    client, _ = _link_case(
        tmp_path, monkeypatch, "Cecotec Freidora Cecofry 5L\n❌ Antes: 90€\n✅ Agora: 60€\nhttps://amzn.to/3xyz", final)
    caption = [c.args[1] for c in client.send_message.call_args_list if c.args[0] == "@meucanal"][0]
    assert "Cecotec Freidora Cecofry 5L" in caption


DESCONTOS_POST = (
    "🔥 Sapatilhas Fila Hypert para mulher\n\n"
    "👉 [https://descontosainanas.com/amz/B0F4QXRPT1](https://descontosainanas.com/amz/B0F4QXRPT1)\n"
    "❌ Antes: 43,15€\n✅ Agora: 29,94€\n[ 31% desconto ]\n"
    "🏷 [#Calçado Mulher](https://boacena.pt/category/moda/mulher/calcado-mulher) · Pub")


def test_descontosainanas_style_post_is_published(tmp_path, monkeypatch):
    client, state = _link_case(tmp_path, monkeypatch, DESCONTOS_POST)
    posted = [c.args[1] for c in client.send_message.call_args_list if c.args[0] == "@meucanal"]
    assert posted and "Sapatilhas Fila Hypert para mulher" in posted[0]
    assert "https://www.amazon.es/dp/B0F4QXRPT1?tag=t-21" in posted[0] and "descontosainanas" not in posted[0]
    assert "B0F4QXRPT1" in state.published


def test_post_with_links_but_no_amazon_link_is_recorded_as_discarded(tmp_path, monkeypatch):
    import json
    _link_case(tmp_path, monkeypatch, "Fone Bluetooth super oferta\nhttps://www.aliexpress.com/item/123.html\nhttps://t.me/x")
    items = json.loads((tmp_path / "discarded.json").read_text())
    assert "aliexpress.com" in items[0]["reason"] and items[0]["title"].startswith("Fone Bluetooth")


def test_short_link_that_cannot_be_opened_is_recorded_as_discarded(tmp_path, monkeypatch):
    import json
    import dealbot.links as links

    def boom(url, max_hops=5):
        raise OSError("timeout")

    monkeypatch.setattr(links, "_follow", boom)
    _link_case(tmp_path, monkeypatch, "Nome do Produto Bom\n❌ Antes: 90€ ✅ Agora: 60€\nhttps://amzn.to/abc")
    items = json.loads((tmp_path / "discarded.json").read_text())
    assert "link curto" in items[0]["reason"] and "amzn.to" in items[0]["reason"]


def test_unexpected_errors_are_recorded_not_lost(tmp_path, monkeypatch):
    import json
    import dealbot.listener as listener

    async def boom(*a, **k):
        raise RuntimeError("falhou o OCR")

    monkeypatch.setattr(listener.asyncio, "to_thread", boom)
    client = MagicMock()
    client.send_file, client.send_message = AsyncMock(), AsyncMock()
    cfg = ListenerConfig(api_id=1, api_hash="h", amazon_tag="t-21", source_channels=["@f"],
                         target_channel="@meucanal", session_path=str(tmp_path / "s"), audit_chat="")
    state, sf = State(published=[]), tmp_path / "state.json"
    state.save(sf)
    msg = SimpleNamespace(text="Produto Bom Nome\n❌ Antes: 90€ ✅ Agora: 60€\nhttps://www.amazon.es/dp/B0B5VPLXRB",
                          message=None, photo=None, media=None, reply_markup=None)
    asyncio.run(listener.handle_message_safely(client, msg, cfg, state, sf))
    items = json.loads((tmp_path / "discarded.json").read_text())
    assert "erro inesperado" in items[0]["reason"] and "falhou o OCR" in items[0]["reason"]


def test_price_failure_record_keeps_a_text_excerpt_to_diagnose_the_format(tmp_path, monkeypatch):
    import json
    _link_case(tmp_path, monkeypatch,
               "🔥 BOM preço! Mínimo histórico!\nRockJam ▫️ Bluetooth Máquina karaoke 2 microfones\n"
               "💰 29,99€\nhttps://www.amazon.es/dp/B0BXT76Z42")
    item = json.loads((tmp_path / "discarded.json").read_text())[0]
    assert "preços" in item["reason"] and "29,99€" in item["excerpt"] and "RockJam" in item["excerpt"]
