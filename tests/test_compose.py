from dealbot.compose import DISCLOSURE, channel_post, proposal_text
from dealbot.feed import Deal

LINK = "https://www.amazon.es/dp/B0DWDH32M8?tag=meu-21"


def test_disclosure_text_exact():
    assert DISCLOSURE == "Como Associado da Amazon, ganho com compras elegíveis. Preços sujeitos a alteração."


def test_channel_post_escapes_and_has_link_and_disclosure():
    t = channel_post("Bola adidas & Co <5>", "Deportes", LINK)
    assert "Bola adidas &amp; Co &lt;5&gt;" in t
    assert f'<a href="{LINK}">Ver oferta</a>' in t
    assert t.endswith(f"<i>{DISCLOSURE}</i>")
    assert "€" not in t


def test_proposal_text():
    d = Deal("g", "Bola <x> & y", "Deportes", "13,41€", "https://img/x.jpg", "https://www.chollometro.com/ofertas/x-1")
    t = proposal_text(d)
    assert "Bola &lt;x&gt; &amp; y" in t
    assert "13,41€" in t and "Deportes" in t
    assert "https://www.chollometro.com/ofertas/x-1" in t
    assert "Responde a esta mensagem com o link da Amazon" in t


def test_short_title_cuts_on_separator_and_limit():
    from dealbot.compose import short_title
    assert short_title("Televisor TCL 55 polegadas | Alexa, Dolby Atmos e muito mais", 40) == "Televisor TCL 55 polegadas"
    assert len(short_title("a" * 300, 50)) <= 50 and short_title("a" * 300, 50).endswith("…")
    assert short_title("Curto", 50) == "Curto"


def test_channel_caption_has_title_link_disclosure_and_fits_telegram():
    from dealbot.compose import DISCLOSURE, channel_caption
    c = channel_caption("Bola & Co", "https://www.amazon.es/dp/X?tag=a-21")
    assert "Bola &amp; Co" in c and 'href="https://www.amazon.es/dp/X?tag=a-21"' in c and DISCLOSURE in c
    assert len(channel_caption("t" * 2000, "https://x")) <= 1024
