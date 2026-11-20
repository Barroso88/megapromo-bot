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
            text="Aspirador sem fios Xiaomi em desconto!\nPreço: 89€\nhttps://www.amazon.es/dp/B0DWDH32M8",
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
