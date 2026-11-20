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


def test_title_skips_emoji_and_dash_percent_headline():
    from dealbot.cleaner import extract_product_title
    text = "🤯 -48%! MEGA preço! Mínimo histórico!\nPolly Pocket Friends Central Perk Collector\nhttps://x"
    assert extract_product_title(text) == "Polly Pocket Friends Central Perk Collector"
    assert extract_product_title("🤯 -48%! MEGA preço! Mínimo histórico!\nhttps://x") == "Oferta Especial"


def test_title_skips_instruction_lines():
    from dealbot.cleaner import extract_product_title
    text = 'Seleciona "Subscreva e Poupe" (cancelável a qualquer altura)\nSabão Skip Ultimate 50 doses\nhttps://x'
    assert extract_product_title(text) == "Sabão Skip Ultimate 50 doses"
    assert extract_product_title('Seleciona "Subscreva e Poupe" (cancelável a qualquer altura)\nhttps://x') == "Oferta Especial"


def test_real_product_names_are_not_mistaken_for_headlines():
    from dealbot.cleaner import extract_product_title
    for name in ("roborock Saros 10R Aspirador 22 000 Pa 7,98 cm preto", "Samsung Galaxy S24 Ultra 256GB",
                 "Super Mario Bros Wonder Nintendo Switch", "Bola adidas Real Madrid Home Club"):
        assert extract_product_title(f"🔥 -30%! Mínimo histórico!\n{name}\nhttps://x") == name


def test_price_and_link_lines_are_never_the_title():
    from dealbot.cleaner import extract_product_title
    text = "❌ Antes: 60,98€\n✅ Agora: 32,00€\n[ 28€ desconto ]\n💥 Link: https://x\nLego Friends Central Perk"
    assert extract_product_title(text) == "Lego Friends Central Perk"
    assert extract_product_title("❌ Antes: 60,98€\n✅ Agora: 32,00€\nhttps://x") == "Oferta Especial"
