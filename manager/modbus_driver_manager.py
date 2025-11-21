"""
manager/modbus_driver_manager.py
--------------------------------
Gerencia o ciclo de vida do servidor Modbus.
Controla start, stop, restart, status e watchdog automático.
"""

import threading
import time
from datetime import datetime
from core.memory import Memory
from core.logger import logger, set_debug, get_debug_status
from core.modbus_server import ModbusServer
from core.config_loader import load_config


class ModbusDriverManager:
    """
    Classe de gerenciamento do driver Modbus.
    Mantém o servidor, estatísticas e watchdog.
    """

    def __init__(self):
        self.server = None
        self.start_time = None
        self._lock = threading.Lock()
        self.stats = {"starts": 0, "stops": 0, "errors": 0}
        self._watchdog_active = False
        self._watchdog_thread = None

    # ----------------------------------------------------------------------
    # Controle principal
    # ----------------------------------------------------------------------
    def start_driver(self):
        """Inicia o servidor Modbus."""
        with self._lock:
            if self.server and self.server.is_running():
                logger.warning("Tentativa de iniciar driver já em execução.")
                return False
            
            #Lê as configurações do arquivo settings.ini
            self.cfg = load_config()

            # --- Parâmetros de memória ---
            hr_count = self.cfg.getint("MEMORY", "hr_count", fallback=100)
            co_count = self.cfg.getint("MEMORY", "coil_count", fallback=0)
            di_count = self.cfg.getint("MEMORY", "di_count", fallback=0)
            ir_count = self.cfg.getint("MEMORY", "ir_count", fallback=0)
            def_val = self.cfg.getint("MEMORY", "default_value", fallback=0)

            self.memory = Memory(
                hr_count=hr_count,
                co_count=co_count,
                di_count=di_count,
                ir_count=ir_count,
                default_value=def_val,
            )

            # Configuração do watchdog
            self._watchdog_interval = self.cfg.getint("WATCHDOG", "interval_seconds", fallback=10)
            self._watchdog_enabled = self.cfg.getboolean("WATCHDOG", "enabled", fallback=True)
            self._manual_stop = False
            self._watchdog_max_retries = self.cfg.getint("WATCHDOG", "max_retries", fallback=5)

            try:
                logger.info("Iniciando Servidor Modbus.")
                self.server = ModbusServer(memory=self.memory)
                self.server.start()

                # --- Aguarda inicialização da thread ---
                import time
                timeout = time.time() + 3  # até 3 segundos
                while time.time() < timeout:
                    if self.server._startup_error:
                        break
                    if self.server.is_running():
                        break
                    time.sleep(0.1)

                # --- Avalia resultado ---
                if self.server._startup_error:
                    err = self.server._startup_error
                    self.stats["errors"] += 1
                    self.server.shutdown()
                    self.server = None
                    return False

                if not self.server.is_running():
                    self.stats["errors"] += 1
                    logger.error("Servidor Modbus não iniciou dentro do tempo limite. Encerrando thread por segurança.")
                    try:
                        self.server.shutdown()
                    except Exception as e:
                        logger.debug(f"Falha ao encerrar servidor após timeout: {e}")
                    self.server = None
                    return False

                # --- Sucesso ---
                self.start_time = datetime.now().astimezone()
                self.stats["starts"] += 1
                logger.info("Driver Modbus iniciado com sucesso.")
                if self._watchdog_enabled:
                    self._start_watchdog()
                    logger.info("Serviço watchdog iniciado com sucesso.")
                return True

            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"Erro ao iniciar driver: {e}")
                return False

    def stop_driver(self):
        """Para o servidor Modbus."""
        with self._lock:
            if not self.server or not self.server.is_running():
                logger.warning("Tentativa de parar driver que não está em execução.")
                return False

            # Força encerramento da thread do servidor (método indireto)
            try:
                logger.info("Solicitando parada do servidor Modbus.")
                self._manual_stop = True
                self.server.shutdown()  # encerra socket e loop TCP
                self.stats["stops"] += 1
                logger.info("Driver Modbus parado manualmente (API ou terminal).")
                return True

            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"Erro ao parar driver: {e}")
                return False

    def restart_driver(self):
        """Reinicia o servidor."""
        logger.info("Reiniciando driver Modbus.")
        self.stop_driver()
        time.sleep(2)
        self._manual_stop = False
        return self.start_driver()

    # ----------------------------------------------------------------------
    # Watchdog
    # ----------------------------------------------------------------------
    def _start_watchdog(self):
        """Inicia o watchdog em thread separada."""
        if self._watchdog_active:
            return
        self._watchdog_retry_count = 0
        self._watchdog_active = True
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()
        logger.debug("Watchdog iniciado.")

    def _watchdog_loop(self):
        while self._watchdog_active:
            try:
                time.sleep(self._watchdog_interval)
                restart_needed = False
                #logger.debug(f"Watchdog: \ndriver_running({self.server and self.server.is_running()})\nself._watchdog_retry_count({self._watchdog_retry_count})\nself._manual_stop({self._manual_stop})\nrestart_needed({restart_needed})\n\n")

                with self._lock:
                    driver_running = self.server and self.server.is_running()

                    if driver_running:
                        if self._watchdog_retry_count > 0:
                            logger.info("Watchdog: servidor voltou ao normal, zerando contador.")
                        self._watchdog_retry_count = 0
                        continue

                    if self._manual_stop:
                        logger.debug("Watchdog: parada manual detectada. Ignorando.")
                        continue

                    if self._watchdog_max_retries > 0 and \
                    self._watchdog_retry_count >= self._watchdog_max_retries:
                        logger.error(
                            f"Watchdog atingiu o limite de {self._watchdog_max_retries} tentativas. "
                            "Monitoramento encerrado."
                        )
                        self._watchdog_active = False
                        break

                    self._watchdog_retry_count += 1
                    logger.warning(
                        f"Watchdog detectou falha. Tentativa #{self._watchdog_retry_count} "
                        f"de reiniciar o driver."
                    )
                    restart_needed = True

            except Exception as e:
                logger.error(f"ERRO CRÍTICO DENTRO DO WATCHDOG: {e}")

            if restart_needed:
                try:
                    self.restart_driver()
                except Exception as e:
                    logger.error(f"Watchdog falhou ao reiniciar driver: {e}")


    # ----------------------------------------------------------------------
    # Status e debug
    # ----------------------------------------------------------------------
    def get_status(self):
        """Retorna o status atual do driver."""
        uptime = None
        if self.start_time:
            uptime = str(datetime.now().astimezone() - self.start_time).split(".")[0]

        connections = self.server.connections if self.server else {}
        status = {
            "running": self.server.is_running() if self.server else False,
            "uptime": uptime,
            "debug": get_debug_status(),
            "stats": self.stats,
            "connections": connections,
        }
        return status

    def set_debug_mode(self, enable: bool):
        """Ativa ou desativa modo debug."""
        set_debug(enable)
        logger.info(f"Modo debug {'ativado' if enable else 'desativado'}.")
        return get_debug_status()


# ----------------------------------------------------------------------
# Teste local manual
# ----------------------------------------------------------------------
if __name__ == "__main__":
    manager = ModbusDriverManager()
    print("Iniciando driver...")
    manager.start_driver()

    print("Driver em execução. Aguarde alguns segundos ou pressione Ctrl+C para parar.")
    time.sleep(5)

    print("\nStatus atual:")
    print(manager.get_status())

    print("\nParando driver...")
    manager.stop_driver()
    print("Status final:")
    print(manager.get_status())
