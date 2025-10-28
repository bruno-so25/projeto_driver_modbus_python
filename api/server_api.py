"""
api/server_api.py
-----------------
API REST do driver Modbus.
Usa FastAPI para comunicação com Node-RED.
"""

from fastapi import FastAPI
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


if __name__ == "__main__":
    logger.info("Iniciando API REST Modbus Driver (porta 8000)...")
    uvicorn.run("api.server_api:app", host="0.0.0.0", port=8000, reload=False)
