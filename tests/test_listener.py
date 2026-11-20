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
