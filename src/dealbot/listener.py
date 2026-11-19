"""Monitor em tempo real de canais Telegram (Piggybacking) com Telethon."""
import asyncio
import io
import logging
from pathlib import Path

from telethon import TelegramClient, events

from .card import make_card
from .cleaner import clean_text_for_repost, compose_repost_caption, extract_links_from_telethon_message
from .compose import short_title
from .config import ListenerConfig
from .links import LinkError, build_affiliate_link, extract_asin
from .state import State

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dealbot.listener")


async def process_incoming_message(client: TelegramClient, message, cfg: ListenerConfig, state: State, state_file: Path):
    """Processa uma mensagem recebida de um dos canais monitorizados."""
    urls = extract_links_from_telethon_message(message)
    if not urls:
        return

    raw_text = (message.text or "") or (getattr(message, "message", "") or "")
    
    # Procura um link da Amazon válido
    detected_asin = None
    for url in urls:
        try:
            asin = extract_asin(url)
            if asin:
                detected_asin = asin
                break
        except (LinkError, Exception) as e:
            logger.debug("Falha ao analisar url %s: %s", url, e)
            continue

    if not detected_asin:
        return

    # Deduplicação: se já publicámos este produto, ignora
    if detected_asin in state.published:
        logger.info("ℹ️ Produto %s já foi publicado anteriormente. Ignorando.", detected_asin)
        return

    logger.info("🎯 Nova promoção detetada! ASIN: %s", detected_asin)

    # Prepara o link com a tua tag de afiliado
    affiliate_link = build_affiliate_link(detected_asin, cfg.amazon_tag)

    # Extrai o título e limpa o texto
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    first_line = lines[0] if lines else "Oferta Amazon"
    # Se a primeira linha contiver apenas o link, tenta a seguinte
    if first_line.lower().startswith("http") and len(lines) > 1:
        first_line = lines[1]
    title = short_title(first_line, 120)

    clean_body = clean_text_for_repost(raw_text, cfg.target_channel)
    caption = compose_repost_caption(
        title=title,
        clean_body=clean_body,
        affiliate_link=affiliate_link,
        target_handle=cfg.target_channel,
    )

    # Processamento visual: tentar obter a foto e criar o cartão do canal
    card_bytes = None
    if message.photo:
        try:
            photo_data = await message.download_media(file=bytes)
            if photo_data:
                card_bytes = make_card(
                    photo=photo_data,
                    title=short_title(title, 110),
                    category="",
                    handle=cfg.target_channel,
                )
                logger.info("🎨 Cartão visual com branding gerado com sucesso!")
        except Exception as e:
            logger.warning("Não foi possível gerar o cartão personalizado (%s). Usando fallback.", e)

    # Publicação no teu canal
    try:
        if card_bytes:
            file_obj = io.BytesIO(card_bytes)
            file_obj.name = "deal.jpg"
            await client.send_file(cfg.target_channel, file_obj, caption=caption, parse_mode="html")
        elif message.photo or message.media:
            # Fallback: reencaminha a mídia original mas com a tua legenda
            await client.send_file(cfg.target_channel, message.media, caption=caption, parse_mode="html")
        else:
            await client.send_message(cfg.target_channel, caption, parse_mode="html", link_preview=True)

        logger.info("✅ Publicado com sucesso no canal %s!", cfg.target_channel)

        # Regista e persiste o estado
        state.mark_published(detected_asin)
        state.trim()
        state.save(state_file)
    except Exception as e:
        logger.error("❌ Erro ao publicar mensagem no canal de destino: %s", e)


async def start_listener(cfg: ListenerConfig):
    state_file = Path(cfg.session_path).parent / "state.json"
    state = State.load(state_file)
    logger.info("Estado carregado: %d produtos já publicados.", len(state.published))

    session_path = Path(cfg.session_path)
    session_path.parent.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(str(session_path), cfg.api_id, cfg.api_hash)
    await client.start()
    logger.info("🚀 Telethon ligado com sucesso! A validar canais configurados...")

    valid_chats = []
    for ch in cfg.source_channels:
        try:
            entity = await client.get_entity(ch)
            valid_chats.append(entity)
            logger.info("✅ Canal ativo e monitorizado: %s (%s)", ch, getattr(entity, "title", ch))
        except Exception as e:
            logger.warning("⚠️ Não foi possível aceder ao canal '%s': %s. Ignorando este canal.", ch, e)

    if not valid_chats:
        logger.error("❌ Nenhum canal de origem válido foi encontrado. Verifica a variável SOURCE_CHANNELS.")
    else:
        logger.info("🎧 A escutar em tempo real %d canais válidos!", len(valid_chats))

        @client.on(events.NewMessage(chats=valid_chats))
        async def handler(event):
            try:
                await process_incoming_message(client, event.message, cfg, state, state_file)
            except Exception as e:
                logger.error("Erro inesperado no handler de mensagens: %s", e)

    await client.run_until_disconnected()


def main():
    cfg = ListenerConfig.from_env()
    asyncio.run(start_listener(cfg))


if __name__ == "__main__":
    main()
