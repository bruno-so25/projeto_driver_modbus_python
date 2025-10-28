"""
main.py
-------
Ponto de entrada do driver Modbus.

Responsável por:
- Inicializar logging e configurações
- Criar instâncias de Memory e Manager
- Subir a API FastAPI (server_api.py)
"""

import uvicorn
from core.logger import logger
from core.config_loader import load_config
from manager.modbus_driver_manager import ModbusDriverManager
from api.server_api import app

if __name__ == "__main__":
    logger.info("Iniciando serviço principal Modbus Driver.")

    # 1. Carrega configurações
    cfg = load_config()
    api_host = cfg.get("API", "host", fallback="0.0.0.0")
    api_port = cfg.getint("API", "port", fallback=5020)

    # 2. Cria o gerenciador principal (driver + memória + watchdog)
    manager = ModbusDriverManager()

    # 3. Injeta o manager dentro da API
    app.state.manager = manager

    # 4. Inicia servidor FastAPI com Uvicorn
    uvicorn.run(app, host=api_host, port=api_port, log_level="info")
