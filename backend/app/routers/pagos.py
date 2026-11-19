from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Operador
from app.schemas.pago import (
    EstadoPago,
    PagoAnular,
    PagoCrear,
    PagoRespuesta,
    PagosPagina,
)
from app.security import CurrentUser, require_role
from app.services import pago as service

router = APIRouter(prefix="/pagos", tags=["Pagos"])
DatabaseSession = Annotated[Session, Depends(get_session)]
PagoUser = Annotated[
    Operador,
    Depends(require_role(["ADMINISTRADOR", "OPERADOR"])),
]
AdminUser = Annotated[Operador, Depends(require_role(["ADMINISTRADOR"]))]
PagoId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.post("", response_model=PagoRespuesta, status_code=201)
def create(data: PagoCrear, session: DatabaseSession, actor: CurrentUser):
    return service.registrar_pago(session, data, actor)


@router.get("", response_model=PagosPagina)
def listar(
    session: DatabaseSession,
    actor: PagoUser,
    documento: str | None = None,
    estado: EstadoPago | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PagosPagina:
    items, total = service.obtener_pagos(
        session,
        documento=documento,
        estado=estado,
        desde=desde,
        hasta=hasta,
        offset=offset,
        limit=limit,
    )
    return PagosPagina(items=items, total=total, offset=offset, limit=limit)


@router.get("/{pago_id}/recibo", response_model=PagoRespuesta)
def recibo(pago_id: PagoId, session: DatabaseSession, actor: PagoUser):
    return service.obtener_recibo(session, pago_id)


@router.post("/{pago_id}/anular", response_model=PagoRespuesta)
def anular(
    pago_id: PagoId,
    data: PagoAnular,
    session: DatabaseSession,
    actor: AdminUser,
):
    return service.anular_pago(session, pago_id, data, actor)
