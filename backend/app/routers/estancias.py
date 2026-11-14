from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Operador
from app.schemas.estancia import (
    EntradaCrear, EstanciaActualizar, SalidaCrear, EstanciaRespuesta,
    EstanciaAbiertaRespuesta, EstanciasActivasPagina, EstadoVehiculoRespuesta,
    FichoRespuesta, ReasignacionCrear, ReasignacionRespuesta,
)
from app.schemas.vehiculo import Placa
from app.security import require_role
from app.services.estancia import ServicioEstancia
from app.services.reasignacion import ServicioReasignacion

router = APIRouter(prefix="/estancias", tags=["Estancias"])
DatabaseSession = Annotated[Session, Depends(get_session)]
EstanciaUser = Annotated[
    Operador,
    Depends(require_role(["ADMINISTRADOR", "OPERADOR"])),
]
AdminUser = Annotated[
    Operador,
    Depends(require_role(["ADMINISTRADOR"])),
]
EstanciaId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.post("/entrada", response_model=EstanciaAbiertaRespuesta, status_code=201)
def entrada(data: EntradaCrear, session: DatabaseSession, actor: EstanciaUser) -> EstanciaAbiertaRespuesta:
    return ServicioEstancia(session).entrada(data, actor)


@router.post("/salida", response_model=EstanciaRespuesta)
def salida(data: SalidaCrear, session: DatabaseSession, actor: EstanciaUser) -> EstanciaRespuesta:
    return ServicioEstancia(session).salida(data, actor)


@router.get("/vehiculo/{placa}", response_model=EstadoVehiculoRespuesta)
def consultar(placa: Placa, session: DatabaseSession, actor: EstanciaUser) -> EstadoVehiculoRespuesta:
    return ServicioEstancia(session).consultar(placa)


@router.get("/activas", response_model=EstanciasActivasPagina)
def activas(
    session: DatabaseSession,
    actor: EstanciaUser,
    placa: Placa | None = None,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EstanciasActivasPagina:
    return ServicioEstancia(session).listar_activas(placa, offset, limit)


@router.get("/{id}/ficho", response_model=FichoRespuesta)
def ficho(id: EstanciaId, session: DatabaseSession, actor: EstanciaUser) -> FichoRespuesta:
    return ServicioEstancia(session).ficho(id)


@router.post("/{id}/reasignar", response_model=ReasignacionRespuesta)
def reasignar(
    id: EstanciaId,
    data: ReasignacionCrear,
    session: DatabaseSession,
    actor: EstanciaUser,
) -> ReasignacionRespuesta:
    return ServicioReasignacion(session).reasignar(id, data, actor)


@router.patch("/{id}", response_model=EstanciaRespuesta)
def actualizar(
    id: EstanciaId,
    data: EstanciaActualizar,
    session: DatabaseSession,
    actor: AdminUser,
) -> EstanciaRespuesta:
    return ServicioEstancia(session).actualizar(id, data, actor)


@router.delete("/{id}", status_code=204)
def eliminar(id: EstanciaId, session: DatabaseSession, actor: AdminUser) -> Response:
    ServicioEstancia(session).eliminar(id, actor)
    return Response(status_code=204)
