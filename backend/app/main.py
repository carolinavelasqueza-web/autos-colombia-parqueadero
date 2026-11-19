import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config import ConfigurationError
from app.routers.auth import router as auth_router
from app.routers.vehiculos import router as vehiculos_router
from app.services.auth import AuthError
from app.services.celda_seed import seed_default_cells
from app.services.vehiculo import VehiculoError
from app.routers.celdas import router as celdas_router
from app.services.celda import CeldaError
from app.routers.operadores import router as operadores_router
from app.services.operador import OperadorError
from app.routers.clientes import router as clientes_router
from app.services.cliente import ClienteError
from app.routers.estancias import router as estancias_router
from app.services.estancia import EstanciaError
from app.routers.puertas import router as puertas_router
from app.routers.reportes import router as reportes_router
from app.routers.tarifas import router as tarifas_router
from app.routers.pagos import router as pagos_router
from app.services.pago import PagoError
from app.services.reporte import ReporteError

logger = logging.getLogger(__name__)


def _seed_enabled() -> bool:
    value = os.getenv("CELDAS_SEED_ON_STARTUP", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if _seed_enabled():
        try:
            seed_default_cells()
        except (ConfigurationError, SQLAlchemyError, OSError, ValueError):
            # El seed no debe impedir que /health siga disponible sin PostgreSQL.
            logger.warning(
                "No se pudieron verificar las celdas predeterminadas al iniciar."
            )
    yield


app = FastAPI(title="Autos Colombia API", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(vehiculos_router)
app.include_router(celdas_router)
app.include_router(operadores_router)
app.include_router(clientes_router)
app.include_router(estancias_router)
app.include_router(puertas_router)
app.include_router(reportes_router)
app.include_router(tarifas_router)
app.include_router(pagos_router)


@app.exception_handler(VehiculoError)
@app.exception_handler(CeldaError)
@app.exception_handler(OperadorError)
@app.exception_handler(ClienteError)
@app.exception_handler(EstanciaError)
@app.exception_handler(ReporteError)
@app.exception_handler(PagoError)
async def entity_error_handler(request, error: VehiculoError | CeldaError | OperadorError | ClienteError | EstanciaError | ReporteError | PagoError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"detail": error.detail})


@app.exception_handler(AuthError)
async def auth_error_handler(request, error: AuthError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.detail},
        headers=error.headers,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
