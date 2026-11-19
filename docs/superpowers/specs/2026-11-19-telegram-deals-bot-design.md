# Bot de promoções Amazon.es para Telegram (semi-automático) — Design

## Intenção
Renda extra via links de afiliado Amazon.es num canal de Telegram, para Portugal, sem custos iniciais. O bot faz a descoberta e a publicação; o dono só fornece o link da Amazon (~10 s por oferta) até ter acesso à API oficial.

## Objetivos
- Descobrir ofertas Amazon.es e propô-las ao dono numa conversa privada do Telegram.
- Receber o link colado pelo dono, montar o link de afiliado e publicar no canal.
- Custo zero (Telegram Bot API, GitHub Actions, feed público).
- Cumprir as regras do programa: aviso de afiliado, sem preços apresentados como garantidos.

## Não-objetivos
- Ler páginas da Amazon ou do Chollometro (só o feed RSS público).
- Seguir os redirecionamentos `/visit/` do Chollometro (cria cliques no afiliado deles).
- Pagar serviços (Keepa). Crescimento do canal. Verificação de preço por API (fase 2).

## Restrições
- Conta Associates ES sem vendas: sem API oficial. Prazo de ~180 dias para a 1.ª venda (confirmar no painel).
- O feed do Chollometro (`https://www.chollometro.com/rss`) dá título, categoria, comerciante, preço e imagem, mas **não o ASIN** (link de saída escondido). Daí o passo manual.
- GitHub Actions não mantém processo ativo: o bot funciona por sondagem a cada ~5 min.
- Só links `amazon.es` (outros mercados exigem outro código de afiliado).

## Abordagens consideradas
- Keepa (pago): rejeitada. Seguir `/visit/`: rejeitada (regras, fragilidade). Só ofertas com link direto: rejeitada (1–2 em 30).
- **Semi-automático com feed + link colado pelo dono: escolhida.**

## Design
Cada execução (GitHub Actions, cron `*/5`) faz, por esta ordem:
1. **Mensagens do dono:** lê `getUpdates` (só do `OWNER_CHAT_ID`). Para cada mensagem com link Amazon: extrai o ASIN (resolve `amzn.to`/`a.co` por redirecionamento), monta `https://www.amazon.es/dp/ASIN?tag=<TAG>` (sempre de raiz, nunca reaproveita `tag` alheio), recupera o título da oferta se a mensagem for resposta a uma proposta, senão usa o texto a seguir ao link; publica no canal; responde ao dono com confirmação ou erro. ASIN já publicado → não republica.
2. **Novas propostas:** lê o feed, guarda ofertas com comerciante Amazon ainda não vistas, e envia ao dono até 3 por execução (título, categoria, preço da comunidade, link do Chollometro, imagem), sem enviar entre as 23h e as 08h (Europe/Lisbon). O `message_id` da proposta fica associado à oferta.
3. **Estado** em `data/state.json` (offset do Telegram, guids vistos, propostas pendentes por message_id, ASINs publicados), com commit pelo workflow.

Publicação no canal: título, categoria, link "Ver oferta", "Como Associado da Amazon, ganho com compras elegíveis. Preços sujeitos a alteração." Sem preço.

Segredos (GitHub Secrets): `TELEGRAM_BOT_TOKEN`, `OWNER_CHAT_ID`, `CHANNEL_ID`, `AMAZON_TAG`.

## Deixado ao construtor
Módulos, formato exato do texto, tratamento de erros de rede/limites do Telegram, testes. Python 3.11+, biblioteca padrão + `pytest`.

## Fase 2
Após 3 vendas e acesso à API: o passo manual passa a ser automático (ASIN e preço verificados pela API oficial).
