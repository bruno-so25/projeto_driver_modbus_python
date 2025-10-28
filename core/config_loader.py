"""
core/config_loader.py
----------------------
Responsável por ler e validar as configurações do arquivo settings.ini.

Este módulo é utilizado em tempo de execução, sempre que o driver for
iniciado ou reiniciado via Node-RED (ou seja, sem necessidade de reiniciar o serviço systemd).

Ele fornece uma interface simples para carregar e acessar configurações
de forma centralizada e consistente em todo o projeto.
"""

import configparser
import os


# Caminho absoluto para o arquivo de configuração
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.ini')


def load_config():
    """
    Lê o arquivo settings.ini e retorna um objeto ConfigParser com as configurações carregadas.

    Essa função é chamada sempre que o driver for inicializado ou reinicializado via API.
    Se o arquivo não existir ou estiver mal formatado, lança exceções específicas.

    Returns:
        configparser.ConfigParser: objeto contendo as configurações carregadas.
    """
    config = configparser.ConfigParser()

    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Arquivo de configuração não encontrado em: {CONFIG_PATH}")

    try:
        config.read(CONFIG_PATH)
    except configparser.Error as e:
        raise ValueError(f"Erro ao ler o arquivo de configuração: {e}")

    return config


def get_config_value(section: str, key: str, default=None):
    """
    Retorna o valor de uma chave específica dentro de uma seção do arquivo settings.ini.

    Args:
        section (str): nome da seção no arquivo ini (ex: 'MODBUS').
        key (str): chave dentro da seção (ex: 'port').
        default (any): valor padrão caso a chave não exista.

    Returns:
        str | any: valor da configuração ou o valor padrão.
    """
    config = load_config()

    if config.has_option(section, key):
        return config.get(section, key)
    else:
        return default


if __name__ == "__main__":
    # Bloco de teste simples (pode ser removido em produção)
    # Útil para verificar rapidamente se o arquivo de configuração está acessível e legível.
    cfg = load_config()
    print("Seções disponíveis:", cfg.sections())

    # Exemplo: obtendo uma configuração da seção MODBUS
    try:
        print("Porta Modbus:", cfg.get('MODBUS', 'port'))
    except Exception as e:
        print("Erro ao acessar a configuração:", e)
