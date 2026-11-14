from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Operador
from app.schemas.reporte import ReporteOcupacionRespuesta
from app.security import require_role
from app.services.reporte import generar_reporte

router = APIRouter(prefix="/reportes", tags=["Reportes"])
DatabaseSession = Annotated[Session, Depends(get_session)]
AdminUser = Annotated[Operador, Depends(require_role(["ADMINISTRADOR"]))]


@router.get("/ocupacion", response_model=ReporteOcupacionRespuesta)
def ocupacion(
    session: DatabaseSession,
    actor: AdminUser,
    desde: Annotated[date | None, Query()] = None,
    hasta: Annotated[date | None, Query()] = None,
) -> ReporteOcupacionRespuesta:
    return generar_reporte(session, desde, hasta)
