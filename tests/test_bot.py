from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from dealbot.bot import run_once
from dealbot.config import Config
from dealbot.feed import Deal
from dealbot.state import State
from dealbot.telegram import TelegramError

OWNER, CHANNEL = "111", "@canal"
CFG = Config(token="t", owner_chat_id=OWNER, channel_id=CHANNEL, amazon_tag="meu-21")
DAY = datetime(2026, 11, 19, 12, 0, tzinfo=ZoneInfo("Europe/Lisbon"))
NIGHT = datetime(2026, 11, 19, 2, 0, tzinfo=ZoneInfo("Europe/Lisbon"))
ASIN = "B0DWDH32M8"


class FakeTG:
    def __init__(self, updates=None, fail_chats=()):
        self.updates, self.sent, self.fail_chats, self._id = updates or [], [], set(fail_chats), 1000

    def get_updates(self, offset):
        return [u for u in self.updates if u["update_id"] >= offset]

    def send_message(self, chat_id, text, reply_to=None):
        if str(chat_id) in self.fail_chats:
            raise TelegramError("falhou")
        self._id += 1
        self.sent.append((str(chat_id), text))
        return self._id

    def to(self, chat):
        return [t for c, t in self.sent if c == chat]


def upd(uid, text, chat=OWNER, reply_to=None):
    m = {"message_id": uid, "chat": {"id": int(chat)}, "text": text}
    if reply_to:
        m["reply_to_message"] = {"message_id": reply_to}
    return {"update_id": uid, "message": m}


def feed_of(n):
    return lambda: n


def deals(n):
    return [Deal(f"g{i}", f"Produto {i}", "Cat", "1,00€", "", f"https://c/{i}") for i in range(n)]


def run(tg, state=None, fetch=None, now=DAY, resolve=None):
    state = state or State()
    run_once(CFG, tg, state, fetch=fetch or (lambda: ""), now=now, resolve=resolve, parse=lambda _x: [])
    return state


def test_reply_to_proposal_publishes_with_title_and_our_tag():
    st = State()
    st.pending["500"] = {"title": "Bola & Co", "category": "Deportes", "price": "1€"}
    tg = FakeTG([upd(1, f"https://www.amazon.es/dp/{ASIN}?tag=outro-21&ref=x", reply_to=500)])
    run(tg, st)
    post = tg.to(CHANNEL)[0]
    assert "Bola &amp; Co" in post and f"/dp/{ASIN}?tag=meu-21" in post
    assert "outro-21" not in post and "ref=x" not in post
    assert ASIN in st.published and "500" not in st.pending and st.offset == 2
    assert tg.to(OWNER)


def test_link_without_context_is_not_published():
    tg = FakeTG([upd(1, f"https://www.amazon.es/dp/{ASIN}")])
    st = run(tg)
    assert tg.to(CHANNEL) == [] and ASIN not in st.published
    assert "título" in tg.to(OWNER)[0] and st.offset == 2


def test_link_plus_text_uses_text_as_title():
    tg = FakeTG([upd(1, f"https://www.amazon.es/dp/{ASIN} Bola adidas")])
    run(tg)
    assert "Bola adidas" in tg.to(CHANNEL)[0]


def test_non_owner_ignored_but_offset_advances():
    tg = FakeTG([upd(1, f"https://www.amazon.es/dp/{ASIN} X", chat="999")])
    st = run(tg)
    assert tg.sent == [] and st.offset == 2


def test_duplicate_asin_not_republished():
    tg = FakeTG([upd(1, f"https://www.amazon.es/dp/{ASIN} A"), upd(2, f"https://www.amazon.es/dp/{ASIN} A")])
    run(tg)
    assert len(tg.to(CHANNEL)) == 1
    assert "já" in tg.to(OWNER)[-1].lower()


def test_short_link_error_reports_to_owner():
    def bad(u):
        raise OSError("x")

    tg = FakeTG([upd(1, "https://amzn.to/abc Titulo")])
    run(tg, resolve=bad)
    assert tg.to(CHANNEL) == [] and tg.to(OWNER)


def test_non_amazon_es_link_rejected():
    tg = FakeTG([upd(1, f"https://www.amazon.com/dp/{ASIN} T")])
    run(tg)
    assert tg.to(CHANNEL) == [] and tg.to(OWNER)


