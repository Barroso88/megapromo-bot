from types import SimpleNamespace
from dealbot.cleaner import extract_links_from_telethon_message, clean_text_for_repost, compose_repost_caption


def test_clean_text_removes_usernames_and_tme():
    raw = """
    Oferta incrível de portátil!
    Preço: 599€ (em vez de 799€)
    Cupão: DESCONTO50
    https://t.me/canal_concorrente
    Segue @canal_concorrente para mais ofertas!
    """
    cleaned = clean_text_for_repost(raw, "@meucanal")
    assert "@canal_concorrente" not in cleaned
    assert "t.me" not in cleaned
    assert "599€" in cleaned
    assert "DESCONTO50" in cleaned


def test_extract_links_from_message_and_buttons():
    btn1 = SimpleNamespace(url="https://amzn.to/3xyz123")
    btn2 = SimpleNamespace(url=None)
    row = SimpleNamespace(buttons=[btn1, btn2])
    reply_markup = SimpleNamespace(rows=[row])
    
    msg = SimpleNamespace(
        text="Veja aqui https://www.amazon.es/dp/B0DWDH32M8",
        message=None,
        reply_markup=reply_markup
    )
    
    urls = extract_links_from_telethon_message(msg)
    assert "https://www.amazon.es/dp/B0DWDH32M8" in urls
    assert "https://amzn.to/3xyz123" in urls


def test_compose_repost_caption():
    caption = compose_repost_caption(
        title="Auriculares Beats Studio Pro",
        clean_body="Preço mínimo histórico: 199€",
        affiliate_link="https://www.amazon.es/dp/B0DWDH32M8?tag=meu-21",
        target_handle="@promospt"
    )
    assert "Auriculares Beats Studio Pro" in caption
    assert "https://www.amazon.es/dp/B0DWDH32M8?tag=meu-21" in caption
    assert "@promospt" in caption
    assert "Como Associado da Amazon" in caption
