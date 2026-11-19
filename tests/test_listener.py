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
        assert "https://www.amazon.es/dp/B0DWDH32M8?tag=minhatag-21" in caption
        assert "@meucanal" in caption
        assert "B0DWDH32M8" in state.published

    asyncio.run(_test())

