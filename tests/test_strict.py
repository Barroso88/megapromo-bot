"""Modo rigoroso: só se publica o que é verificável (textos com o formato real dos canais)."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from dealbot.cleaner import extract_strict_title
from dealbot.config import ListenerConfig
from dealbot.price_extractor import extract_verified_prices
from dealbot.state import State

URL = "\n\n👉 https://link.amazon/B02tcoIIz\n❌ Antes: 335,35€\n✅ Agora: 213,37€\n[ 36% desconto ]"


@pytest.mark.parametrize("first_line, expected", [
    ("EXCELENTE PREÇO 📱 Smartphone POCO C95 Pro 8GB+256GB com bateria de 7500mAh, carga de 45W, ecrã de 6,9 a 120Hz",
     "Smartphone POCO C95 Pro 8GB+256GB com bateria de 7500mAh"),
    ("🌟 MELHOR PREÇO - Smart TV Philips OLED 55 Polegadas ✅ Tudo o que precisas, com um bruto desconto.",
     "Smart TV Philips OLED 55 Polegadas"),
    ("104 LAVAGENS · SUPER PREÇO 🧼 Pastilhas para máquina de lavar loiça Finish Power All in One · removem manchas",
     "Pastilhas para máquina de lavar loiça Finish Power All in One"),
    ("IMPECÁVEIS!!! 🤩 Botins Skechers Garlan Deno para homem", "Botins Skechers Garlan Deno para homem"),
    ("🤩 Relógio Diesel Mr. Daddy para homem", "Relógio Diesel Mr. Daddy para homem"),
])
def test_ainanas_titles_lose_the_hype_prefix(first_line, expected):
    assert extract_strict_title(first_line + URL) == expected


@pytest.mark.parametrize("first_line", [
    "Os mais recentes 🎧 Todo o feedback que temos visto destes fones é INCRÍVEL",
    "🧨 FAZ A DIFERENÇA!!! Se tens animais ( ou crianças ) isto faz parte do arsenal obrigatório para tua casa.",
    "Já viste isto? 😱",
])
def test_commentary_is_not_accepted_as_a_title(first_line):
    assert extract_strict_title(first_line + "\n\n🫡 BISSELL SpotClean Pet Pro" + URL) is None


def test_marker_lines_are_accepted_and_unknown_formats_are_not():
    assert extract_strict_title("🔥 BOM preço!\n\nMaxi-Cosi ▫️ Zelia carrinho 3 em 1\n\n🔗 Link: https://x") == \
        "Maxi-Cosi – Zelia carrinho 3 em 1"
    assert extract_strict_title("Preço mínimo\n🔹 Cecotec AirGlisse 8in1 CottonCandy | Modelador\n👉 https://x") == \
        "Cecotec AirGlisse 8in1 CottonCandy"
    assert extract_strict_title("Uma linha qualquer sem formato conhecido\nhttps://x") is None


def test_verified_prices_need_labels_in_the_text_or_an_image_that_matches_the_percentage(monkeypatch):
    import dealbot.price_extractor as pe
    reads = {}
    monkeypatch.setattr(pe, "extract_prices_from_image", lambda b, stated_pct=None: reads["pair"])
    reads["pair"] = ("90,00€", "60,00€")
    assert extract_verified_prices("❌ Antes: 335,35€ ✅ Agora: 213,37€ [36% desconto]") == ("335,35€", "213,37€")
    assert extract_verified_prices("❌ Antes: 335,35€ ✅ Agora: 213,37€ [10% desconto]") == (None, None)   # contradição
    assert extract_verified_prices("-33% Excelente preço", b"img") == ("90,00€", "60,00€")               # imagem + %
    assert extract_verified_prices("-50% Excelente preço", b"img") == (None, None)
    assert extract_verified_prices("Preço mínimo histórico", b"img") == (None, None)                     # uma só fonte


def _run(tmp_path, monkeypatch, text, amazon=True, strict=True):
    import dealbot.listener as listener
    from test_amazon_image import jpeg
    monkeypatch.setattr(listener, "fetch_amazon_image", lambda a, *x, **k: jpeg(500, 500) if amazon else None)
    monkeypatch.setattr(listener, "isolate_product", lambda b: pytest.fail("o modo rigoroso não recorta fotos"))
    monkeypatch.setattr(listener, "make_card", lambda *a, **k: b"CARD")
    client = MagicMock()
    client.send_file, client.send_message = AsyncMock(), AsyncMock()
    cfg = ListenerConfig(api_id=1, api_hash="h", amazon_tag="t-21", source_channels=["@f"], target_channel="@meu",
                         session_path=str(tmp_path / "s"), audit_chat="", strict=strict)
    state, sf = State(published=[]), tmp_path / "state.json"
    msg = SimpleNamespace(text=text, message=None, photo=None, media=None, reply_markup=None)
    asyncio.run(listener.process_incoming_message(client, msg, cfg, state, sf))
    reason = ""
    if (tmp_path / "discarded.json").exists():
        reason = json.loads((tmp_path / "discarded.json").read_text())[0]["reason"]
    return client.send_file.call_count, reason


GOOD = "🤩 Relógio Diesel Mr. Daddy para homem\n\n👉 https://www.amazon.es/dp/B08SJ61XP8\n❌ Antes: 415,76€\n✅ Agora: 170,23€"


def test_strict_publishes_a_fully_verified_offer(tmp_path, monkeypatch):
    assert _run(tmp_path, monkeypatch, GOOD) == (1, "")


def test_strict_discards_without_amazon_image_title_or_verified_prices(tmp_path, monkeypatch):
    sent, reason = _run(tmp_path / "a", monkeypatch, GOOD, amazon=False)
    assert sent == 0 and "imagem da Amazon" in reason
    sent, reason = _run(tmp_path / "b", monkeypatch, GOOD.replace("🤩 Relógio", "Já viste isto? 😱\nRelógio"))
    assert sent == 0 and "nome do produto" in reason
    sent, reason = _run(tmp_path / "c", monkeypatch, "🔹 Relógio Diesel Mr. Daddy\n👉 https://www.amazon.es/dp/B08SJ61XP8")
    assert sent == 0 and "preços" in reason


def test_strict_mode_is_on_by_default_from_the_environment(monkeypatch):
    for k, v in {"TELEGRAM_API_ID": "1", "TELEGRAM_API_HASH": "h", "AMAZON_TAG": "t", "SOURCE_CHANNELS": "@a",
                 "TARGET_CHANNEL": "@b"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("STRICT_MODE", raising=False)
    assert ListenerConfig.from_env().strict is True
    monkeypatch.setenv("STRICT_MODE", "0")
    assert ListenerConfig.from_env().strict is False