def test_channel_failure_notifies_owner_and_does_not_block_queue():
    tg = FakeTG([upd(1, f"https://www.amazon.es/dp/{ASIN} T")], fail_chats=[CHANNEL])
    st = run(tg)
    assert ASIN not in st.published and st.offset == 2
    assert tg.to(OWNER) and "canal" in tg.to(OWNER)[0].lower()


def test_channel_and_owner_failure_keeps_offset_for_retry():
    tg = FakeTG([upd(1, f"https://www.amazon.es/dp/{ASIN} T")], fail_chats=[CHANNEL, OWNER])
    st = run(tg)
    assert st.offset == 0 and ASIN not in st.published


def test_error_reply_escapes_html():
    def bad(u):
        raise OSError("<urlopen error [Errno -2] Name or service not known>")

    tg = FakeTG([upd(1, "https://amzn.to/abc Titulo")])
    run(tg, resolve=bad)
    msg = tg.to(OWNER)[0]
    assert "&lt;urlopen" in msg and "<urlopen" not in msg


def test_proposals_max_three_then_rest_next_run():
    ds = deals(5)
    tg = FakeTG()
    st = State()
    run_once(CFG, tg, st, fetch=lambda: "", now=DAY, parse=lambda _x: ds)
    assert len(tg.to(OWNER)) == 3 and st.seen == ["g0", "g1", "g2"] and len(st.pending) == 3
    run_once(CFG, tg, st, fetch=lambda: "", now=DAY, parse=lambda _x: ds)
    assert len(tg.to(OWNER)) == 5 and set(st.seen) == {d.guid for d in ds}


def test_no_proposals_at_night():
    tg = FakeTG()
    run_once(CFG, tg, State(), fetch=lambda: "", now=NIGHT, parse=lambda _x: deals(2))
    assert tg.sent == []


def test_fetch_failure_does_not_stop_owner_handling():
    def boom():
        raise OSError("feed em baixo")

    tg = FakeTG([upd(1, f"https://www.amazon.es/dp/{ASIN} T")])
    st = State()
    run_once(CFG, tg, st, fetch=boom, now=DAY)
    assert len(tg.to(CHANNEL)) == 1 and st.offset == 2


