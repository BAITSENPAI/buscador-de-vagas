import os
import sys
import socket
import webbrowser
import threading
import time
from pathlib import Path

# Garante suporte a UTF-8 no console Windows sem quebrar por emojis
if sys.platform.startswith("win"):
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Garante que o diretório base esteja no sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from backend.database import init_db

def find_free_port(start_port=8000, max_attempts=50):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return start_port

def open_browser(port):
    time.sleep(1.5)
    url = f"http://127.0.0.1:{port}"
    print(f"\n==========================================")
    print(f"[*] Buscador de Vagas com IA está ativo!")
    print(f"Acesse pelo navegador: {url}")
    print(f"Pressione CTRL+C nesta janela para encerrar.")
    print(f"==========================================\n")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Não foi possível abrir o navegador automaticamente: {e}")

def main():
    print("Inicializando o banco de dados local...")
    init_db()

    port = find_free_port(8000)
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    from backend.main import app
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

if __name__ == "__main__":
    main()
