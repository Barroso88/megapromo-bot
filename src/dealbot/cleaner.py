"""Limpeza e reformatação de mensagens copiadas de outros canais."""
import re
from html import escape
from .compose import DISCLOSURE, short_title
from .links import find_url, extract_asin, build_affiliate_link

# Regex para limpar arrobas de canais concorrentes e links t.me
USERNAME_RE = re.compile(r"@([a-zA-Z0-9_]{4,32})")
TELEGRAM_LINK_RE = re.compile(r"https?://(?:t|telegram)\.me/[a-zA-Z0-9_+/]+")
HTTP_LINK_RE = re.compile(r"https?://\S+")


def extract_links_from_telethon_message(message) -> list[str]:
    """Extrai URLs do texto, caption e botões inline da mensagem do Telethon."""
    urls = []
    text = (message.text or "") + "\n" + (getattr(message, "message", "") or "")
    for match in HTTP_LINK_RE.finditer(text):
        urls.append(match.group(0))

    # Verifica botões inline (reply_markup)
    reply_markup = getattr(message, "reply_markup", None)
    if reply_markup and hasattr(reply_markup, "rows"):
        for row in reply_markup.rows:
            for btn in getattr(row, "buttons", []):
                url = getattr(btn, "url", None)
                if url:
                    urls.append(url)
    return urls


def clean_text_for_repost(raw_text: str, target_handle: str) -> str:
    """
    Remove menções a outros canais (@outro, t.me/outro),
    remove links brutos e prepara o texto limpo mantendo descrição/preço.
    """
    if not raw_text:
        return ""

    lines = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Remove links do Telegram e arrobas
        line = TELEGRAM_LINK_RE.sub("", line)
        line = USERNAME_RE.sub("", line)
        # Se a linha continha apenas o link ou ficou vazia/irrelevante, ignora
        line = line.strip(" -—•*~")
        if line and not line.lower().startswith("http"):
            lines.append(line)

    cleaned = "\n".join(lines).strip()
    return cleaned


def compose_repost_caption(title: str, clean_body: str, affiliate_link: str, target_handle: str) -> str:
    """
    Formata o post com a identidade visual e dados do teu canal.
    """
    parts = []
    header_title = short_title(title, 140) if title else ""
    if header_title:
        parts.append(f"🔥 <b>{escape(header_title)}</b>")

    # Se o texto original limpo tiver detalhes (ex: especificações ou cupões) que não sejam apenas o título
    if clean_body:
        # Se o clean_body não for idêntico ao título
        body_lines = [l for l in clean_body.splitlines() if l.strip() and l.strip() != header_title][:6]
        if body_lines:
            parts.append(escape("\n".join(body_lines)))

    parts.append(f'👉 <a href="{escape(affiliate_link, quote=True)}"><b>VER OFERTA NA AMAZON</b></a>')
    
    if target_handle:
        handle = target_handle if target_handle.startswith("@") else f"@{target_handle}"
        parts.append(f"📢 Segue <b>{escape(handle)}</b> para não perderes promoções!")

    parts.append(f"<i>{DISCLOSURE}</i>")
    return "\n\n".join(parts)
