"""Dashboard Web leve para o Unraid (visualização em tempo real das ofertas extraídas)."""
import json
import logging
import os
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger("dealbot.web")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MegaPromo Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #0b0f19; color: #f3f4f6; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .card-glow:hover { box-shadow: 0 10px 25px -5px rgba(255, 107, 0, 0.25); }
    </style>
</head>
<body class="min-h-screen">
    <!-- Navbar -->
    <header class="border-b border-gray-800 bg-gray-900/60 backdrop-blur sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <span class="text-2xl font-black tracking-wider text-orange-500">MEGA<span class="text-white">PROMO</span></span>
                <span class="bg-gray-800 text-xs px-2.5 py-0.5 rounded-full text-gray-300 font-mono">Unraid Live</span>
            </div>
            <div class="flex items-center space-x-4">
                <div class="flex items-center space-x-2">
                    <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    <span class="text-sm text-gray-300 font-medium">Monitor Ativo</span>
                </div>
                <a href="https://t.me/megapromo_pt" target="_blank" class="bg-orange-600 hover:bg-orange-500 text-white text-xs font-bold px-3 py-1.5 rounded-lg transition">Abrir Canal</a>
            </div>
        </div>
    </header>

    <!-- Conteúdo Principal -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <!-- Estatísticas -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-8">
            <div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <span class="text-xs text-gray-400 uppercase font-semibold">Ofertas Extraídas</span>
                <p id="total-count" class="text-3xl font-extrabold text-white mt-1">0</p>
            </div>
            <div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <span class="text-xs text-gray-400 uppercase font-semibold">Canal de Destino</span>
                <p class="text-xl font-bold text-orange-400 mt-2 truncate">@megapromo_pt</p>
            </div>
            <div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <span class="text-xs text-gray-400 uppercase font-semibold">Tag de Afiliado</span>
                <p class="text-xl font-bold text-emerald-400 mt-2 font-mono">megapromopt-21</p>
            </div>
        </div>

        <!-- Título da Galeria -->
        <div class="flex items-center justify-between mb-6">
            <h2 class="text-xl font-bold text-white flex items-center gap-2">
                <span>📸</span> Galeria de Posts Publicados
            </h2>
            <button onclick="fetchHistory()" class="text-sm bg-gray-800 hover:bg-gray-700 text-gray-200 px-3 py-1.5 rounded-lg border border-gray-700 transition">🔄 Atualizar</button>
        </div>

        <!-- Grelha de Ofertas -->
        <div id="deals-grid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            <!-- Os cartões são inseridos aqui dinamicamente -->
        </div>

        <div id="empty-state" class="text-center py-16 hidden">
            <p class="text-gray-500 text-lg">Ainda não foram extraídas ofertas nesta sessão.</p>
            <p class="text-gray-600 text-sm mt-1">O bot está à escuta nos canais do Telegram e adicionará as ofertas aqui em tempo real.</p>
        </div>
    </main>

    <script>
        async function fetchHistory() {
            try {
                const res = await fetch('/api/history');
                const data = await res.json();
                renderDeals(data);
            } catch (e) {
                console.error("Erro ao carregar histórico:", e);
            }
        }

        function renderDeals(deals) {
            const grid = document.getElementById('deals-grid');
            const empty = document.getElementById('empty-state');
            document.getElementById('total-count').textContent = deals.length;

            if (!deals || deals.length === 0) {
                grid.innerHTML = '';
                empty.classList.remove('hidden');
                return;
            }

            empty.classList.add('hidden');
            grid.innerHTML = deals.map(deal => {
                const time = deal.timestamp ? new Date(deal.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : '';
                return `
                <div class="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden card-glow transition duration-200 flex flex-col">
                    <div class="aspect-square bg-gray-950 relative overflow-hidden flex items-center justify-center border-b border-gray-800/80">
                        <img src="/images/${deal.image_file}" alt="${deal.title}" class="w-full h-full object-contain" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📦</text></svg>'">
                        <span class="absolute top-3 left-3 bg-gray-900/90 backdrop-blur text-xs text-orange-400 font-semibold px-2.5 py-1 rounded-full border border-gray-700/60">
                            ${deal.source || 'Telegram'}
                        </span>
                        <span class="absolute top-3 right-3 bg-gray-900/90 backdrop-blur text-xs text-gray-400 font-mono px-2 py-0.5 rounded">
                            ${time}
                        </span>
                    </div>
                    <div class="p-5 flex-1 flex flex-col justify-between">
                        <div>
                            <h3 class="text-white font-bold text-base line-clamp-2 leading-snug" title="${deal.title}">${deal.title}</h3>
                            <p class="text-xs text-gray-500 font-mono mt-1">ASIN: ${deal.asin}</p>
                        </div>
                        <div class="mt-4 pt-4 border-t border-gray-800/80 flex items-center justify-between">
                            <span class="text-xs font-semibold px-2 py-1 rounded bg-emerald-950 text-emerald-400 border border-emerald-800/60">Publicado ✅</span>
                            <a href="${deal.affiliate_link}" target="_blank" class="inline-flex items-center text-xs font-bold text-orange-400 hover:text-orange-300">
                                Ver na Amazon ➔
                            </a>
                        </div>
                    </div>
                </div>
                `;
            }).join('');
        }

        fetchHistory();
        setInterval(fetchHistory, 10000); // Atualiza automaticamente de 10 em 10 segundos
    </script>
</body>
</html>
"""


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, data_dir: Path, **kwargs):
        self.data_dir = data_dir
        super().__init__(*args, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
            return

        elif parsed.path == "/api/history":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            history_file = self.data_dir / "history.json"
            if history_file.exists():
                self.wfile.write(history_file.read_bytes())
            else:
                self.wfile.write(b"[]")
            return

        elif parsed.path.startswith("/images/"):
            filename = parsed.path.replace("/images/", "")
            img_path = self.data_dir / "cards" / filename
            if img_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.end_headers()
                self.wfile.write(img_path.read_bytes())
                return
            else:
                self.send_error(404, "Imagem não encontrada")
                return

        self.send_error(404, "Página não encontrada")


def save_deal_to_history(data_dir: Path, asin: str, title: str, source: str,
                         affiliate_link: str, card_bytes: bytes | None):
    """Guarda a oferta no histórico JSON e o cartão gerado no disco."""
    try:
        cards_dir = data_dir / "cards"
        cards_dir.mkdir(parents=True, exist_ok=True)

        image_filename = f"{asin}.jpg"
        if card_bytes:
            (cards_dir / image_filename).write_bytes(card_bytes)

        history_file = data_dir / "history.json"
        history = []
        if history_file.exists():
            try:
                history = json.loads(history_file.read_text(encoding="utf-8"))
            except Exception:
                history = []

        new_entry = {
            "asin": asin,
            "title": title,
            "source": source,
            "affiliate_link": affiliate_link,
            "image_file": image_filename,
            "timestamp": datetime.now().isoformat()
        }

        # Insere no início da lista (mais recente primeiro)
        history.insert(0, new_entry)
        history = history[:200] # Guarda até às últimas 200 ofertas

        history_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error("Erro ao guardar oferta no histórico web: %s", e)


def start_web_server(data_dir: Path, port: int = 8080):
    """Inicia o servidor web numa thread de background."""
    handler = lambda *args, **kwargs: DashboardHandler(*args, data_dir=data_dir, **kwargs)
    httpd = ThreadingHTTPServer(("0.0.0.0", port), handler)
    logger.info("🌐 Servidor WebUI iniciado na porta %d (http://0.0.0.0:%d)", port, port)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd
