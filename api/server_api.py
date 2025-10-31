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

from manager.modbus_driver_manager import ModbusDriverManager
from core.logger import logger

app = FastAPI(title="Modbus Driver API", version="1.0.0")

# Instância global do gerenciador
manager = ModbusDriverManager()

@app.get("/status")
def get_status():
    """Retorna o status atual do driver."""
    status = manager.get_status()
    return JSONResponse(content=jsonable_encoder(status))

@app.post("/start")
def start_driver():
    """Inicia o driver Modbus."""
    ok = manager.start_driver()
    if ok:
        return {"message": "Driver iniciado com sucesso."}
    return JSONResponse(status_code=400, content={"error": "Falha ao iniciar driver."})

@app.post("/stop")
def stop_driver():
    """Para o driver Modbus."""
    ok = manager.stop_driver()
    if ok:
        return {"message": "Driver parado com sucesso."}
    return JSONResponse(status_code=400, content={"error": "Falha ao parar driver."})

@app.post("/restart")
def restart_driver():
    """Reinicia o driver Modbus."""
    ok = manager.restart_driver()
    if ok:
        return {"message": "Driver reiniciado com sucesso."}
    return JSONResponse(status_code=400, content={"error": "Falha ao reiniciar driver."})

@app.post("/debug/on")
def enable_debug():
    """Ativa modo debug."""
    manager.set_debug_mode(True)
    return {"message": "Modo debug ativado."}

@app.post("/debug/off")
def disable_debug():
    """Desativa modo debug."""
    manager.set_debug_mode(False)
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
    if not manager.server or not manager.server.is_running():
        return JSONResponse(status_code=503, content={"error": "Driver Modbus não está em execução"})
    try:
        if address is not None:
            point = manager.memory.read_point(address, area)
            if not point:
                return JSONResponse(status_code=404, content={"error": f"Endereço {address} não encontrado em {area}"})
            return {"area": area, "address": address, **point}
        else:
            points = manager.memory.all_points(area)
            return {"area": area, "points": points}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


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
    if not manager.server or not manager.server.is_running():
        return JSONResponse(status_code=503, content={"error": "Driver Modbus não está em execução"})
    try:
        area = data.get("area", "HR").upper()
        address = int(data["address"])
        value = int(data["value"])

        manager.memory.write_point(address, value, area)
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
