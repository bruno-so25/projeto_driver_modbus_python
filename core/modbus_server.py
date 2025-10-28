"""
core/modbus_server.py
---------------------
Implementa o servidor Modbus TCP usando a biblioteca pymodbus (v3.11+).

Funções principais:
- Lê parâmetros do settings.ini (host, port, timeout, etc.)
- Usa o objeto Memory como backend dos registradores
- Inicia o servidor Modbus TCP em thread própria
- Registra logs detalhados de inicialização e erros
"""

from threading import Thread
from pymodbus.server import StartTcpServer
from pymodbus.datastore import (
    ModbusServerContext,
    ModbusDeviceContext,
    ModbusSparseDataBlock,
)
try:
    from pymodbus.device import ModbusDeviceIdentification
except ModuleNotFoundError:
    from pymodbus import ModbusDeviceIdentification

from core.config_loader import load_config
from core.memory import Memory
from core.logger import logger, get_debug_status

from datetime import datetime
import inspect


class TracedDataBlock(ModbusSparseDataBlock):
    """
    Extende ModbusSparseDataBlock para interceptar leituras e escritas.
    Quando o modo debug estiver ativo, registra as operações no log.
    """
    def __init__(self, initial_values, parent_server=None):
        super().__init__(initial_values)
        self._server = parent_server

    def _get_client_ip(self):
        """Tenta identificar o IP do cliente que originou a requisição."""
        frame = inspect.currentframe()
        while frame:
            if "request" in frame.f_locals:
                req = frame.f_locals["request"]
                return getattr(req, "client_address", ("unknown", 0))[0]
            frame = frame.f_back
        return "unknown"

    def getValues(self, address, count=1):
        values = super().getValues(address, count)
        if get_debug_status():
            logger.debug(f"Leitura Modbus: addr={address}, count={count}, values={values}")

        client_ip = self._get_client_ip()
        if self._server:
            self._server._update_connection_stats(client_ip, is_write=False)
        
        return values

    def setValues(self, address, values):
        super().setValues(address, values)
        if get_debug_status():
            logger.debug(f"Escrita Modbus: addr={address}, values={values}")

        client_ip = self._get_client_ip()
        if self._server:
            self._server._update_connection_stats(client_ip, is_write=True)


class ModbusServer(Thread):
    """
    Servidor Modbus TCP executado em thread própria.
    Suporta modo debug controlado via API.
    """

    def __init__(self, memory: Memory):
        super().__init__(daemon=True)
        self._memory = memory
        self._running = False

        # Armazena conexões ativas e estatísticas
        self.connections = {}  

        # Configurações
        self.config = load_config()
        self.host = self.config.get("MODBUS", "host", fallback="0.0.0.0")
        self.port = self.config.getint("MODBUS", "port", fallback=5020)
        self.timeout = self.config.getint("MODBUS", "timeout", fallback=5)
        self.unit_id = self.config.getint("MODBUS", "unit_id", fallback=1)

        # Inicialização dos holding registers a partir da Memory
        points = self._memory.all_points()
        initial_values = {addr: self._memory.read_point(addr)["value"] for addr in range(len(points))}
        hr_block = TracedDataBlock(initial_values, parent_server=self)  # usa o bloco com tracer

        di_block = ModbusSparseDataBlock({})
        co_block = ModbusSparseDataBlock({})
        ir_block = ModbusSparseDataBlock({})

        device_ctx = ModbusDeviceContext(di=di_block, co=co_block, hr=hr_block, ir=ir_block)
        self.context = ModbusServerContext(device_ctx, single=True)

    def run(self):
        """Executa o servidor TCP Modbus."""
        self._running = True
        logger.info(f"Iniciando Modbus Server em {self.host}:{self.port}")
        try:
            identity = ModbusDeviceIdentification()
            identity.VendorName = self.config.get("DEVICE", "vendor_name", fallback="Generic Vendor")
            identity.ProductCode = self.config.get("DEVICE", "product_code", fallback="GEN")
            identity.VendorUrl = self.config.get("DEVICE", "vendor_url", fallback="http://localhost")
            identity.ProductName = self.config.get("DEVICE", "product_name", fallback="Modbus Driver")
            identity.MajorMinorRevision = self.config.get("DEVICE", "revision", fallback="1.0.0")

            StartTcpServer(
                context=self.context,
                identity=identity,
                address=(self.host, self.port),
            )
        except Exception as e:
            logger.error(f"Erro no servidor Modbus: {e}")
        finally:
            self._running = False
            logger.info("Servidor Modbus finalizado.")

    def is_running(self) -> bool:
        return self._running

    def _update_connection_stats(self, client_ip: str, is_write: bool = False):
        """Atualiza ou cria estatísticas de conexão por cliente."""
        now = datetime.utcnow()
        if client_ip not in self.connections:
            self.connections[client_ip] = {
                "ip": client_ip,
                "first_seen": now,
                "last_seen": now,
                "reads": 0,
                "writes": 0,
            }
        conn = self.connections[client_ip]
        conn["last_seen"] = now
        if is_write:
            conn["writes"] += 1
        else:
            conn["reads"] += 1


if __name__ == "__main__":
    mem = Memory(num_registers=10, default_value=0)
    server = ModbusServer(memory=mem)
    server.start()
    input("Servidor Modbus em execução. Pressione ENTER para encerrar...\n")
    logger.info("Encerrando servidor Modbus (teste local).")

