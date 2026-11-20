"""Monitor em tempo real de canais Telegram (Piggybacking) com Telethon."""
import asyncio
import io
import logging
from pathlib import Path

from telethon import TelegramClient, events

from .card import make_card
from .cleaner import clean_text_for_repost, compose_repost_caption, extract_links_from_telethon_message, extract_product_title
from .product_image import isolate_product
from .price_extractor import extract_prices
from .compose import short_title
from .config import ListenerConfig
from .links import LinkError, build_affiliate_link, extract_asin
from .state import State
from .web import save_deal_to_history, save_discard_to_history, start_web_server

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dealbot.listener")


async def _audit_discard(client, cfg: ListenerConfig, source: str, asin: str, url: str, reason: str,
                         data_dir: Path | None = None, title: str = "",
                         price_before: str | None = None, price_after: str | None = None) -> None:
    """Regista no log, no dashboard e no chat de auditoria (se houver) uma oferta que NÃO foi publicada."""
    logger.info("🚫 Oferta %s descartada: %s", asin, reason)
    if data_dir is not None:
        save_discard_to_history(data_dir, asin, title, source, url, reason, price_before, price_after)
    if not cfg.audit_chat:
        return
    try:
        await client.send_message(
            cfg.audit_chat,
            f"🚫 <b>[MEGAPROMO - DESCARTADO]</b>\n\n"
            f"📢 <b>Origem:</b> {source}\n"
            f"📦 <b>ASIN:</b> <code>{asin}</code>\n"
            f"🔗 <a href=\"{url}\">Link Original</a>\n"
            f"<i>Não publicado: {reason}.</i>",
            parse_mode="html",
            link_preview=False,
        )
    except Exception:
        pass


