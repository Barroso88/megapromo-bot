# Bot de promoções Amazon.es (semi-automático) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bot de Telegram que propõe ofertas Amazon.es ao dono e, quando este cola o link da Amazon, publica no canal com o link de afiliado.

**Architecture:** Script Python de execução única (`python -m dealbot`) chamado a cada ~5 min pelo GitHub Actions. Sem servidor: sondagem por `getUpdates`, estado em `data/state.json` com commit pelo workflow. Módulos pequenos e puros (feed, asin, links, compose, state) orquestrados por `bot.run_once`, com o cliente Telegram e o `fetch` injetados para testar sem rede.

**Tech Stack:** Python 3.11+, biblioteca padrão (`urllib`, `xml.etree`, `json`, `zoneinfo`), `pytest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-19-telegram-deals-bot-design.md`

## Global Constraints

- Feed: `https://www.chollometro.com/rss` (200 OK com `User-Agent: Mozilla/5.0`). Nunca seguir `/visit/` nem fazer scraping de páginas.
- Link de afiliado sempre `https://www.amazon.es/dp/<ASIN>?tag=<AMAZON_TAG>`, construído de raiz; só domínios `amazon.es`, `amzn.to`, `a.co` aceites.
- Texto do canal inclui exatamente: `Como Associado da Amazon, ganho com compras elegíveis. Preços sujeitos a alteração.` e não mostra preço.
- Só mensagens de `OWNER_CHAT_ID` são processadas.
- Máx. 3 propostas por execução; nenhuma entre as 23h e as 08h `Europe/Lisbon`.
- Segredos só por variáveis de ambiente: `TELEGRAM_BOT_TOKEN`, `OWNER_CHAT_ID`, `CHANNEL_ID`, `AMAZON_TAG`. Nenhum valor real no repositório.
- Mensagens ao dono e posts em português de Portugal. Telegram `parse_mode=HTML` com texto escapado.

## Review Focus

- Mensagem de quem não é o dono → ignorada, sem resposta e sem publicação (Task 6).
- Link com `tag=` de terceiros ou parâmetros extra (`?tag=outro-21&ref=x`) → link final só com o nosso `tag` (Task 1).
- Link curto `amzn.to` que resolve para fora de `amazon.es`, ou falha de rede → erro ao dono, nada publicado (Task 1 e 6).
- Mesmo ASIN colado duas vezes → segunda vez não republica e avisa o dono (Task 6).
- Título com `&`, `<`, `>` → escapado no post e nas propostas (Task 3).
- Falha do feed ou do Telegram a meio → a execução não corrompe o estado nem perde o offset já confirmado (Task 6).

---

## File Structure

- `pyproject.toml` — metadados e config do pytest
- `src/dealbot/links.py` — ASIN e link de afiliado
- `src/dealbot/feed.py` — leitura do feed e `Deal`
- `src/dealbot/compose.py` — textos do canal e das propostas
- `src/dealbot/state.py` — `State` em JSON
- `src/dealbot/telegram.py` — cliente Telegram (HTTP)
- `src/dealbot/config.py` — `Config.from_env`
- `src/dealbot/bot.py` — `run_once`
- `src/dealbot/__main__.py` — ponto de entrada
- `tests/` — um ficheiro por módulo, mais `tests/fixtures/feed.xml`
- `.github/workflows/bot.yml`, `README.md`, `data/state.json`

### Task 1: Scaffold, ASIN e link de afiliado

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/dealbot/__init__.py`, `src/dealbot/links.py`, `tests/test_links.py`

**Interfaces:**
- Produces: `extract_asin(url: str, resolve=None) -> str | None`, `build_affiliate_link(asin: str, tag: str) -> str`, `find_url(text: str) -> str | None`, `class LinkError(Exception)`.
  `resolve: Callable[[str], str]` recebe um link curto e devolve o URL final (por defeito segue redirecionamentos com `urllib`, timeout 10 s).

- [ ] **Step 1:** `git init`; criar `pyproject.toml` (pacote em `src/`, `pytest` com `pythonpath=src`) e `.gitignore` (`__pycache__`, `.venv`).
- [ ] **Step 2: Testes** em `tests/test_links.py`:
  - `extract_asin("https://www.amazon.es/dp/B0DWDH32M8") == "B0DWDH32M8"`; idem para `/gp/product/B0DWDH32M8/ref=x` e `.../Nome-Produto/dp/B0DWDH32M8?th=1`.
  - `extract_asin("https://amzn.to/abc", resolve=lambda u: "https://www.amazon.es/dp/B0DWF3Y3P3") == "B0DWF3Y3P3"`.
  - `extract_asin("https://www.amazon.com/dp/B0DWDH32M8") is None`; `extract_asin("https://evil.com/dp/B0DWDH32M8") is None`; short link que resolve para `amazon.com` → `None`.
  - `resolve` a lançar `OSError` → `LinkError`.
  - `build_affiliate_link("B0DWDH32M8","meu-21") == "https://www.amazon.es/dp/B0DWDH32M8?tag=meu-21"`; ASIN inválido → `ValueError`.
  - `find_url("olá https://amzn.to/x?y=1 obrigado") == "https://amzn.to/x?y=1"`; sem URL → `None`.
  - Entrada `https://www.amazon.es/dp/B0DWDH32M8?tag=outro-21&ref=x` → `extract_asin` devolve o ASIN e o link construído só contém `tag=meu-21`.
