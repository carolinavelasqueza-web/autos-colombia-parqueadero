"""Seed idempotente de las 80 celdas predeterminadas."""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.celdas_predeterminadas import CELDAS_PREDETERMINADAS
from app.database import get_engine
from app.models import Celda


def ensure_default_cells(session: Session) -> int:
    """Inserta las celdas base que falten sin sobrescribir las existentes.

    El índice único de ``codigo`` permite que varios procesos de la API
    ejecuten el seed al mismo tiempo sin duplicar filas.
    """
    values = [
        {"codigo": codigo, "tipo": tipo}
        for codigo, tipo in CELDAS_PREDETERMINADAS
    ]
    statement = (
        insert(Celda)
        .values(values)
        .on_conflict_do_nothing(index_elements=[Celda.codigo])
        .returning(Celda.codigo)
    )
    inserted = len(session.execute(statement).scalars().all())
    session.commit()
    return inserted


def seed_default_cells() -> int:
    """Ejecuta el seed con una sesión propia y la cierra al terminar."""
    with Session(get_engine()) as session:
        return ensure_default_cells(session)