async def process_incoming_message(client: TelegramClient, message, cfg: ListenerConfig, state: State, state_file: Path):
    """Processa uma mensagem recebida de um dos canais monitorizados."""
    urls = extract_links_from_telethon_message(message)
    if not urls:
        return

    raw_text = getattr(message, "raw_text", None) or (message.text or "") or (getattr(message, "message", "") or "")
    
    # Obtém o nome/título do canal de origem para o log
    source_display = "Canal Desconhecido"
    try:
        chat = await message.get_chat()
        username = getattr(chat, "username", None)
        title_chat = getattr(chat, "title", None)
        source_display = f"@{username}" if username else (title_chat or "Canal")
    except Exception:
        pass

    # Procura um link da Amazon válido
    detected_asin = None
    original_url = None
    for url in urls:
        try:
            asin = extract_asin(url)
            if asin:
                detected_asin = asin
                original_url = url
                break
        except (LinkError, Exception) as e:
            logger.debug("Falha ao analisar url %s: %s", url, e)
            continue

    if not detected_asin:
        return

    # Deduplicação: se já publicámos este produto, ignora
    if detected_asin in state.published:
        logger.info("ℹ️ Produto %s já foi publicado anteriormente. Ignorando.", detected_asin)
        if cfg.audit_chat:
            try:
                audit_dup = (
                    f"ℹ️ <b>[MEGAPROMO - JÁ PUBLICADO]</b>\n\n"
                    f"📢 <b>Origem:</b> {source_display}\n"
                    f"📦 <b>ASIN:</b> <code>{detected_asin}</code>\n"
                    f"🔗 <a href=\"{original_url}\">Link Original</a>\n"
                    f"<i>Descartado para evitar produtos repetidos no teu canal.</i>"
                )
                await client.send_message(cfg.audit_chat, audit_dup, parse_mode="html", link_preview=False)
            except Exception:
                pass
        return

    logger.info("🎯 Nova promoção detetada! ASIN: %s", detected_asin)

    # Prepara o link com a tua tag de afiliado
    affiliate_link = build_affiliate_link(detected_asin, cfg.amazon_tag)

    # Extrai o título real do produto ignorando chamadas genéricas
    title = extract_product_title(raw_text, resolved_url=original_url)

    clean_body = clean_text_for_repost(raw_text, cfg.target_channel)
    caption = compose_repost_caption(
        title=title,
        clean_body=clean_body,
        affiliate_link=affiliate_link,
        target_handle=cfg.target_channel,
    )

    # Só se publica quando os DOIS preços (antes e agora) foram lidos: do texto ou da imagem (OCR).
    photo_data = None
    if message.photo:
        try:
            photo_data = await message.download_media(file=bytes)
        except Exception as e:
            logger.warning("Não foi possível descarregar a foto (%s).", e)
    price_before, price_after = await asyncio.to_thread(extract_prices, raw_text, photo_data)
    logger.info("💰 Preços detetados: Antes=%s, Depois=%s", price_before, price_after)
    if not (price_before and price_after):
        await _audit_discard(client, cfg, source_display, detected_asin, original_url,
                             "preços antes/depois não detetados",
                             data_dir=state_file.parent, title=title,
                             price_before=price_before, price_after=price_after)
        return

    card_bytes = None
    if photo_data:
        try:
            # Só depois de ler os preços: corta a foto ao produto (sem faixa de preço, logótipo nem marca do canal)
            photo_data = await asyncio.to_thread(isolate_product, photo_data)
            card_bytes = make_card(
                photo_data,
                title,
                "",
                cfg.target_channel,
                price=price_after,
                old_price=price_before,
            )
            logger.info("🎨 Cartão visual com branding gerado com sucesso!")
        except Exception as e:
            logger.warning("Não foi possível gerar o cartão personalizado (%s).", e)
            await _audit_discard(client, cfg, source_display, detected_asin, original_url,
                                 "não foi possível gerar o cartão",
                                 data_dir=state_file.parent, title=title,
                                 price_before=price_before, price_after=price_after)
            return

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

        # Envia relatório visual de auditoria para o teu chat privado ou grupo de controlo
        if cfg.audit_chat:
            try:
                audit_report = (
                    f"🎯 <b>[MEGAPROMO - NOVA PUBLICAÇÃO]</b>\n\n"
                    f"📢 <b>Origem:</b> {source_display}\n"
                    f"📦 <b>ASIN:</b> <code>{detected_asin}</code>\n"
                    + (f"💰 <b>Preços lidos (OCR):</b> antes {price_before} → agora {price_after}\n" if price_after else "")
                    + f"🔗 <b>Original:</b> <a href=\"{original_url}\">Ver link original</a>\n"
                    f"🚀 <b>Teu Link:</b> <a href=\"{affiliate_link}\">Ver com tua tag</a>\n"
                    f"✅ <b>Publicado em:</b> {cfg.target_channel}"
                )
                if card_bytes:
                    audit_file = io.BytesIO(card_bytes)
                    audit_file.name = "audit.jpg"
                    await client.send_file(cfg.audit_chat, audit_file, caption=audit_report, parse_mode="html")
                elif message.photo or message.media:
                    await client.send_file(cfg.audit_chat, message.media, caption=audit_report, parse_mode="html")
                else:
                    await client.send_message(cfg.audit_chat, audit_report, parse_mode="html", link_preview=True)
            except Exception as e:
                logger.warning("Não foi possível enviar relatório de auditoria para %s: %s", cfg.audit_chat, e)

        # Regista e persiste o estado
        state.mark_published(detected_asin)
        state.trim()
        state.save(state_file)

        # Guarda no histórico da WebUI
        save_deal_to_history(
            data_dir=state_file.parent,
            asin=detected_asin,
            title=title,
            source=source_display,
            affiliate_link=affiliate_link,
            card_bytes=card_bytes,
        )
    except Exception as e:
        logger.error("❌ Erro ao publicar mensagem no canal de destino: %s", e)


async def start_listener(cfg: ListenerConfig):
    state_file = Path(cfg.session_path).parent / "state.json"
    state = State.load(state_file)
    logger.info("Estado carregado: %d produtos já publicados.", len(state.published))

    # Inicia o Dashboard Web na porta configurada (padrão: 8080)
    web_port = int(Path().cwd().joinpath("").parent and "8080")
    try:
        import os
        port = int(os.environ.get("WEB_PORT", "8080"))
        start_web_server(data_dir=state_file.parent, port=port)
    except Exception as e:
        logger.warning("Não foi possível iniciar o servidor WebUI: %s", e)

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
