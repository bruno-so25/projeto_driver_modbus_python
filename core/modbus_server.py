"""
core/modbus_server.py
---------------------
Servidor Modbus TCP síncrono usando pymodbus 3.9.0.

Funções:
- Lê configurações do settings.ini
- Mantém registradores em memória via classe Memory
- Loga leituras, escritas e conexões
- Expõe estatísticas de clientes (IP, leituras, escritas, tempo de conexão)
"""

from threading import Thread
from datetime import datetime
from pymodbus.server.sync import ModbusTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import (
    ModbusServerContext,
    ModbusSlaveContext,
    ModbusSequentialDataBlock,
)
try:
    from pymodbus.device import ModbusDeviceIdentification
except ModuleNotFoundError:
    from pymodbus import ModbusDeviceIdentification

from core.config_loader import load_config
from core.memory import Memory
from core.logger import logger, get_debug_status
import socketserver


# ----------------------------------------------------------------------
# DataBlocks com rastreamento por área (HR/IR = 16-bit; CO/DI = bit/0-1)
# ----------------------------------------------------------------------
class TracedSeqBlock(ModbusSequentialDataBlock):
    """HR/IR: 16-bit words."""
    def __init__(self, address, values, parent_server=None, area="HR"):
        super().__init__(address, values)
        self._server = parent_server
        self._area = area  # "HR" ou "IR"

    def getValues(self, address, count=1):
        values = super().getValues(address, count)
        if get_debug_status():
            logger.debug(f"[{self._area}] READ addr={address}, count={count}, values={values}")
        if self._server:
            self._server._update_connection_stats("unknown", is_write=False)
        return values

    def setValues(self, address, values):
        # IR é somente leitura por definição; ignore se alguém tentar escrever
        if self._area == "IR":
            if get_debug_status():
                logger.debug(f"[{self._area}] WRITE IGNORED addr={address}, values={values}")
            return

        # --- NOVO BLOCO: sincroniza com Memory central ---
        if self._server and hasattr(self._server, "_memory"):
            #base = getattr(self, "address", 0)
            for i, v in enumerate(values):
                try:
                    abs_addr = address + i - 1
                    self._server._memory.write_point(abs_addr, v, self._area)
                except Exception as e:
                    logger.debug(f"Falha ao sincronizar {self._area}[{address+i}] -> {e}")
        
        super().setValues(address, values)

        if get_debug_status():
            logger.debug(f"[{self._area}] WRITE addr={address}, values={values}")

        if self._server:
            self._server._update_connection_stats("unknown", is_write=True)


class TracedBitBlock(ModbusSequentialDataBlock):
    """CO/DI: bits 0/1 representados como inteiros 0/1."""
    def __init__(self, address, values, parent_server=None, area="CO"):
        super().__init__(address, values)
        self._server = parent_server
        self._area = area  # "CO" ou "DI"

    def getValues(self, address, count=1):
        values = super().getValues(address, count)
        if get_debug_status():
            logger.debug(f"[{self._area}] READ addr={address}, count={count}, values={values}")
        if self._server:
            self._server._update_connection_stats("unknown", is_write=False)
        return values

    def setValues(self, address, values):
        # DI é somente leitura; ignore escrita
        if self._area == "DI":
            if get_debug_status():
                logger.debug(f"[{self._area}] WRITE IGNORED addr={address}, values={values}")
            return

        # normaliza para 0/1
        norm = [1 if int(v) else 0 for v in values]
        
        # --- NOVO BLOCO: sincroniza com Memory central ---
        if self._server and hasattr(self._server, "_memory"):
            #base = getattr(self, "address", 0)
            for i, v in enumerate(norm):
                try:
                    abs_addr = address + i - 1
                    self._server._memory.write_point(abs_addr, v, self._area)
                except Exception as e:
                    logger.debug(f"Falha ao sincronizar {self._area}[{address+i}] -> {e}")

        super().setValues(address, norm)

        if get_debug_status():
            logger.debug(f"[{self._area}] WRITE addr={address}, values={norm}")

        if self._server:
            self._server._update_connection_stats("unknown", is_write=True)


