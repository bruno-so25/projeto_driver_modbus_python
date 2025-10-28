# Projeto Modbus Driver

## Visão geral
O projeto implementa um **driver Modbus TCP** em Python, com gerenciamento via **API REST** e controle externo pelo **Node-RED**.  
Toda a configuração é carregada de arquivo texto (`settings.ini`), e o sistema grava logs detalhados de eventos e leituras.  
O serviço é executado no Ubuntu, isolado em ambiente virtual e gerenciado pelo **systemd**.

---

## Estrutura de diretórios

```
projeto_modbus_driver/
├── env/ # Ambiente virtual Python
├── config/
│ └── settings.ini # Configurações gerais do driver
├── core/
│ ├── modbus_server.py # Servidor Modbus TCP
│ ├── memory.py # Armazenamento dos pontos em memória
│ ├── config_loader.py # Leitura do arquivo settings.ini
│ └── logger.py # Configuração de logs e modo debug
├── manager/
│ └── modbus_driver_manager.py # Controla start/stop/restart do servidor
├── api/
│ └── server_api.py # API REST para integração com Node-RED
├── logs/
│ └── driver.log # Log de operação e debug
├── main.py # Ponto de entrada principal do serviço
├── requirements.txt # Dependências do projeto
└── ARCHITECTURE.md # Descrição e documentação do projeto
```