"""
api/server_api.py
-----------------
API REST do driver Modbus.
Usa FastAPI para comunicação com Node-RED.
"""

from fastapi import FastAPI, Query, Body, HTTPException
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import uvicorn
from datetime import datetime
from manager.modbus_driver_manager import ModbusDriverManager
from core.logger import logger

app = FastAPI(title="Modbus Driver API", version="1.0.0")


def get_manager():
    m = getattr(app.state, "manager", None)
    if not m:
        raise HTTPException(status_code=500, detail="Manager não inicializado")
    return m
# # Instância global do gerenciador
# manager = ModbusDriverManager()

@app.get("/status")
def get_status():
    """Retorna o status atual do driver."""
    m = get_manager()
    status = m.get_status()
    return JSONResponse(content=jsonable_encoder(status))

@app.post("/start")
def start_driver():
    """Inicia o driver Modbus."""
    m = get_manager()
    ok = m.start_driver()
    if ok:
        return {"message": "Driver iniciado com sucesso."}
    return JSONResponse(status_code=400, content={"error": "Falha ao iniciar driver."})

@app.post("/stop")
def stop_driver():
    """Para o driver Modbus."""
    m = get_manager()
    ok = m.stop_driver()
    if ok:
        return {"message": "Driver parado com sucesso."}
    return JSONResponse(status_code=400, content={"error": "Falha ao parar driver."})

@app.post("/restart")
def restart_driver():
    """Reinicia o driver Modbus."""
    m = get_manager()
    ok = m.restart_driver()
    if ok:
        return {"message": "Driver reiniciado com sucesso."}
    return JSONResponse(status_code=400, content={"error": "Falha ao reiniciar driver."})

@app.post("/debug/on")
def enable_debug():
    """Ativa modo debug."""
    m = get_manager()
    m.set_debug_mode(True)
    return {"message": "Modo debug ativado."}

@app.post("/debug/off")
def disable_debug():
    """Desativa modo debug."""
    m = get_manager()
    m.set_debug_mode(False)
    return {"message": "Modo debug desativado."}

# --------------------------------------------------------------
# 🔸 Leitura de memória (todas as áreas ou ponto específico)
# --------------------------------------------------------------
@app.get("/points")
def get_points(area: str = Query(default="HR"), address: int = Query(default=None)):
    """
    Lê pontos Modbus da memória interna.
    - area: HR, CO, DI, IR
    - address: opcional; se informado, retorna apenas o ponto.
    """
    m = get_manager()
    if not m.server or not m.server.is_running():
        return JSONResponse(status_code=503, content={"error": "Driver Modbus não está em execução"})
    try:
        if address is not None:
            point = m.memory.read_point(address, area)
            if not point:
                return JSONResponse(status_code=404, content={"error": f"Endereço {address} não encontrado em {area}"})
            return {"area": area, "address": address, **point}
        else:
            points = m.memory.all_points(area)
            return {"area": area, "points": points}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# ----------------------------------------------------------------------
# 🔸 Leitura de memória a partir de um timestamp específico (por área)
# ----------------------------------------------------------------------
def parse_iso8601_local(s: str) -> datetime:
    s = s.strip()
    # se o usuário colocou 'Z' ou offset explícito, respeita
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    dt = datetime.fromisoformat(s)
    # se não tem fuso (usuário digitou hora local), assume fuso do sistema
    if dt.tzinfo is None:
        dt = dt.astimezone()  # converte para datetime local-aware
    return dt

@app.get("/points/changed")
def get_changed_points(
    area: str = Query(default="HR"),
    since: str = Query(..., description="ISO datetime, ex: 2025-11-01T03:00:00Z")
):
    m = get_manager()
    if not m.server or not m.server.is_running():
        return JSONResponse(status_code=503, content={"error": "Driver Modbus não está em execução"})

    try:
        ts = parse_iso8601_local(since)
        changed = m.memory.changed_points(ts, area.upper())

        return { "area": area, "changed": changed }

    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

# --------------------------------------------------------------
# 🔸 Escrita de memória (HR ou CO)
# --------------------------------------------------------------
@app.post("/points")
def set_point(data: dict = Body(...)):
    """
    Escreve um valor na memória (simula escrita Modbus).
    Exemplo corpo JSON:
    {
        "area": "HR",
        "address": 5,
        "value": 123
    }
    """
    m = get_manager()
    if not m.server or not m.server.is_running():
        return JSONResponse(status_code=503, content={"error": "Driver Modbus não está em execução"})
    try:
        area = data.get("area", "HR").upper()
        address = int(data["address"])
        value = int(data["value"])

        # Verifica se o valor de value é positivo/negativo dentro da faixa limite e adequa se necessário
        if value < -32768 or value > 65535:
            return JSONResponse(status_code=400, content={"error": f"O valor está fora do range aceitável."})
        if value < 0:
            value = 65536 + value

        # Atualiza o DataBlock Modbus que consequentemente sincroniza a Memory
        ctx = m.server.context
        if ctx:
            unit_id = m.server.unit_id
            slave = ctx[unit_id] if not ctx.single else ctx
            if area == "HR":
                slave.setValues(3, address, [value])
            elif area == "CO":
                slave.setValues(1, address, [value])
            # IR e DI são somente leitura, não atualizam. Se tentar escrever em IR/DI é levantado um PermissionError na Memory
        
        logger.info(f"API: escrita em {area}[{address}] = {value}")
        return {"status": "OK", "message": f"{area}[{address}] atualizado para {value}"}

    except PermissionError as e:
        return JSONResponse(status_code=403, content={"error": str(e)})
    except KeyError as e:
        return JSONResponse(status_code=400, content={"error": f"Campo ausente: {e}"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    logger.info("Iniciando API REST Modbus Driver (porta 8000)...")
    uvicorn.run("api.server_api:app", host="0.0.0.0", port=8000, reload=False)
