from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Operador
from app.schemas.tarifa import TarifaActualizar, TarifaRespuesta, TipoTarifa
from app.security import CurrentUser, require_role
from app.services import tarifa as service

router = APIRouter(prefix="/tarifas", tags=["Tarifas"])
DatabaseSession = Annotated[Session, Depends(get_session)]
AdminUser = Annotated[Operador, Depends(require_role(["ADMINISTRADOR"]))]


@router.get("", response_model=list[TarifaRespuesta])
def list_all(session: DatabaseSession, actor: CurrentUser):
    return service.list_tarifas(session)


@router.put("/{tipo}", response_model=TarifaRespuesta)
def update(
    tipo: TipoTarifa,
    data: TarifaActualizar,
    session: DatabaseSession,
    actor: AdminUser,
    response: Response,
):
    tarifa, creada = service.actualizar_tarifa(session, tipo, data, actor)
    response.status_code = 201 if creada else 200
    return tarifa
