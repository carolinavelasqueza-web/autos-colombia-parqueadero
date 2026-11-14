from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Puerta


def listar_puertas(session: Session, incluir_inactivas: bool = False) -> list[Puerta]:
    """Devuelve las puertas ordenadas por código; por defecto solo las activas."""
    query = select(Puerta).order_by(Puerta.codigo, Puerta.id)
    if not incluir_inactivas:
        query = query.where(Puerta.activo.is_(True))
    return list(session.scalars(query))
