import json
import urllib.error

import pytest

from dealbot.telegram import Telegram, TelegramError

TOKEN = "123:SECRET"


class FakeResp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def make(payload=None, exc=None):
    calls = []

    def opener(req, timeout=None):
        calls.append((req.full_url, json.loads(req.data.decode())))
        if exc:
            raise exc
        return FakeResp(payload)

    return Telegram(TOKEN, opener=opener), calls


def test_send_message_returns_message_id_and_body():
    tg, calls = make({"ok": True, "result": {"message_id": 99}})
    assert tg.send_message(5, "<b>oi</b>", reply_to=3) == 99
    url, body = calls[0]
    assert url == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert body["chat_id"] == 5 and body["text"] == "<b>oi</b>"
    assert body["parse_mode"] == "HTML" and body["reply_to_message_id"] == 3
    assert body["disable_web_page_preview"] is True


def test_send_photo():
    tg, calls = make({"ok": True, "result": {"message_id": 7}})
    assert tg.send_photo("@c", "https://i/x.jpg", "cap") == 7
    assert calls[0][1]["photo"] == "https://i/x.jpg" and calls[0][1]["caption"] == "cap"


def test_get_updates():
    tg, calls = make({"ok": True, "result": [{"update_id": 5}]})
    assert tg.get_updates(5) == [{"update_id": 5}]
    assert calls[0][1]["offset"] == 5 and calls[0][1]["timeout"] == 0


def test_api_error_raises():
    tg, _ = make({"ok": False, "description": "x"})
    with pytest.raises(TelegramError):
        tg.send_message(1, "a")


def test_network_error_raises_without_token():
    tg, _ = make(exc=urllib.error.URLError(f"falhou https://api.telegram.org/bot{TOKEN}/x"))
    with pytest.raises(TelegramError) as e:
        tg.send_message(1, "a")
    assert TOKEN not in str(e.value)
