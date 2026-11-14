"""Reasignación transaccional de la celda de una estancia abierta.

Todo ocurre en una sola transacción: se bloquea la estancia, se valida la celda
nueva, se mueve el vehículo, se registra ``estancia_reasignacion`` y se audita.
Si cualquier paso falla, la sesión se revierte y no queda un estado intermedio.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Celda, Estancia, EstanciaReasignacion, Vehiculo
from app.schemas.celda import CeldaRespuesta
from app.schemas.estancia import (
    EstanciaAbiertaRespuesta,
    EstanciaRespuesta,
    ReasignacionCrear,
    ReasignacionRespuesta,
)
from app.schemas.puerta import PuertaRespuesta
from app.services.auditoria import registrar_auditoria
from app.services.estancia import EstanciaError, transaccion
from app.tipos import MENSAJE_TIPO_INCOMPATIBLE, tipos_compatibles


class ServicioReasignacion:
    def __init__(self, session: Session) -> None:
        self.session = session

    @transaccion
    def reasignar(
        self, estancia_id: int, data: ReasignacionCrear, operador
    ) -> ReasignacionRespuesta:
        estancia = self.session.scalar(
            select(Estancia).where(Estancia.id == estancia_id).with_for_update()
        )
        if estancia is None:
            raise EstanciaError(404, "Estancia no encontrada.")
        if not estancia.esta_abierta():
            raise EstanciaError(409, "Solo se pueden reasignar estancias abiertas.")
        if data.celda_nueva_id == estancia.celda_id:
            raise EstanciaError(409, "La celda nueva debe ser diferente a la actual.")

        nueva = self.session.get(Celda, data.celda_nueva_id)
        if nueva is None:
            raise EstanciaError(404, "Celda no encontrada.")
        if nueva.activo is not True:
            raise EstanciaError(409, "La celda no está disponible.")

        vehiculo = self.session.get(Vehiculo, estancia.vehiculo_id)
        if vehiculo is None:
            raise EstanciaError(404, "Vehículo no encontrado.")
        if not tipos_compatibles(vehiculo.tipo, nueva.tipo):
            raise EstanciaError(400, MENSAJE_TIPO_INCOMPATIBLE)

        ocupada = self.session.scalar(
            select(Estancia.id).where(
                Estancia.celda_id == nueva.id,
                Estancia.salida.is_(None),
                Estancia.id != estancia.id,
            )
        )
        if ocupada is not None:
            raise EstanciaError(409, "La celda está ocupada.")

        anterior = self.session.get(Celda, estancia.celda_id)
        if anterior is None:
            raise EstanciaError(404, "Celda no encontrada.")

        anterior_id = estancia.celda_id
        estancia.celda_id = nueva.id
        self.session.flush()

        registro = EstanciaReasignacion(
            estancia_id=estancia.id,
            celda_anterior_id=anterior_id,
            celda_nueva_id=nueva.id,
            operador_id=operador.id,
            fecha=datetime.now(timezone.utc),
            motivo=data.motivo,
        )
        self.session.add(registro)
        self.session.flush()
        registrar_auditoria(
            self.session,
            operador,
            "REASIGNAR",
            "estancia",
            estancia.id,
            {
                "placa": vehiculo.placa,
                "celda_anterior_id": anterior_id,
                "celda_nueva_id": nueva.id,
                "motivo": data.motivo,
            },
        )

        return ReasignacionRespuesta(
            id=registro.id,
            estancia_id=estancia.id,
            celda_anterior=CeldaRespuesta.model_validate(anterior),
            celda_nueva=CeldaRespuesta.model_validate(nueva),
            operador_id=operador.id,
            fecha=registro.fecha,
            motivo=registro.motivo,
            estancia=EstanciaAbiertaRespuesta(
                **EstanciaRespuesta.model_validate(estancia).model_dump(),
                celda=CeldaRespuesta.model_validate(nueva),
                puerta_entrada=(
                    PuertaRespuesta.model_validate(estancia.puerta_entrada)
                    if estancia.puerta_entrada is not None
                    else None
                ),
            ),
        )
