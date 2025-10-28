Instalação do Serviço Systemd – Modbus Driver Python
##🧩 1. Copiar o arquivo do serviço

Copie o arquivo modbus-driver-py.service para o diretório do systemd:
<pre> ```bash
sudo cp modbus-driver-py.service /etc/systemd/system/
</pre>

##⚙️ 2. Ajustar parâmetros do serviço
Edite o arquivo copiado com seu editor preferido:

<pre> ```bash
sudo nano /etc/systemd/system/modbus-driver-py.service
</pre>

Substitua os valores entre < > conforme seu ambiente.

Salve e feche o arquivo.

##🔄 3. Atualizar o daemon do systemd
Após editar o arquivo, recarregue o systemd para aplicar as mudanças:

<pre> ```bash
sudo systemctl daemon-reload
</pre>

##🚀 4. Habilitar o serviço para iniciar automaticamente

<pre> ```bash
sudo systemctl enable modbus-driver-py.service
</pre>

##▶️ 5. Iniciar o serviço

<pre> ```bash
sudo systemctl start modbus-driver-py.service
</pre>

Verifique o status:

<pre> ```bash
sudo systemctl status modbus-driver-py.service
</pre>

##🛑 6. Parar ou reiniciar o serviço

<pre> ```bash
sudo systemctl stop modbus-driver-py.service
sudo systemctl restart modbus-driver-py.service
</pre>

##📜 7. Visualizar logs

<pre> ```bash
sudo journalctl -u modbus-driver-py.service -f
</pre>

✅ 8. Remover o serviço

<pre> ```bash
sudo systemctl disable modbus-driver-py.service
sudo rm /etc/systemd/system/modbus-driver-py.service
sudo systemctl daemon-reload
</pre>