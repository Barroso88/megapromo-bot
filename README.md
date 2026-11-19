# MegaPromo: Monitor de Promoções Amazon.es para Telegram (Piggybacking)

Sistema automático em tempo real que monitoriza canais públicos de promoções no Telegram (usando Telethon), extrai os produtos da **Amazon Espanha**, substitui as tags de afiliado pela **tua tag**, gera automaticamente um **cartão visual com a imagem de marca do teu canal** (Pillow) e publica no teu canal.

---

## 🚀 Como Funciona o Fluxo Automático

1. **Escuta Contínua:** O script fica ligado ao Telegram através de MTProto (Telethon) a monitorizar 3 a 5 canais de referência em tempo real.
2. **Filtro & ASIN:** Quando surge uma mensagem com link da Amazon Espanha (direto `amazon.es` ou encurtado `amzn.to`/`amzn.eu`), descompacta o redirecionamento e extrai o código ASIN (10 caracteres).
3. **Deduplicação:** Verifica se o produto já foi publicado (em `data/state.json`). Se for repetido, ignora.
4. **Edição Visual & Branding:**
   - Descarrega a foto original do produto.
   - Gera um cartão quadrado elegante (1080x1080) com fundo limpo, a foto do produto, o título e uma faixa inferior com o handle do **teu** canal.
   - Limpa menções a outros canais (`@outros`, links `t.me/`, etc.).
   - Insere o teu link limpo de afiliado (`https://www.amazon.es/dp/{ASIN}?tag={TUA_TAG}`) e o aviso legal de afiliado da Amazon.
5. **Publicação:** Envia imediatamente para o teu canal de Telegram.

---

## 📋 Pré-requisitos

1. **Credenciais da API do Telegram:**
   - Vai a [my.telegram.org](https://my.telegram.org) e faz login com o teu número de telemóvel.
   - Clica em **API development tools** e cria uma aplicação (qualquer nome serve).
   - Guarda o **App api_id** e o **App api_hash**.
2. **Tag de Afiliado da Amazon:**
   - O teu Tracking ID da Amazon.es (ex.: `oteu-21`).
3. **Canais:**
   - Canais de origem a monitorizar (ex.: `@canal1, @canal2`).
   - O teu canal de destino (ex.: `@oteucanal`). Garante que a tua conta do Telegram é administradora com permissão de publicar mensagens.

---

## 🔑 Passo 1: Autenticação Inicial da Sessão

Antes de subir para o Unraid, autentica a tua conta localmente para gerar o ficheiro de sessão:

```bash
# 1. Instala dependências
pip install -r requirements.txt

# 2. Executa o assistente de login
python login.py
```
Insere o `api_id`, `api_hash`, o teu número de telefone e o código recebido no Telegram.  
Isto criará o ficheiro `data/dealbot.session`.

---

## 🐳 Passo 2: Executar no Unraid (Docker)

### Opção A: Docker Compose (Recomendado)

Cria uma pasta no teu Unraid (ex.: `/mnt/user/appdata/dealbot`), copia a pasta `data/` com a tua sessão e este projeto, e inicia o container:

```yaml
services:
  dealbot:
    build: .
    container_name: dealbot
    restart: unless-stopped
    volumes:
      - /mnt/user/appdata/dealbot/data:/app/data
    environment:
      - TELEGRAM_API_ID=12345678
      - TELEGRAM_API_HASH=abcdef0123456789abcdef0123456789
      - AMAZON_TAG=oteu-21
      - SOURCE_CHANNELS=@canal_origem1,@canal_origem2
      - TARGET_CHANNEL=@oteucanal
      - TELEGRAM_SESSION_PATH=/app/data/dealbot.session
```

Corre:
```bash
docker compose up -d
```

### Opção B: Adicionar Container manualmente na GUI do Unraid

1. No separador **Docker** do Unraid, clica em **Add Container**.
2. **Name:** `dealbot`
3. **Repository:** Compila a imagem localmente ou cria a partir do `Dockerfile`.
4. **Volume Mapping:**
   - Container Path: `/app/data`
   - Host Path: `/mnt/user/appdata/dealbot/data`
5. **Variáveis de Ambiente:**
   - `TELEGRAM_API_ID`: O teu API ID numérico.
   - `TELEGRAM_API_HASH`: O teu hash do Telegram.
   - `AMAZON_TAG`: O teu tracking ID da Amazon.es (ex: `oteu-21`).
   - `SOURCE_CHANNELS`: Canais a vigiar separados por vírgula (`@canal1,@canal2`).
   - `TARGET_CHANNEL`: O teu canal (`@teucanal`).
   - `TELEGRAM_SESSION_PATH`: `/app/data/dealbot.session`

---

## 🧪 Testes

Para correr a suite de testes automatizados:
```bash
.venv/bin/pytest
```
