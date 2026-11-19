"""Textos do canal e das propostas (Telegram HTML)."""
import re
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


PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})+|\d+)[,.](\d{2})\s*€?")


def parse_prices(text: str) -> tuple[str | None, str | None, str]:
    """Preços escritos pelo dono (até 2): devolve (atual, antigo, texto restante)."""
    found = [m.group(0).replace("€", "").strip() for m in PRICE_RE.finditer(text)][:2]
    rest = re.sub(r"\s+", " ", PRICE_RE.sub(" ", text)).strip()
    if not found:
        return None, None, rest
    def val(p): return float(p.replace(".", "").replace(",", "."))
    found.sort(key=val)
    return found[0], (found[1] if len(found) > 1 else None), rest


def short_title(title: str, limit: int = 90) -> str:
    title = title.strip()
    cut = title.split(" | ")[0].strip()
    if len(cut) >= 15:
        title = cut
    if len(title) <= limit:
        return title
    return title[: limit - 1].rstrip(" ,;-") + "…"


def channel_caption(title: str, link: str) -> str:
    head = f"<b>{escape(short_title(title, 200))}</b>"
    tail = f'👉 <a href="{escape(link, quote=True)}">Ver oferta</a>\n\n<i>{DISCLOSURE}</i>'
    return f"{head}\n\n{tail}"


def proposal_text(deal: Deal) -> str:
    lines = [f"<b>{escape(deal.title)}</b>"]
    if deal.price:
        lines.append(f"Preço (comunidade): {escape(deal.price)}")
    if deal.category:
        lines.append(f"Categoria: {escape(deal.category)}")
    lines.append(escape(deal.thread_url))
    lines.append("Responde a esta mensagem com o link da Amazon (amazon.es) para publicar.")
    return "\n".join(lines)
