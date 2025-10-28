Instalação do Serviço Systemd – Modbus Driver Python
## 1. Copiar o arquivo do serviço

Copie o arquivo modbus-driver-py.service para o diretório do systemd:
```bash
sudo cp modbus-driver-py.service /etc/systemd/system/
```

## 2. Ajustar parâmetros do serviço
Edite o arquivo copiado com seu editor preferido:

```bash
sudo nano /etc/systemd/system/modbus-driver-py.service
```

Substitua os valores entre < > conforme seu ambiente.

Salve e feche o arquivo.

## 3. Atualizar o daemon do systemd
Após editar o arquivo, recarregue o systemd para aplicar as mudanças:

```bash
sudo systemctl daemon-reload
```

## 4. Habilitar o serviço para iniciar automaticamente

```bash
sudo systemctl enable modbus-driver-py.service
```

## ▶5. Iniciar o serviço

```bash
sudo systemctl start modbus-driver-py.service
```

Verifique o status:

```bash
sudo systemctl status modbus-driver-py.service
```

## 6. Parar ou reiniciar o serviço

```bash
sudo systemctl stop modbus-driver-py.service
sudo systemctl restart modbus-driver-py.service
```

## 7. Visualizar logs

```bash
sudo journalctl -u modbus-driver-py.service -f
```

## 8. Remover o serviço

```bash
sudo systemctl disable modbus-driver-py.service
sudo rm /etc/systemd/system/modbus-driver-py.service
sudo systemctl daemon-reload
```