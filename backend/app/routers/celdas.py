from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Operador
from app.schemas.celda import (
    CeldaActualizar, CeldaCrear, CeldaRespuesta, CeldasPagina, DisponibilidadCeldas,
)
from app.security import CurrentUser, require_role
from app.services import celda as service
from app.services.auth import AuthError

router = APIRouter(prefix="/celdas", tags=["Celdas"])
DatabaseSession = Annotated[Session, Depends(get_session)]
AdminUser = Annotated[Operador, Depends(require_role(["ADMINISTRADOR"]))]
CellId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.post("", response_model=CeldaRespuesta, status_code=201)
def create(data: CeldaCrear, session: DatabaseSession, actor: AdminUser):
    return service.create_cell(session, data, actor)


@router.get("", response_model=CeldasPagina)
def list_all(
    session: DatabaseSession,
    actor: CurrentUser,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    activo: Annotated[bool | None, Query()] = True,
    incluir_inactivas: bool = False,
):
    if incluir_inactivas and actor.rol != "ADMINISTRADOR":
        raise AuthError(403, "No tienes permisos para esta operación.")
    return service.list_cells(session, offset, limit, activo, incluir_inactivas)


@router.get("/disponibilidad", response_model=DisponibilidadCeldas)
def disponibilidad(session: DatabaseSession, actor: CurrentUser):
    return service.disponibilidad(session)


@router.get("/{id}", response_model=CeldaRespuesta)
def get_one(id: CellId, session: DatabaseSession, actor: CurrentUser):
    return service.get_cell(session, id)


@router.patch("/{id}", response_model=CeldaRespuesta)
def update(id: CellId, data: CeldaActualizar, session: DatabaseSession, actor: AdminUser):
    return service.update_cell(session, id, data, actor)


@router.delete("/{id}", status_code=204)
def delete(id: CellId, session: DatabaseSession, actor: AdminUser) -> Response:
    service.delete_cell(session, id, actor)
    return Response(status_code=204)
