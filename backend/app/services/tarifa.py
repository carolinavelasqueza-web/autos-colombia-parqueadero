"""Tarifas mensuales con historial y una sola vigente por tipo."""

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import TIPOS_TARIFA, Operador, Tarifa
from app.schemas.tarifa import TarifaActualizar
from app.services.auditoria import auditar_cambio
from app.services.pago import PagoError


def ahora() -> datetime:
    """Instante de referencia; aislado para pruebas deterministas."""
    return datetime.now(timezone.utc)


def _validar_tipo(tipo: str) -> str:
    if tipo not in TIPOS_TARIFA:
        raise PagoError(422, "Tipo de tarifa no válido.")
    return tipo


def list_tarifas(session: Session) -> list[Tarifa]:
    """Lista las tarifas vigentes, una por tipo."""
    try:
        return list(
            session.scalars(
                select(Tarifa)
                .where(Tarifa.vigente_hasta.is_(None))
                .order_by(Tarifa.tipo)
            )
        )
    except SQLAlchemyError:
        session.rollback()
        raise PagoError(503, "No se pudieron consultar las tarifas.") from None


def tarifa_vigente(
    session: Session, tipo: str, momento: datetime | None = None
) -> Tarifa:
    """Devuelve la tarifa vigente del tipo en el instante indicado."""
    tipo = _validar_tipo(tipo)
    referencia = momento or ahora()
    tarifa = session.scalar(
        select(Tarifa).where(
            Tarifa.tipo == tipo,
            Tarifa.vigente_desde <= referencia,
            or_(
                Tarifa.vigente_hasta.is_(None),
                referencia < Tarifa.vigente_hasta,
            ),
        )
    )
    if tarifa is None:
        raise PagoError(409, f"No hay tarifa vigente para el tipo {tipo}.")
    return tarifa


def actualizar_tarifa(
    session: Session, tipo: str, data: TarifaActualizar, actor: Operador
) -> tuple[Tarifa, bool]:
    """Crea la tarifa del tipo o cierra la vigente y registra una nueva.

    Devuelve la tarifa resultante y si fue creada por primera vez.
    """
    tipo = _validar_tipo(tipo)
    instante = ahora()
    try:
        anterior = session.scalar(
            select(Tarifa)
            .where(Tarifa.tipo == tipo, Tarifa.vigente_hasta.is_(None))
            .with_for_update()
        )
        if anterior is not None:
            anterior.vigente_hasta = instante
            session.flush()

        nueva = Tarifa(
            tipo=tipo,
            valor=data.valor,
            vigente_desde=instante,
            vigente_hasta=None,
        )
        session.add(nueva)
        session.flush()

        auditar_cambio(
            session,
            actor,
            "ACTUALIZAR_TARIFA",
            "tarifa",
            nueva.id,
            anteriores=(
                {"valor": anterior.valor, "vigente_desde": anterior.vigente_desde}
                if anterior is not None
                else None
            ),
            nuevos={
                "valor": nueva.valor,
                "vigente_desde": nueva.vigente_desde,
            },
            contexto={
                "tipo": tipo,
                "accion": "CREAR" if anterior is None else "REEMPLAZAR",
            },
        )
        session.commit()
        return nueva, anterior is None
    except IntegrityError as error:
        session.rollback()
        code = getattr(error.orig, "sqlstate", None)
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        if code == "23505" and constraint == "uq_tarifa_vigente":
            raise PagoError(
                409, "Ya existe una tarifa vigente para ese tipo."
            ) from None
        if code == "23503":
            raise PagoError(
                409, "La operación entra en conflicto con los datos existentes."
            ) from None
        if code in {"23502", "23514"}:
            raise PagoError(
                422, "Los datos incumplen las restricciones de la tarifa."
            ) from None
        raise PagoError(
            409, "La operación entra en conflicto con los datos existentes."
        ) from None
    except SQLAlchemyError:
        session.rollback()
        raise PagoError(
            503, "No se pudo completar la operación con la base de datos."
        ) from None
