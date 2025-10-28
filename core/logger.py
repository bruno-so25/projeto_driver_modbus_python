"""
core/logger.py
---------------
Gerencia o sistema de logs do driver Modbus.

Objetivos:
- Criar logs detalhados de eventos e operações (leituras, escritas, status).
- Permitir ativar/desativar modo DEBUG em tempo de execução.
- Fazer rotação automática dos arquivos de log para evitar crescimento excessivo.

Usa o módulo logging do Python com RotatingFileHandler.
"""

import logging
from logging.handlers import RotatingFileHandler
from .config_loader import load_config

# Variável global de controle do nível de debug
DEBUG_ENABLED = False


def setup_logger():
    """
    Configura o logger principal do sistema com base no settings.ini.
    A função pode ser chamada várias vezes (por exemplo, após reload de configuração).
    """
    global DEBUG_ENABLED

    # Carrega configurações
    config = load_config()
    log_file = config.get('LOGGING', 'log_file', fallback='logs/driver.log')
    log_level_str = config.get('LOGGING', 'level', fallback='INFO').upper()
    log_max = config.getint('LOGGING', 'log_max', fallback='5')

    # Define o nível de log inicial
    log_level = getattr(logging, log_level_str, logging.INFO)
    DEBUG_ENABLED = (log_level == logging.DEBUG)

    # Cria diretório de logs se não existir
    import os
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Configura logger
    logger = logging.getLogger('modbus_driver')
    logger.setLevel(log_level)
    logger.handlers.clear()  # Evita duplicação se setup_logger for chamado novamente

    handler = RotatingFileHandler(
        log_file, maxBytes=log_max*1024*1024, backupCount=5, encoding='utf-8'
    )

    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def set_debug(enabled: bool):
    """
    Ativa ou desativa o modo debug em tempo de execução.
    Esse controle será exposto pela API (Node-RED).
    """
    global DEBUG_ENABLED
    logger = logging.getLogger('modbus_driver')
    DEBUG_ENABLED = enabled
    level = logging.DEBUG if enabled else logging.INFO
    logger.setLevel(level)
    logger.info(f"Debug mode {'enabled' if enabled else 'disabled'} via API")


def get_debug_status() -> bool:
    """Retorna o status atual do modo debug."""
    return DEBUG_ENABLED


# Instância global do logger (configurado na importação inicial)
logger = setup_logger()


if __name__ == "__main__":
    # Teste básico de gravação e rotação
    logger.info("Teste: log de informação")
    logger.warning("Teste: log de aviso")
    logger.error("Teste: log de erro")

    print("Log gravado em:", load_config().get('LOGGING', 'log_file'))
