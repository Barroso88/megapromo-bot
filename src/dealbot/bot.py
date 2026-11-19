"""Uma execução do bot: trata mensagens do dono e propõe novas ofertas."""
import re
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from .compose import channel_post, proposal_text
from .config import Config
from .feed import fetch_feed, parse_feed
from .links import LinkError, build_affiliate_link, extract_asin, find_url
from .state import State
from .telegram import TelegramError

LISBON = ZoneInfo("Europe/Lisbon")
MAX_PROPOSALS = 3
QUIET_FROM, QUIET_UNTIL = 23, 8


def _reply(tg, chat, text, reply_to=None) -> bool:
    try:
        tg.send_message(chat, text, reply_to=reply_to)
        return True
    except TelegramError:
        return False


def _handle_message(cfg: Config, tg, state: State, msg: dict, resolve) -> bool:
    """True se a mensagem ficou tratada (offset pode avançar); False para repetir."""
    if str(msg.get("chat", {}).get("id")) != str(cfg.owner_chat_id):
        return True
    text = msg.get("text") or msg.get("caption") or ""
    url = find_url(text)
    if not url:
        return True
    chat, mid = cfg.owner_chat_id, msg.get("message_id")
    try:
        asin = extract_asin(url, resolve=resolve)
    except LinkError as e:
        _reply(tg, chat, f"❌ {escape(str(e))}", mid)
        return True
    if not asin:
        _reply(tg, chat, "❌ Só aceito links da amazon.es (ou amzn.to / a.co).", mid)
        return True
    if asin in state.published:
        _reply(tg, chat, "ℹ️ Esse produto já foi publicado.", mid)
        return True

    reply_id = str(msg.get("reply_to_message", {}).get("message_id", ""))
    pending = state.pending.get(reply_id)
    if pending:
        title, category = pending["title"], pending.get("category", "")
    else:
        title, category = re.sub(r"\s+", " ", text.replace(url, " ")).strip(), ""
    if not title:
        _reply(tg, chat, "❌ Responde à mensagem da oferta ou escreve o título a seguir ao link.", mid)
        return True

    post = channel_post(title, category, build_affiliate_link(asin, cfg.amazon_tag))
    try:
        tg.send_message(cfg.channel_id, post)
    except TelegramError as e:
        # Avisa o dono; só repete se nem o aviso chegar. Evita bloquear a fila por um erro permanente.
        return _reply(
            tg, chat,
            f"❌ Não consegui publicar no canal ({escape(str(e))}). "
            "Verifica se o bot é administrador e se o CHANNEL_ID está certo; depois volta a colar o link.",
            mid,
        )
    state.mark_published(asin)
    state.pending.pop(reply_id, None)
    _reply(tg, chat, "✅ Publicado no canal.", mid)
    return True


def handle_updates(cfg: Config, tg, state: State, resolve=None) -> None:
    for update in tg.get_updates(state.offset):
        msg = update.get("message")
        if msg is not None and not _handle_message(cfg, tg, state, msg, resolve):
            return
        state.offset = update["update_id"] + 1


def propose_deals(cfg: Config, tg, state: State, fetch, parse, now: datetime) -> None:
    hour = (now.astimezone(LISBON) if now.tzinfo else now).hour
    if hour >= QUIET_FROM or hour < QUIET_UNTIL:
        return
    try:
        deals = parse(fetch())
    except Exception:
        return
    sent = 0
    for deal in deals:
        if sent >= MAX_PROPOSALS:
            break
        if deal.guid in state.seen:
            continue
        try:
            message_id = tg.send_message(cfg.owner_chat_id, proposal_text(deal))
        except TelegramError:
            return
        state.add_pending(message_id, deal)
        state.seen.append(deal.guid)
        sent += 1


def run_once(cfg: Config, tg, state: State, fetch=fetch_feed, now: datetime | None = None,
             resolve=None, parse=parse_feed) -> None:
    now = now or datetime.now(LISBON)
    handle_updates(cfg, tg, state, resolve)
    propose_deals(cfg, tg, state, fetch, parse, now)
    state.trim()
