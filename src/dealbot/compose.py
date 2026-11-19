"""Textos do canal e das propostas (Telegram HTML)."""
from html import escape

from .feed import Deal

DISCLOSURE = "Como Associado da Amazon, ganho com compras elegíveis. Preços sujeitos a alteração."


def channel_post(title: str, category: str, link: str) -> str:
    parts = [f"<b>{escape(title)}</b>"]
    if category:
        parts.append(f"🏷 {escape(category)}")
    parts.append(f'👉 <a href="{escape(link, quote=True)}">Ver oferta</a>')
    parts.append(f"<i>{DISCLOSURE}</i>")
    return "\n\n".join(parts)


def proposal_text(deal: Deal) -> str:
    lines = [f"<b>{escape(deal.title)}</b>"]
    if deal.price:
        lines.append(f"Preço (comunidade): {escape(deal.price)}")
    if deal.category:
        lines.append(f"Categoria: {escape(deal.category)}")
    lines.append(escape(deal.thread_url))
    lines.append("Responde a esta mensagem com o link da Amazon (amazon.es) para publicar.")
    return "\n".join(lines)
