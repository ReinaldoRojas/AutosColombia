from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.routers.vehiculos import router as vehiculos_router
from app.services.vehiculo import VehiculoError
from app.routers.celdas import router as celdas_router
from app.services.celda import CeldaError
from app.routers.operadores import router as operadores_router
from app.services.operador import OperadorError
from app.routers.estancias import router as estancias_router
from app.services.estancia import EstanciaError
from app.routers.clientes import router as clientes_router
from app.services.cliente import ClienteError
from app.routers.puertas import router as puertas_router

app = FastAPI(title="Autos Colombia API")
app.include_router(vehiculos_router)
app.include_router(celdas_router)
app.include_router(operadores_router)
app.include_router(estancias_router)
app.include_router(clientes_router)
app.include_router(puertas_router)


@app.exception_handler(VehiculoError)
@app.exception_handler(CeldaError)
@app.exception_handler(OperadorError)
@app.exception_handler(EstanciaError)
async def entity_error_handler(request, error: VehiculoError | CeldaError | OperadorError | EstanciaError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"detail": error.detail})


@app.exception_handler(ClienteError)
async def client_error_handler(request, error: ClienteError) -> JSONResponse:
    content: dict = {"detail": error.detail}
    if error.cliente_id is not None:
        content["cliente_id"] = error.cliente_id
    return JSONResponse(status_code=error.status_code, content=content)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
