import pytest


@pytest.fixture(autouse=True)
def no_network_translate(monkeypatch):
    """Os testes nunca chamam o Google Translate."""
    import dealbot.bot as bot
    monkeypatch.setattr(bot, "to_pt", lambda t: t)
    monkeypatch.setattr(bot.propose_deals, "__defaults__", (lambda t: t,))
    monkeypatch.setattr(bot.run_once, "__defaults__", (bot.fetch_feed, None, None, bot.parse_feed,
                                                      lambda t: t, bot.default_fetch_image, bot.default_make_card))


@pytest.fixture(autouse=True)
def no_network_amazon_images(monkeypatch):
    """Os testes nunca pedem imagens à Amazon (cada teste que precisa substitui isto)."""
    import dealbot.listener as listener
    monkeypatch.setattr(listener, "fetch_amazon_image", lambda asin, *a, **k: None)


@pytest.fixture(autouse=True)
def no_network_listener_translate(monkeypatch):
    """O monitor nunca chama o Google Translate nos testes (cada teste que precisa substitui isto)."""
    import dealbot.listener as listener
    monkeypatch.setattr(listener, "to_pt", lambda t: t)
