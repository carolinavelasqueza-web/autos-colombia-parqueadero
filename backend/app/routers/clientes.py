from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Operador
from app.schemas.cliente import (
    ClienteActualizar,
    ClienteCrear,
    ClienteRespuesta,
    ClientesMensualidadPagina,
    ClientesPagina,
    MensualidadRespuesta,
)
from app.security import CurrentUser, require_role
from app.services import cliente as service

router = APIRouter(prefix="/clientes", tags=["Clientes"])
DatabaseSession = Annotated[Session, Depends(get_session)]

# Permite acceso tanto a ADMINISTRADOR como a OPERADOR para registrar y actualizar clientes
OperadorOrAdminUser = Annotated[Operador, Depends(require_role(["ADMINISTRADOR", "OPERADOR"]))]

# Solo ADMINISTRADOR se mantiene para la eliminación (delete)
AdminUser = Annotated[Operador, Depends(require_role(["ADMINISTRADOR"]))]

ClienteId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.post("", response_model=ClienteRespuesta, status_code=201)
def create(data: ClienteCrear, session: DatabaseSession, actor: OperadorOrAdminUser):
    return service.create_cliente(session, data, actor)


@router.get("", response_model=ClientesPagina)
def list_all(
    session: DatabaseSession,
    actor: CurrentUser,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    activo: Annotated[bool | None, Query()] = None,
):
    return service.list_clientes(session, offset, limit, activo)


@router.get("/mensualidad/alertas", response_model=ClientesMensualidadPagina)
def alertas(
    session: DatabaseSession,
    actor: CurrentUser,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return service.listar_alertas(session, offset, limit)


@router.get("/{id}/mensualidad", response_model=MensualidadRespuesta)
def mensualidad(id: ClienteId, session: DatabaseSession, actor: CurrentUser):
    return service.get_mensualidad(session, id)


@router.get("/{id}", response_model=ClienteRespuesta)
def get_one(id: ClienteId, session: DatabaseSession, actor: CurrentUser):
    return service.get_cliente(session, id)


@router.patch("/{id}", response_model=ClienteRespuesta)
def update(
    id: ClienteId,
    data: ClienteActualizar,
    session: DatabaseSession,
    actor: OperadorOrAdminUser,
):
    return service.update_cliente(session, id, data, actor)


@router.delete("/{id}", status_code=204)
def delete(id: ClienteId, session: DatabaseSession, actor: AdminUser) -> Response:
    service.delete_cliente(session, id, actor)
    return Response(status_code=204)