from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Operador
from app.schemas.operador import OperadorActualizar, OperadorCrear, OperadorRespuesta, OperadoresPagina
from app.security import CurrentUser, require_role
from app.services import operador as service

router = APIRouter(prefix="/operadores", tags=["Operadores"])
DatabaseSession = Annotated[Session, Depends(get_session)]
AdminUser = Annotated[Operador, Depends(require_role(["ADMINISTRADOR"]))]
OperatorId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.post("", response_model=OperadorRespuesta, status_code=201)
def create(data: OperadorCrear, session: DatabaseSession, actor: AdminUser) -> Operador:
    return service.create_operator(session, data, actor)


@router.get("", response_model=OperadoresPagina)
def list_all(
    session: DatabaseSession,
    actor: CurrentUser,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    activo: Annotated[bool | None, Query()] = True,
    incluir_inactivos: bool = False,
) -> dict:
    return service.list_operators(session, offset, limit, activo, incluir_inactivos)


@router.get("/{id}", response_model=OperadorRespuesta)
def get_one(id: OperatorId, session: DatabaseSession, actor: CurrentUser) -> Operador:
    return service.get_operator(session, id)


@router.patch("/{id}", response_model=OperadorRespuesta)
def update(id: OperatorId, data: OperadorActualizar, session: DatabaseSession, actor: AdminUser) -> Operador:
    return service.update_operator(session, id, data, actor)


@router.delete("/{id}", status_code=204)
def delete(id: OperatorId, session: DatabaseSession, actor: AdminUser) -> Response:
    service.deactivate_operator(session, id, actor)
    return Response(status_code=204)
