# Bot de promoções Amazon.es → Telegram (semi-automático)

O bot propõe-te ofertas da Amazon no Telegram. Tu respondes com o link da amazon.es e ele publica no canal com o **teu** código de afiliado.

## Configuração (uma vez)
1. **Criar o bot:** no Telegram, fala com `@BotFather` → `/newbot` → guarda o token.
2. **Criar o canal** (público ou privado) e adicionar o bot como **administrador** com permissão para publicar.
3. **OWNER_CHAT_ID:** envia `/start` ao teu bot e abre `https://api.telegram.org/bot<TOKEN>/getUpdates` no browser; copia `message.chat.id`. (Faz isto antes de ativar o workflow, para o bot não consumir a mensagem.)
4. **CHANNEL_ID:** `@nomedocanal` (canal público) ou o id numérico `-100…` (privado).
5. **Repositório no GitHub:** faz push deste projeto e cria, em *Settings → Secrets and variables → Actions*, os segredos `TELEGRAM_BOT_TOKEN`, `OWNER_CHAT_ID`, `CHANNEL_ID`, `AMAZON_TAG` (ex.: `oteu-21`, o teu Tracking ID da amazon.es).
   > **Custo:** o workflow corre ~8 600 vezes por mês. Num repositório **público** o GitHub Actions é grátis e ilimitado, e não expõe segredos (ficam em *Secrets*; o repositório só tem código e `data/state.json` com títulos e ASINs já publicados). Num repositório **privado** o plano gratuito dá 2 000 minutos/mês e o bot ficaria parado a meio do mês: nesse caso muda o cron em `.github/workflows/bot.yml` para `*/30 7-22 * * *` (~950 min/mês).
6. Em *Actions* corre o workflow `dealbot` manualmente (*Run workflow*). Passa a correr sozinho de ~5 em ~5 minutos.

## Uso diário
- Chegam-te propostas (máx. 3 por execução, nunca entre as 23h e as 08h). Na primeira execução podes receber várias seguidas.
- Abre a oferta, copia o link da amazon.es do produto (ou o link curto do Site Stripe) e **responde à mensagem da proposta** com esse link.
- Também podes colar um link com o título a seguir (`https://www.amazon.es/dp/... Bola adidas`) sem responder.
- O bot publica no canal e confirma. Produtos repetidos não são republicados.

## Regras a respeitar
- Só links `amazon.es`. O bot usa sempre o teu `tag`, nunca o de terceiros.
- O aviso de afiliado vai em todos os posts. Os posts não mostram preço.
- A conta de Associados costuma fechar sem vendas qualificadas em 180 dias: confirma a tua data no painel.

## Desenvolvimento
```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest && .venv/bin/pytest
```
