#!/usr/bin/env python3
"""Script auxiliar para autenticar uma sessão do Telegram (Telethon)."""
import os
import sys
from pathlib import Path
from telethon.sync import TelegramClient

def main():
    print("=" * 60)
    print("🔐 Dealbot - Autenticação da Sessão Telegram")
    print("=" * 60)
    print("Precisas de um api_id e api_hash obtidos em https://my.telegram.org\n")

    api_id_default = "37175577"
    api_hash_default = "73f860a71855ab034e248b7cdcbfc681"

    api_id_env = os.environ.get("TELEGRAM_API_ID", api_id_default).strip()
    api_hash_env = os.environ.get("TELEGRAM_API_HASH", api_hash_default).strip()
    session_path = os.environ.get("TELEGRAM_SESSION_PATH", "data/dealbot.session").strip()

    if not api_id_env:
        api_id_raw = input("Introduz o teu TELEGRAM_API_ID: ").strip()
    else:
        api_id_raw = api_id_env

    if not api_hash_env:
        api_hash = input("Introduz o teu TELEGRAM_API_HASH: ").strip()
    else:
        api_hash = api_hash_env


    try:
        api_id = int(api_id_raw)
    except ValueError:
        print("❌ Erro: API ID tem de ser um número inteiro.")
        sys.exit(1)

    dest = Path(session_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    print(f"\nA ligar aos servidores do Telegram e a gravar em '{dest}'...")
    with TelegramClient(str(dest.with_suffix("")), api_id, api_hash) as client:
        me = client.get_me()
        print("\n" + "=" * 60)
        print(f"✅ Autenticado com sucesso como: {me.first_name} (@{me.username or 'sem_username'})")
        print(f"📁 Ficheiro de sessão guardado com sucesso!")
        print("Agora podes copiar este ficheiro para o teu servidor Unraid.")
        print("=" * 60)

if __name__ == "__main__":
    main()
