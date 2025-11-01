"""
test_full_driver.py
-------------------
Teste completo do serviço Modbus Driver + API REST.

Fluxo:
1. Testa endpoints principais (/start, /stop, /restart, /debug)
2. Descobre tamanhos reais da memória via /points
3. Testa leitura/escrita via Modbus TCP e via API (/points)
4. Compara valores Modbus ↔ API
5. Verifica conexões e estatísticas
6. Testa comportamento com driver parado
"""

import time
import requests
from pymodbus.client.sync import ModbusTcpClient

API_URL = "http://127.0.0.1:8000"
MODBUS_HOST = "127.0.0.1"
MODBUS_PORT = 5020


# ----------------------------------------------------------------------
# Utilitários
# ----------------------------------------------------------------------
def api_request(method, endpoint):
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


# ----------------------------------------------------------------------
# Testes de API
# ----------------------------------------------------------------------
def test_api_sequence():
    print_section("🔹 Testando API REST")

    print("→ /status")
    print(api_request("GET", "/status"))

    print("\n→ /start")
    print(api_request("POST", "/start"))
    time.sleep(3)

    print("\n→ /debug/on")
    print(api_request("POST", "/debug/on"))

    print("\n→ /restart")
    print(api_request("POST", "/restart"))
    time.sleep(4)

    print("\n→ /status")
    print(api_request("GET", "/status"))


def discover_memory_sizes():
    """Obtém o tamanho de cada área consultando a API."""
    print_section("🔹 Descobrindo tamanhos de memória via API")
    sizes = {}
    for area in ["HR", "CO", "DI", "IR"]:
        try:
            r = requests.get(f"{API_URL}/points?area={area}", timeout=5)
            if r.status_code == 200:
                data = r.json()
                sizes[area] = len(data.get("points", {}))
            else:
                sizes[area] = 0
        except Exception as e:
            print(f"[ERRO] Falha ao ler área {area}: {e}")
            sizes[area] = 0
    print("Tamanhos detectados:", sizes)
    return sizes


# ----------------------------------------------------------------------
# Testes Modbus + API cruzados
# ----------------------------------------------------------------------
def test_modbus_and_api_consistency(sizes):
    """Compara leituras/escritas Modbus vs API."""
    print_section("🔹 Testando coerência Modbus ↔ API")

    client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)
    if not client.connect():
        print("[ERRO] Não foi possível conectar ao Modbus Server.")
        return False

    try:
        hr_n = sizes.get("HR", 1)
        co_n = sizes.get("CO", 1)
        di_n = sizes.get("DI", 1)
        ir_n = sizes.get("IR", 1)

        # --- HR ---
        test_value = 999
        print(f"Escrevendo HR[0]={test_value} via Modbus…")
        client.write_register(0, test_value, unit=1)
        time.sleep(2.5)

        api_val = requests.get(f"{API_URL}/points?address=0&area=HR").json()["value"]
        rr = client.read_holding_registers(0, 1, unit=1)
        modbus_val = rr.registers[0] if not rr.isError() else None
        print(f"→ API: {api_val}, Modbus: {modbus_val}")
        assert api_val == modbus_val, "Valor HR incoerente entre API e Modbus"

        # --- CO ---
        print("Escrevendo CO[0]=1 via API…")
        requests.post(f"{API_URL}/points", json={"area": "CO", "address": 0, "value": 1})
        time.sleep(0.5)
        rr = client.read_coils(0, co_n, unit=1)
        bits = rr.bits[:co_n]
        print(f"→ CO lido via Modbus: {bits}")
        assert bits[0] is True, "CO[0] não refletiu escrita via API"

        # --- DI ---
        rr = client.read_discrete_inputs(0, di_n, unit=1)
        bits = rr.bits[:di_n]
        print(f"→ DI bits (somente leitura): {bits}")

        # --- IR ---
        rr = client.read_input_registers(0, ir_n, unit=1)
        regs = rr.registers if not rr.isError() else []
        print(f"→ IR valores: {regs}")

        print("✅ Coerência API ↔ Modbus confirmada.")
        return True

    except Exception as e:
        print(f"[ERRO CONSISTÊNCIA] {e}")
        return False
    finally:
        client.close()


# ----------------------------------------------------------------------
# Verificações e finalização
# ----------------------------------------------------------------------
def verify_connection_status():
    print_section("🔹 Verificando status do driver após leituras")
    status = api_request("GET", "/status")
    if not status:
        print("❌ Falha ao consultar /status.")
        return False

    conns = status.get("connections", {})
    if not conns:
        print("❌ Nenhuma conexão registrada.")
        return False

    for ip, data in conns.items():
        print(f"→ {ip} | Leituras={data['reads']} | Escritas={data['writes']}")

    print("✅ Conexões e contadores OK.")
    return True


def finalize_driver():
    print_section("🔹 Finalizando teste")
    print("→ /debug/off")
    print(api_request("POST", "/debug/off"))
    print("\n→ /stop")
    print(api_request("POST", "/stop"))
    time.sleep(2)
    print("\n→ /status final")
    print(api_request("GET", "/status"))


def test_api_with_driver_stopped():
    print_section("🔹 Testando acesso à API com driver parado")

    r = requests.get(f"{API_URL}/points?address=0&area=HR")
    print("→ GET /points HR[0] com driver parado:", r.status_code, r.text)

    payload = {"address": 0, "value": 123, "area": "HR"}
    r = requests.post(f"{API_URL}/points", json=payload)
    print("→ POST /points HR[0] com driver parado:", r.status_code, r.text)


# ----------------------------------------------------------------------
# Execução principal
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("=== TESTE COMPLETO DO DRIVER MODBUS ===")

    test_api_sequence()
    time.sleep(5)

    sizes = discover_memory_sizes()
    ok_consistency = test_modbus_and_api_consistency(sizes)
    ok_status = verify_connection_status()

    finalize_driver()
    test_api_with_driver_stopped()

    print_section("🔸 RESULTADO FINAL")
    if ok_consistency and ok_status:
        print("✅ TESTE CONCLUÍDO COM SUCESSO — driver e API coerentes e funcionais.")
    else:
        print("❌ TESTE FALHOU — verifique logs e comportamento do servidor.")
