"""
main.py
-------
Ponto de entrada do driver Modbus.

Responsável por:
- Inicializar logging e configurações
- Criar instâncias de Memory e Manager
- Subir a API FastAPI (server_api.py)
"""

import signal
import sys
import uvicorn
from core.logger import logger
from core.config_loader import load_config
from manager.modbus_driver_manager import ModbusDriverManager
from api.server_api import app


def main():
    logger.info("Iniciando serviço principal Modbus Driver.")

    # Carrega config e inicializa FastAPI
    cfg = load_config()
    api_host = cfg.get("API", "host", fallback="0.0.0.0")
    api_port = cfg.getint("API", "port", fallback=8000)

    # Cria o gerenciador
    manager = ModbusDriverManager()
    app.state.manager = manager

    # Captura sinais do systemd (stop/restart)
    def handle_shutdown(sig, frame):
        logger.info(f"Sinal recebido ({sig}). Encerrando serviço.")
        manager.stop_driver()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    uvicorn.run(app, host=api_host, port=api_port, log_level="info")

if __name__ == "__main__":
    main()