def test_config_from_env_missing(monkeypatch):
    for k in ("TELEGRAM_BOT_TOKEN", "OWNER_CHAT_ID", "CHANNEL_ID", "AMAZON_TAG"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(SystemExit) as e:
        Config.from_env()
    assert "TELEGRAM_BOT_TOKEN" in str(e.value)
    for k, v in (("TELEGRAM_BOT_TOKEN", "t"), ("OWNER_CHAT_ID", "1"), ("CHANNEL_ID", "@c"), ("AMAZON_TAG", "x-21")):
        monkeypatch.setenv(k, v)
    assert Config.from_env().amazon_tag == "x-21"


def test_config_strips_whitespace_and_newlines(monkeypatch):
    for k, v in (("TELEGRAM_BOT_TOKEN", " 123:abc\n"), ("OWNER_CHAT_ID", "1 \r\n"), ("CHANNEL_ID", "@c\n"), ("AMAZON_TAG", "x-21 ")):
        monkeypatch.setenv(k, v)
    cfg = Config.from_env()
    assert cfg == Config("123:abc", "1", "@c", "x-21")


class PhotoTG(FakeTG):
    def __init__(self, *a, fail_photo=False, **k):
        super().__init__(*a, **k)
        self.photos, self.fail_photo = [], fail_photo

    def send_photo_bytes(self, chat_id, data, caption):
        if self.fail_photo:
            raise TelegramError("foto")
        self.photos.append((str(chat_id), data, caption))
        return 1


def test_pending_with_image_publishes_card_photo():
    st = State()
    st.pending["500"] = {"title": "Bola", "category": "Desporto", "price": "", "image": "https://i/x.jpg"}
    tg = PhotoTG([upd(1, f"https://www.amazon.es/dp/{ASIN}", reply_to=500)])
    run_once(CFG, tg, st, fetch=lambda: "", now=DAY, parse=lambda _x: [],
             fetch_image=lambda u: b"IMG", make_card=lambda *a, **k: b"CARD")
    assert tg.photos == [(CHANNEL, b"CARD", tg.photos[0][2])]
    assert f"/dp/{ASIN}?tag=meu-21" in tg.photos[0][2] and tg.to(CHANNEL) == []
    assert ASIN in st.published


def test_card_failures_fall_back_to_text_post():
    for fi, tg in ((lambda u: None, PhotoTG()), (lambda u: b"IMG", PhotoTG(fail_photo=True))):
        st = State()
        st.pending["500"] = {"title": "Bola", "category": "", "price": "", "image": "https://i/x.jpg"}
        tg.updates = [upd(1, f"https://www.amazon.es/dp/{ASIN}", reply_to=500)]
        run_once(CFG, tg, st, fetch=lambda: "", now=DAY, parse=lambda _x: [],
                 fetch_image=fi, make_card=lambda *a, **k: b"CARD")
        assert f"/dp/{ASIN}?tag=meu-21" in tg.to(CHANNEL)[0] and ASIN in st.published


def test_proposals_are_translated_and_keep_image():
    tg, st = FakeTG(), State()
    run_once(CFG, tg, st, fetch=lambda: "", now=DAY, translate=lambda t: f"PT:{t}",
             parse=lambda _x: [Deal("g", "Hola", "Deportes", "1€", "https://i/150x150/a.jpg", "https://c/1")])
    assert "PT:Hola" in tg.to(OWNER)[0] and "PT:Deportes" in tg.to(OWNER)[0]
    (p,) = st.pending.values()
    assert p["title"] == "PT:Hola" and p["category"] == "PT:Deportes" and p["image"] == "https://i/150x150/a.jpg"


def test_owner_prices_in_reply_reach_the_card():
    st, got = State(), {}
    st.pending["500"] = {"title": "TV", "category": "C", "price": "", "image": "https://i/x.jpg"}
    tg = PhotoTG([upd(1, f"https://www.amazon.es/dp/{ASIN} 507,25 284,80", reply_to=500)])

    def mk(photo, title, category, handle, price=None, old_price=None):
        got.update(price=price, old=old_price)
        return b"CARD"

    run_once(CFG, tg, st, fetch=lambda: "", now=DAY, parse=lambda _x: [], fetch_image=lambda u: b"I", make_card=mk)
    assert got == {"price": "284,80", "old": "507,25"} and tg.photos


def test_listener_config_amazon_images_flag(monkeypatch):
    from dealbot.config import ListenerConfig
    base = {"TELEGRAM_API_ID": "1", "TELEGRAM_API_HASH": "h", "AMAZON_TAG": "t-21",
            "SOURCE_CHANNELS": "@a", "TARGET_CHANNEL": "@b"}
    for k, v in base.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("AMAZON_IMAGES", raising=False)
    assert ListenerConfig.from_env().amazon_images is True            # por defeito ligado (decisão do dono)
    for off in ("0", "false", "no", "off", " FALSE "):
        monkeypatch.setenv("AMAZON_IMAGES", off)
        assert ListenerConfig.from_env().amazon_images is False
    monkeypatch.setenv("AMAZON_IMAGES", "1")
    assert ListenerConfig.from_env().amazon_images is True


def test_listener_config_price_flags(monkeypatch):
    from dealbot.config import ListenerConfig
    base = {"TELEGRAM_API_ID": "1", "TELEGRAM_API_HASH": "h", "AMAZON_TAG": "t-21",
            "SOURCE_CHANNELS": "@a", "TARGET_CHANNEL": "@b"}
    for k, v in base.items():
        monkeypatch.setenv(k, v)
    for k in ("REQUIRE_PRICES", "SHOW_PRICES"):
        monkeypatch.delenv(k, raising=False)
    cfg = ListenerConfig.from_env()
    assert cfg.show_prices is True and cfg.require_prices is False        # por defeito: preços opcionais
    monkeypatch.setenv("REQUIRE_PRICES", " TRUE ")
    assert ListenerConfig.from_env().require_prices is True
    monkeypatch.setenv("SHOW_PRICES", "0")
    assert ListenerConfig.from_env().show_prices is False