# ----------------------------------------------------------------------
# Subclasse do servidor Modbus que captura IPs dos clientes
# ----------------------------------------------------------------------
class TrackedModbusTcpServer(ModbusTcpServer):
    """Intercepta requisições e registra o IP do cliente conectado."""
    def __init__(self, *args, parent_server=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._parent_server = parent_server

    def process_request(self, request, client_address):
        """Captura o IP do cliente a cada requisição Modbus."""
        if self._parent_server and client_address:
            ip = client_address[0] if isinstance(client_address, tuple) else str(client_address)
            self._parent_server._register_client_connection(ip)
        return super().process_request(request, client_address)



# ---------------------------------------------------------------------------
# SubClasse de ModbusTcpServer com SO_REUSEADDR ativo.
# Permite reutilizar endereço após ele ser fechado, sem esperar o TIME_WAIT
# ---------------------------------------------------------------------------
class ReusableModbusTcpServer(ModbusTcpServer):
    def server_bind(self):
        self.socket.setsockopt(socketserver.socket.SOL_SOCKET, socketserver.socket.SO_REUSEADDR, 1)
        super().server_bind()

# ----------------------------------------------------------------------
# Classe principal do servidor Modbus
# ----------------------------------------------------------------------
class ModbusServer(Thread):
    """Servidor Modbus TCP executado em thread própria."""

    def __init__(self, memory: Memory):
        super().__init__(daemon=True)

        self._startup_error = None   # armazena exceção de inicialização

        self._memory = memory
        self._server_instance = None
        self._running = False
        self.connections = {}

        # Lê as configurações em config/settings.ini
        self.config = load_config()
        self.host = self.config.get("MODBUS", "host", fallback="0.0.0.0")
        self.port = self.config.getint("MODBUS", "port", fallback=5020)
        self.timeout = self.config.getint("MODBUS", "timeout", fallback=5)
        self.unit_id = self.config.getint("MODBUS", "unit_id", fallback=1)

        # ------------------------------------------------------------
        # Inicializa blocos a partir da memória compartilhada (Memory)
        # ------------------------------------------------------------

        # Blocos com tracer por área, carregando diretamente da Memory correta
        hr_values = [v["value"] for v in self._memory.all_points("HR").values()]
        ir_values = [v["value"] for v in self._memory.all_points("IR").values()]
        co_values = [v["value"] for v in self._memory.all_points("CO").values()]
        di_values = [v["value"] for v in self._memory.all_points("DI").values()]

        # Evita blocos vazios
        hr_values = hr_values or [0]
        ir_values = ir_values or [0]
        co_values = co_values or [0]
        di_values = di_values or [0]

        # Blocos com tracer por área
        hr_block = TracedSeqBlock(1, hr_values, parent_server=self, area="HR")
        ir_block = TracedSeqBlock(1, ir_values, parent_server=self, area="IR")
        co_block = TracedBitBlock(1, co_values, parent_server=self, area="CO")
        di_block = TracedBitBlock(1, di_values, parent_server=self, area="DI")

        slave = ModbusSlaveContext(di=di_block, co=co_block, hr=hr_block, ir=ir_block)
        self.context = ModbusServerContext(slaves={self.unit_id: slave}, single=False)
        logger.info(f"Servidor Modbus configurado com Unit ID = {self.unit_id}")

    # ------------------------------------------------------------------

    def run(self):
        """Executa o servidor TCP Modbus (modo síncrono, pymodbus 2.5.3)."""
        try:
            identity = ModbusDeviceIdentification()
            identity.VendorName = self.config.get("DEVICE", "vendor_name", fallback="Generic Vendor")
            identity.ProductCode = self.config.get("DEVICE", "product_code", fallback="GEN")
            identity.VendorUrl = self.config.get("DEVICE", "vendor_url", fallback="http://localhost")
            identity.ProductName = self.config.get("DEVICE", "product_name", fallback="Modbus Driver")
            identity.MajorMinorRevision = self.config.get("DEVICE", "revision", fallback="1.0.0")

            self._server_instance = ReusableModbusTcpServer(
                context=self.context,
                identity=identity,
                address=(self.host, self.port),
            )
            
            # Só muda pra True após conseguir instanciar o ModbusTcpServer
            self._running = True
            logger.info(f"Modbus Server iniciado em {self.host}:{self.port}")

            self._server_instance.serve_forever()
        except Exception as e:
            self._startup_error = e   # <-- sinaliza erro
            logger.error(f"Erro no servidor Modbus: {e}")
        finally:
            self._running = False
            logger.info("Servidor Modbus finalizado.")

    # ------------------------------------------------------------------
    def shutdown(self):
        """Encerra o servidor TCP Modbus."""
        if self._server_instance:
            try:
                logger.info("Encerrando Modbus TCP.")
                self._server_instance.shutdown()
                self._server_instance.server_close()
            except Exception as e:
                logger.error(f"Erro ao encerrar servidor Modbus: {e}")
        self._running = False

    # ------------------------------------------------------------------
    def is_running(self):
        """Retorna se o servidor está ativo."""
        return self._running

    # ------------------------------------------------------------------
    def _register_client_connection(self, client_ip: str):
        """Registra novo cliente conectado."""
        now = datetime.now().astimezone()
        if client_ip not in self.connections:
            self.connections[client_ip] = {
                "ip": client_ip,
                "first_seen": now,
                "last_seen": now,
                "reads": 0,
                "writes": 0,
            }

    # ------------------------------------------------------------------
    def _update_connection_stats(self, client_ip: str, is_write: bool = False):
        """Atualiza estatísticas de leitura/escrita."""
        now = datetime.now().astimezone()
        if client_ip not in self.connections:
            self._register_client_connection(client_ip)
        conn = self.connections[client_ip]
        conn["last_seen"] = now
        if is_write:
            conn["writes"] += 1
        else:
            conn["reads"] += 1


# ----------------------------------------------------------------------
# Execução direta (teste isolado)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    mem = Memory(hr_count=10, co_count=5, di_count=5, ir_count=5, default_value=0)
    server = ModbusServer(memory=mem)
    server.start()
    input("Servidor Modbus em execução. Pressione ENTER para encerrar...\n")
    server.shutdown()
    logger.info("Encerrando servidor Modbus (teste local).")
