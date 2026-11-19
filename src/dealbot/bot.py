"""Uma execução do bot: trata mensagens do dono e propõe novas ofertas."""
import re
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from .card import make_card as default_make_card
from .compose import channel_caption, channel_post, parse_prices, proposal_text, short_title
from .config import Config
from .feed import Deal, fetch_feed, fetch_image as default_fetch_image, parse_feed
from .links import LinkError, build_affiliate_link, extract_asin, find_url
from .state import State
from .telegram import TelegramError
from .translate import to_pt

LISBON = ZoneInfo("Europe/Lisbon")
MAX_PROPOSALS = 3
QUIET_FROM, QUIET_UNTIL = 23, 8


def _reply(tg, chat, text, reply_to=None) -> bool:
    try:
        tg.send_message(chat, text, reply_to=reply_to)
        return True
    except TelegramError:
        return False


def _publish(cfg: Config, tg, title: str, category: str, link: str, image: str,
             fetch_image, make_card, price=None, old_price=None) -> None:
    """Cartão com foto se possível; senão (ou se a foto falhar) publicação só de texto."""
    photo = fetch_image(image) if image else None
    if photo:
        try:
            card = make_card(photo, short_title(title, 110), category, cfg.channel_id,
                             price=price, old_price=old_price)
            tg.send_photo_bytes(cfg.channel_id, card, channel_caption(title, link))
            return
        except (ValueError, TelegramError, OSError):
            pass
    tg.send_message(cfg.channel_id, channel_post(title, category, link))


def _handle_message(cfg: Config, tg, state: State, msg: dict, resolve,
                    fetch_image, make_card) -> bool:
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

    price, old_price, rest = parse_prices(text.replace(url, " "))
    reply_id = str(msg.get("reply_to_message", {}).get("message_id", ""))
    pending = state.pending.get(reply_id)
    image = ""
    if pending:
        title, category, image = pending["title"], pending.get("category", ""), pending.get("image", "")
    else:
        title, category = rest, ""
    if not title:
        _reply(tg, chat, "❌ Responde à mensagem da oferta ou escreve o título a seguir ao link.", mid)
        return True

    try:
        _publish(cfg, tg, title, category, build_affiliate_link(asin, cfg.amazon_tag), image,
                 fetch_image, make_card, price, old_price)
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


def handle_updates(cfg: Config, tg, state: State, resolve=None, fetch_image=default_fetch_image,
                   make_card=default_make_card) -> None:
    for update in tg.get_updates(state.offset):
        msg = update.get("message")
        if msg is not None and not _handle_message(cfg, tg, state, msg, resolve, fetch_image, make_card):
            return
        state.offset = update["update_id"] + 1


def propose_deals(cfg: Config, tg, state: State, fetch, parse, now: datetime, translate=to_pt) -> None:
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
        deal = Deal(deal.guid, translate(deal.title), translate(deal.category), deal.price,
                    deal.image, deal.thread_url)
        try:
            message_id = tg.send_message(cfg.owner_chat_id, proposal_text(deal))
        except TelegramError:
            return
        state.add_pending(message_id, deal)
        state.seen.append(deal.guid)
        sent += 1


def run_once(cfg: Config, tg, state: State, fetch=fetch_feed, now: datetime | None = None,
             resolve=None, parse=parse_feed, translate=to_pt, fetch_image=default_fetch_image,
             make_card=default_make_card) -> None:
    now = now or datetime.now(LISBON)
    handle_updates(cfg, tg, state, resolve, fetch_image, make_card)
    propose_deals(cfg, tg, state, fetch, parse, now, translate)
    state.trim()
