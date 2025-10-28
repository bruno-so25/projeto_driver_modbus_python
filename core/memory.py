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

    def __init__(self, num_registers: int = 100, default_value: int = 0):
        self._lock = Lock()
        self._points = {
            addr: {
                "value": default_value,
                "quality": PointQuality.UNKNOWN,
                "timestamp": datetime.utcnow()
            }
            for addr in range(num_registers)
        }

    def read_point(self, address: int):
        """Lê um ponto específico."""
        with self._lock:
            return self._points.get(address)

    def write_point(self, address: int, value: int):
        """Escreve um valor em um ponto e atualiza qualidade e timestamp."""
        with self._lock:
            if address not in self._points:
                raise KeyError(f"Endereço inválido: {address}")

            self._points[address]["value"] = value
            self._points[address]["quality"] = PointQuality.OK
            self._points[address]["timestamp"] = datetime.utcnow()

    def set_quality(self, address: int, quality: PointQuality):
        """Altera apenas a qualidade de um ponto."""
        with self._lock:
            if address in self._points:
                self._points[address]["quality"] = quality
                self._points[address]["timestamp"] = datetime.utcnow()

    def all_points(self):
        """Retorna uma cópia dos pontos atuais."""
        with self._lock:
            return self._points.copy()

    def changed_points(self, since: datetime):
        """Retorna pontos alterados desde um timestamp."""
        with self._lock:
            return {
                addr: data
                for addr, data in self._points.items()
                if data["timestamp"] > since
            }


# Teste local
if __name__ == "__main__":
    mem = Memory(num_registers=5, default_value=0)
    print("Estado inicial:")
    print(mem.all_points())

    print("\nEscrevendo endereço 2 = 123")
    mem.write_point(2, 123)

    print("Leitura ponto 2:", mem.read_point(2))

    p = mem.read_point(2)
    p["quality"] = p["quality"].value
    print("Opção em texto: Leitura ponto 2:", p)

    print("\nAlterando qualidade do ponto 2 para BAD")
    mem.set_quality(2, PointQuality.BAD)

    print("Leitura ponto 2:", mem.read_point(2))
