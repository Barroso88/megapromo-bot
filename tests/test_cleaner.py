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
        affiliate_link="https://www.amazon.es/dp/B0DWDH32M8?tag=megapromopt-21",
        target_handle="@megapromo_pt"
    )
    assert "🔥 <b>Auriculares Beats Studio Pro</b>" in caption
    assert "💥 Link: https://www.amazon.es/dp/B0DWDH32M8?tag=megapromopt-21" in caption
    assert "Como Associado da Amazon" in caption


def test_title_ignores_percent_headline_with_markdown_and_finds_product_line():
    from dealbot.cleaner import extract_product_title
    text = ("🔥 32%! Excelente preço!** __Mínimo histórico!__\n\n"
            "Orico Dock Mac Mini M4 com SSD 2TB\n👉 https://www.amazon.es/dp/B0FBWWW131")
    assert extract_product_title(text) == "Orico Dock Mac Mini M4 com SSD 2TB"


def test_title_strips_markdown_markers():
    from dealbot.cleaner import extract_product_title
    assert extract_product_title("**Gafas Hawkers** Polarizadas\nhttps://x") == "Gafas Hawkers Polarizadas"


def test_only_headlines_give_generic_title():
    from dealbot.cleaner import extract_product_title
    assert extract_product_title("🔥 32%! Excelente preço! __Mínimo histórico!__ Aproveita já\nhttps://x") == "Oferta Especial"