- [ ] **Step 3:** Correr `pytest tests/test_links.py -v`. Esperado: FAIL (módulo inexistente).
- [ ] **Step 4:** Implementar em `links.py`. ASIN = 10 caracteres `[A-Z0-9]`; hosts permitidos `amazon.es`/`www.amazon.es`; `amzn.to` e `a.co` passam por `resolve` e o resultado volta a ser validado como `amazon.es`.
- [ ] **Step 5:** `pytest -v`. Esperado: PASS.
- [ ] **Step 6:** `git add -A && git commit -m "feat: extração de ASIN e link de afiliado"`

### Task 2: Leitura do feed

**Files:**
- Create: `src/dealbot/feed.py`, `tests/test_feed.py`, `tests/fixtures/feed.xml`

**Interfaces:**
- Produces: `@dataclass(frozen=True) Deal(guid: str, title: str, category: str, price: str, image: str, thread_url: str)`; `parse_feed(xml_text: str) -> list[Deal]` (só comerciante `Amazon`); `fetch_feed(url: str = FEED_URL) -> str` (com `User-Agent: Mozilla/5.0`, timeout 15 s).

- [ ] **Step 1:** Guardar em `tests/fixtures/feed.xml` um recorte real do feed (2 itens Amazon, 1 de outro comerciante, 1 sem `pepper:merchant`). Obter com `curl -A "Mozilla/5.0" https://www.chollometro.com/rss`.
- [ ] **Step 2: Testes:** `parse_feed` devolve só os 2 itens Amazon; o primeiro tem `price == "13,41€"`, `category == "Deportes y aire libre"`, `thread_url` começa por `https://www.chollometro.com/ofertas/`, `image` vem de `media:thumbnail`; XML inválido → lista vazia sem exceção; item sem preço → `price == ""`.
- [ ] **Step 3:** Correr → FAIL. Implementar com `xml.etree.ElementTree` e namespace `http://www.pepper.com/rss`. `guid` = `<guid>`.
- [ ] **Step 4:** Correr → PASS. Commit `feat: leitura do feed`.

### Task 3: Composição de textos

**Files:**
- Create: `src/dealbot/compose.py`, `tests/test_compose.py`

**Interfaces:**
- Consumes: `Deal` (Task 2).
- Produces: `channel_post(title: str, category: str, link: str) -> str`; `proposal_text(deal: Deal) -> str`; constante `DISCLOSURE`.

- [ ] **Step 1: Testes:** `channel_post("Bola adidas & Co <5>", "Deportes", "https://www.amazon.es/dp/B0DWDH32M8?tag=meu-21")` contém `Bola adidas &amp; Co &lt;5&gt;`, contém o link num `<a href="...">Ver oferta</a>`, termina com `DISCLOSURE` (texto exato das Global Constraints) e não contém `€`. `proposal_text(deal)` contém título escapado, preço, categoria e `thread_url`, e a instrução "Responde a esta mensagem com o link da Amazon".
- [ ] **Step 2:** FAIL → implementar com `html.escape` → PASS → commit `feat: textos`.

### Task 4: Estado

**Files:**
- Create: `src/dealbot/state.py`, `tests/test_state.py`

**Interfaces:**
- Produces: `@dataclass State(offset: int = 0, seen: list[str], pending: dict[str, dict], published: list[str])`; `State.load(path) -> State` (ficheiro em falta ou corrompido → estado vazio); `State.save(path)` (escrita atómica: ficheiro temporário + `os.replace`); `State.add_pending(message_id: int, deal: Deal)`; `State.mark_published(asin: str)`; `State.trim()` limita `seen` a 500 e `pending` às 100 mais recentes.

- [ ] **Step 1: Testes:** ida-e-volta `save`/`load` preserva tudo; JSON corrompido → `State()`; `trim` com 600 `seen` deixa 500 (os mais recentes); `pending` indexado por `str(message_id)` com `title`, `category`, `price`.
- [ ] **Step 2:** FAIL → implementar → PASS → commit `feat: estado`.

### Task 5: Cliente Telegram

**Files:**
- Create: `src/dealbot/telegram.py`, `tests/test_telegram.py`

**Interfaces:**
- Produces: `class Telegram(token: str, opener=urllib.request.urlopen)` com `get_updates(offset: int) -> list[dict]`, `send_message(chat_id: str | int, text: str, reply_to: int | None = None) -> int` (devolve `message_id`), `send_photo(chat_id, photo_url: str, caption: str) -> int`; `class TelegramError(Exception)`. Chamadas a `https://api.telegram.org/bot<token>/<método>` com JSON, `parse_mode=HTML`, `disable_web_page_preview` ativo para mensagens de texto.

