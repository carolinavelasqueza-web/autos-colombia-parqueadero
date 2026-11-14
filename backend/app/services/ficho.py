"""Generación consecutiva y diaria de códigos de ficho.

El formato es ``AC-YYYYMMDD-XXXX`` con la fecha en hora de Bogotá. La unicidad
la garantiza el índice único de ``estancia.ficho_codigo``; este módulo solo
calcula el siguiente consecutivo y la capa de servicio reintenta si otra
transacción se adelanta.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Estancia

BOGOTA = timezone(timedelta(hours=-5), "America/Bogota")
MAX_DIARIOS = 9999


class FichoAgotado(Exception):
    """Se alcanzó el máximo de fichos diarios o no fue posible asignar uno."""


def fecha_bogota(fecha: datetime | None = None) -> datetime:
    momento = fecha or datetime.now(timezone.utc)
    if momento.tzinfo is None or momento.utcoffset() is None:
        raise ValueError("La fecha del ficho debe incluir zona horaria.")
    return momento.astimezone(BOGOTA)


def generar_ficho(session: Session, fecha: datetime | None = None) -> str:
    """Devuelve el siguiente código del día; el INSERT valida la unicidad final."""
    momento = fecha_bogota(fecha)
    prefijo = f"AC-{momento:%Y%m%d}-"
    ultimo = session.scalar(
        select(func.max(Estancia.ficho_codigo)).where(
            Estancia.ficho_codigo.like(f"{prefijo}%")
        )
    )
    consecutivo = 1
    if ultimo:
        try:
            consecutivo = int(ultimo.rsplit("-", 1)[1]) + 1
        except (IndexError, ValueError):
            consecutivo = 1
    if consecutivo > MAX_DIARIOS:
        raise FichoAgotado("Se agotaron los fichos del día.")
    return f"{prefijo}{consecutivo:04d}"
