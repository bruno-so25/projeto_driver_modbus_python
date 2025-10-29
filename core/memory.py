"""
core/memory.py
---------------
Responsável por armazenar em memória os pontos Modbus
(holding registers, coils, input registers, etc.).

Os valores são voláteis (RAM). Essa estrutura será acessada
tanto pelo servidor Modbus quanto pela API e pelo Manager.
"""

from datetime import datetime
from enum import Enum
from threading import Lock


class PointQuality(str, Enum):
    """Estado de qualidade do ponto."""
    OK = "OK"          # valor válido
    BAD = "BAD"        # erro ou valor inválido
    STALE = "STALE"    # desatualizado
    UNKNOWN = "UNKNOWN"  # ponto ainda não inicializado


class Memory:
    """
    Armazena todos os pontos Modbus em dicionários.

    Cada ponto:
        {
            "value": int,
            "quality": PointQuality,
            "timestamp": datetime
        }

    O Lock garante segurança em acesso concorrente (threads/API).
    """

    def __init__(self, hr_count: int = 100, co_count: int = 0, di_count: int = 0, ir_count: int = 0, default_value: int = 0,):
        """Inicializa as áreas de memória Modbus."""
        self._lock = Lock()

        def make_block(count):
            return {
                addr: {
                    "value": default_value,
                    "quality": PointQuality.UNKNOWN,
                    "timestamp": datetime.utcnow(),
                }
                for addr in range(count)
            }

        self.holding = make_block(hr_count)          # Holding Registers (R/W)
        self.coils = make_block(co_count)            # Coils (R/W)
        self.discrete_inputs = make_block(di_count)  # Discrete Inputs (R)
        self.input_registers = make_block(ir_count)  # Input Registers (R)

    def _get_table(self, area: str):
        """Seleciona o bloco de memória conforme a área."""
        area = area.upper()
        if area == "HR":
            return self.holding
        elif area == "CO":
            return self.coils
        elif area == "DI":
            return self.discrete_inputs
        elif area == "IR":
            return self.input_registers
        else:
            raise ValueError(f"Área inválida: {area}")
    
    def read_point(self, address: int, area: str = "HR"):
        """Lê um ponto específico de uma área."""
        with self._lock:
            table = self._get_table(area)
            return table.get(address)

    def write_point(self, address: int, value: int, area: str = "HR"):
        """Escreve um valor em uma área (HR/CO)."""
        if area.upper() in ("DI", "IR"):
            raise PermissionError(f"A área {area} é somente leitura.")
        with self._lock:
            table = self._get_table(area)
            if address not in table:
                raise KeyError(f"Endereço inválido: {address}")
            table[address]["value"] = value
            table[address]["quality"] = PointQuality.OK
            table[address]["timestamp"] = datetime.utcnow()

    def set_quality(self, address: int, quality: PointQuality, area: str = "HR"):
        """Altera a qualidade de um ponto."""
        with self._lock:
            table = self._get_table(area)
            if address in table:
                table[address]["quality"] = quality
                table[address]["timestamp"] = datetime.utcnow()

    def all_points(self, area: str = "HR"):
        """Retorna uma cópia dos pontos atuais de uma área."""
        with self._lock:
            table = self._get_table(area)
            return table.copy()

    def changed_points(self, since: datetime, area: str = "HR"):
        """Retorna pontos alterados desde um timestamp."""
        with self._lock:
            table = self._get_table(area)
            return {
                addr: data
                for addr, data in table.items()
                if data["timestamp"] > since
            }


# Teste local
if __name__ == "__main__":
    mem = Memory(hr_count=5, co_count=3, di_count=2, ir_count=2, default_value=0)
    print("Holding Registers:", mem.all_points("HR"))
    print("Coils:", mem.all_points("CO"))
    print("Discrete Inputs:", mem.all_points("DI"))
    print("Input Registers:", mem.all_points("IR"))

    print("\nEscrevendo HR[2] = 123 e CO[1] = 1")
    mem.write_point(2, 123, "HR")
    mem.write_point(1, 1, "CO")

    print("HR[2]:", mem.read_point(2, "HR"))
    print("CO[1]:", mem.read_point(1, "CO"))

    print("\nTentando escrever em DI (deve dar erro):")
    try:
        mem.write_point(0, 1, "DI")
    except Exception as e:
        print("Erro esperado:", e)