- [ ] **Step 1: Testes** com `opener` falso (devolve bytes JSON): `send_message` envia o corpo esperado e devolve `result.message_id`; `get_updates(5)` envia `offset=5` e `timeout=0`; resposta `{"ok": false, "description": "x"}` → `TelegramError`; erro de rede → `TelegramError`; o token nunca aparece na mensagem da exceção.
- [ ] **Step 2:** FAIL → implementar → PASS → commit `feat: cliente telegram`.

### Task 6: Orquestração (`run_once`)

**Files:**
- Create: `src/dealbot/config.py`, `src/dealbot/bot.py`, `src/dealbot/__main__.py`, `tests/test_bot.py`

**Interfaces:**
- Consumes: tudo das Tasks 1–5.
- Produces: `@dataclass Config(token, owner_chat_id: str, channel_id: str, amazon_tag: str)` com `Config.from_env()` (variável em falta → `SystemExit` com mensagem a nomeá-la, sem imprimir valores); `run_once(cfg: Config, tg: Telegram, state: State, fetch=fetch_feed, now: datetime | None = None, resolve=None) -> None`.

Ordem em `run_once`: (1) `handle_updates` — para cada update `offset = update_id + 1` é gravado em `state` só depois de a mensagem ser tratada; (2) `propose_deals` — só se `now` (Europe/Lisbon) estiver entre as 08h e as 23h.

- [ ] **Step 1: Testes** com `Telegram` falso (regista chamadas) e `fetch` falso:
  - Resposta do dono a uma proposta com link `amazon.es/dp/B0DWDH32M8` → uma chamada ao canal com o link `?tag=...` e o título da proposta; resposta ao dono com confirmação; ASIN em `state.published`.
  - Link sem resposta e sem texto adicional → nada publicado, resposta ao dono a pedir "responde à mensagem da oferta ou escreve o título a seguir ao link".
  - Link + texto "Bola adidas" sem resposta → publicado com esse título.
  - Mensagem de outro `chat_id` → zero chamadas de envio, mas `offset` avança.
  - Mesmo ASIN duas vezes → um único envio ao canal e aviso "já publicado".
  - `resolve` com erro → resposta de erro ao dono, nada publicado.
  - `propose_deals` com 5 ofertas Amazon novas → envia 3, `seen` guarda as 3 enviadas (as outras 2 ficam para a execução seguinte), `pending` mapeia cada `message_id`; segunda execução não reenvia as 3.
  - `now` às 02:00 → nenhuma proposta enviada.
  - `fetch` a lançar exceção → `run_once` conclui sem erro e o tratamento de mensagens do dono continua a funcionar.
  - `Telegram.send_message` ao canal a falhar → `offset` dessa mensagem **não** avança e o ASIN não é marcado como publicado.
- [ ] **Step 2:** FAIL → implementar `config.py`, `bot.py`. `__main__.py`: carrega `State` de `data/state.json`, corre `run_once`, grava o estado (mesmo com exceção, via `finally`).
- [ ] **Step 3:** `pytest -v`. Esperado: tudo PASS.
- [ ] **Step 4:** Commit `feat: orquestração do bot`.

### Task 7: Workflow, README e ensaio real

**Files:**
- Create: `.github/workflows/bot.yml`, `README.md`, `data/state.json` (`{}`)

- [ ] **Step 1:** Workflow: `schedule: "*/5 * * * *"` + `workflow_dispatch`; `permissions: contents: write`; `concurrency: group: dealbot, cancel-in-progress: false`; passos: checkout, `actions/setup-python` 3.12, `python -m dealbot` com os 4 segredos em `env`, e commit/push de `data/state.json` só se mudou (`git diff --quiet || ...`, utilizador `github-actions[bot]`).
- [ ] **Step 2:** README em português: criar o bot em @BotFather; criar o canal e adicionar o bot como administrador com permissão de publicar; obter `OWNER_CHAT_ID` (enviar `/start` ao bot e abrir `getUpdates`); obter `CHANNEL_ID`; criar os 4 segredos no repositório; como usar (responder à proposta com o link da amazon.es, copiado do browser ou do Site Stripe); lembrete do prazo de 180 dias e do aviso de afiliado.
- [ ] **Step 3 (com o dono):** criar repositório privado no GitHub, push, definir segredos, correr o workflow manualmente. Esperado: chegam até 3 propostas ao chat privado; responder a uma com um link real → aparece no canal com o teu `tag`.
- [ ] **Step 4:** Commit `docs: workflow e README`.

---

## Self-Review

- **Cobertura do design:** feed (T2), ASIN/link/regras de domínio e `tag` próprio (T1), textos e aviso (T3), estado (T4), Telegram (T5), passos 1–3 do design, horário e limite de 3 (T6), cron/segredos/commit de estado (T7). Fase 2 fora do âmbito.
- **Tipos:** `Deal` (T2) usado em T3, T4 e T6; `State.add_pending/mark_published` (T4) usados em T6; `Telegram.send_message -> int` (T5) usado para `pending`.
- **Review Focus:** cada linha tem teste na task indicada.
