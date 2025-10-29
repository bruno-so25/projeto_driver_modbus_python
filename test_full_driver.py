import time
import requests
from pymodbus.client.sync import ModbusTcpClient

API_URL = "http://127.0.0.1:8000"
MODBUS_HOST = "127.0.0.1"
MODBUS_PORT = 5020


def api_request(method, endpoint):
    """Executa requisições GET/POST simples à API."""
    url = f"{API_URL}{endpoint}"
    try:
        if method == "GET":
            r = requests.get(url, timeout=5)
        else:
            r = requests.post(url, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[ERRO API] {endpoint}: {e}")
        return None


def print_section(title):
    print("\n" + "=" * 80)
    print(f"{title}")
    print("=" * 80)


def test_api_sequence():
    """Testa endpoints principais da API."""
    print_section("🔹 Testando API REST")

    print("→ /status")
    print(api_request("GET", "/status"))

    print("\n→ /start")
    print(api_request("POST", "/start"))
    time.sleep(3)

    print("\n→ /status")
    print(api_request("GET", "/status"))

    print("\n→ /debug/on")
    print(api_request("POST", "/debug/on"))

    print("\n→ /restart")
    print(api_request("POST", "/restart"))
    time.sleep(4)

    print("\n→ /status")
    print(api_request("GET", "/status"))


def test_modbus_client():
    """Simula cliente Modbus e gera tráfego com logs detalhados."""
    print_section("🔹 Testando comunicação Modbus")

    c = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)
    if not c.connect():
        print("[ERRO] Não foi possível conectar ao Modbus Server.")
        return False

    try:
        rr = c.read_holding_registers(0, 5, unit=1)
        print(f"Leitura inicial HR: {rr.registers}")

        c.write_register(0, 321, unit=1)
        rr = c.read_holding_registers(0, 1, unit=1)
        print(f"Leitura após escrita HR[0]: {rr.registers}")

        c.write_coil(0, True, unit=1)
        rr = c.read_coils(0, 4, unit=1)
        print(f"Leitura Coils: {rr.bits}")

        ir = c.read_input_registers(0, 4, unit=1)
        di = c.read_discrete_inputs(0, 4, unit=1)
        print(f"Input Registers: {ir.registers}")
        print(f"Discrete Inputs: {di.bits}")

        return True
    except Exception as e:
        print(f"[ERRO CLIENTE MODBUS] {e}")
        return False
    finally:
        c.close()
        print("Cliente Modbus encerrado.")


def verify_connection_status():
    """Confirma se o IP do cliente foi registrado corretamente."""
    print_section("🔹 Verificando status do driver após leituras")
    status = api_request("GET", "/status")
    if not status:
        print("❌ Falha ao consultar /status.")
        return False

    print(status)
    conns = status.get("connections", {})
    if not conns:
        print("❌ Nenhuma conexão registrada.")
        return False

    total_reads, total_writes = 0, 0
    for ip, data in conns.items():
        r, w = data["reads"], data["writes"]
        print(f"→ {ip} | Leituras={r} | Escritas={w}")
        total_reads += r
        total_writes += w

    # Verifica se houve atividade real
    assert total_reads > 0, "Nenhuma leitura registrada"
    assert total_writes > 0, "Nenhuma escrita registrada"

    print("✅ Conexão e contadores de leitura/escrita OK.")
    return True


def finalize_driver():
    """Desativa debug e encerra o driver."""
    print_section("🔹 Finalizando teste")
    print("→ /debug/off")
    print(api_request("POST", "/debug/off"))
    print("\n→ /stop")
    print(api_request("POST", "/stop"))
    time.sleep(2)
    print("\n→ /status final")
    print(api_request("GET", "/status"))


if __name__ == "__main__":
    print("=== TESTE COMPLETO DO DRIVER MODBUS ===")

    test_api_sequence()

    print("\nAguardando driver iniciar novamente para teste Modbus...")
    time.sleep(5)

    ok_modbus = test_modbus_client()
    time.sleep(2)

    ok_status = verify_connection_status()
    finalize_driver()

    print_section("🔸 RESULTADO FINAL")
    if ok_modbus and ok_status:
        print("✅ TESTE CONCLUÍDO COM SUCESSO — driver e API funcionando corretamente.")
    else:
        print("❌ TESTE FALHOU — verifique logs e comportamento do servidor.")
