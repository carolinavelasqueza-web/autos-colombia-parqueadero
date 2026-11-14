from functools import wraps

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.celdas_predeterminadas import CODIGOS_CELDAS_PREDETERMINADAS
from app.models import Celda, Estancia, Operador
from app.schemas.celda import CeldaActualizar, CeldaCrear
from app.services.auditoria import auditar, registrar_auditoria
from app.tipos import normalizar_tipo, tipos_compatibles

CAMPOS_AUDITADOS = ("codigo", "tipo", "activo")


class CeldaError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def database_operation(operation=None, *, commit: bool = False):
    """Centraliza rollback, mensajes públicos y el commit de escrituras."""

    def decorar(op):
        @wraps(op)
        def wrapped(session: Session, *args, **kwargs):
            try:
                result = op(session, *args, **kwargs)
                if commit:
                    session.commit()
                return result
            except IntegrityError as error:
                session.rollback()
                code = getattr(error.orig, "sqlstate", None)
                constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
                if code == "23505" and constraint == "uq_celda_codigo":
                    raise CeldaError(409, "Ya existe una celda con ese código.") from None
                if code == "23503":
                    raise CeldaError(409, "La celda tiene registros relacionados y no se puede eliminar.") from None
                if code in {"23502", "23514"}:
                    raise CeldaError(422, "Los datos incumplen las restricciones de la celda.") from None
                raise CeldaError(409, "La operación entra en conflicto con los datos existentes.") from None
            except SQLAlchemyError:
                session.rollback()
                raise CeldaError(503, "No se pudo completar la operación con la base de datos.") from None

        return wrapped

    return decorar(operation) if operation is not None else decorar


def find_cell(session: Session, cell_id: int) -> Celda:
    cell = session.get(Celda, cell_id)
    if cell is None:
        raise CeldaError(404, "Celda no encontrada.")
    return cell


def _has_estancias(session: Session, cell_id: int) -> bool:
    return bool(
        session.scalar(select(exists().where(Estancia.celda_id == cell_id)))
    )


def celdas_libres_para(session: Session, tipo_vehiculo: str) -> list[Celda]:
    """Celdas activas sin estancia abierta compatibles con la familia del vehículo."""
    rows = session.scalars(
        select(Celda)
        .outerjoin(
            Estancia,
            (Estancia.celda_id == Celda.id) & Estancia.salida.is_(None),
        )
        .where(Celda.activo.is_(True), Estancia.id.is_(None))
        .order_by(Celda.id)
    ).all()
    return [celda for celda in rows if tipos_compatibles(tipo_vehiculo, celda.tipo)]


def _deactivate(session: Session, cell: Celda, actor: Operador, motivo: str) -> None:
    if cell.activo is False:
        return
    cell.activo = False
    registrar_auditoria(
        session,
        actor,
        "DESACTIVAR",
        "celda",
        cell.id,
        {"activo_anterior": True, "activo_nuevo": False, "motivo": motivo},
    )


@database_operation(commit=True)
@auditar(
    accion="CREAR",
    entidad="celda",
    modelo=Celda,
    campos=CAMPOS_AUDITADOS,
)
def create_cell(session: Session, data: CeldaCrear, actor: Operador) -> Celda:
    cell = Celda(**data.model_dump())
    session.add(cell)
    session.flush()
    return cell


@database_operation
def list_cells(
    session: Session,
    offset: int,
    limit: int,
    activo: bool | None = True,
    incluir_inactivas: bool = False,
) -> dict:
    query = select(Celda)
    count_query = select(func.count()).select_from(Celda)
    if not incluir_inactivas and activo is not None:
        query = query.where(Celda.activo == activo)
        count_query = count_query.where(Celda.activo == activo)
    total = session.scalar(count_query)
    items = list(session.scalars(query.order_by(Celda.id).offset(offset).limit(limit)))
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@database_operation
def get_cell(session: Session, cell_id: int) -> Celda:
    return find_cell(session, cell_id)


@database_operation
def disponibilidad(session: Session) -> dict:
    """Resume las celdas activas y su ocupación real en una sola consulta."""
    rows = session.execute(
        select(Celda, Estancia.id)
        .outerjoin(Estancia, (Estancia.celda_id == Celda.id) & Estancia.salida.is_(None))
        .where(Celda.activo.is_(True))
        .order_by(Celda.tipo, Celda.codigo, Celda.id)
    ).all()

    celdas: list[dict] = []
    resumen: dict[str, dict] = {}
    for celda, estancia_abierta_id in rows:
        disponible = estancia_abierta_id is None
        celdas.append(
            {
                "id": celda.id,
                "codigo": celda.codigo,
                "tipo": celda.tipo,
                "disponible": disponible,
            }
        )
        grupo = resumen.setdefault(
            normalizar_tipo(celda.tipo),
            {"tipo": celda.tipo, "total": 0, "disponibles": 0, "ocupadas": 0},
        )
        grupo["total"] += 1
        grupo["disponibles" if disponible else "ocupadas"] += 1

    total = len(celdas)
    disponibles = sum(1 for celda in celdas if celda["disponible"])
    ocupadas = total - disponibles
    return {
        "total": total,
        "disponibles": disponibles,
        "ocupadas": ocupadas,
        "ocupacion_porcentaje": round(ocupadas * 100 / total, 1) if total else 0.0,
        "por_tipo": [resumen[clave] for clave in sorted(resumen)],
        "celdas": celdas,
    }


@database_operation(commit=True)
@auditar(
    accion="ACTUALIZAR",
    entidad="celda",
    id_arg="cell_id",
    modelo=Celda,
    campos=CAMPOS_AUDITADOS,
)
def update_cell(session: Session, cell_id: int, data: CeldaActualizar, actor: Operador) -> Celda:
    cell = find_cell(session, cell_id)
    changes = data.model_dump(exclude_unset=True)
    if (
        cell.codigo in CODIGOS_CELDAS_PREDETERMINADAS
        and "codigo" in changes
        and changes["codigo"] != cell.codigo
    ):
        raise CeldaError(
            409,
            "No se puede cambiar el código de una celda predeterminada.",
        )
    changed = []
    for key, value in changes.items():
        if getattr(cell, key) != value:
            setattr(cell, key, value)
            changed.append(key)
    if changed:
        session.flush()
    return cell


@database_operation
def delete_cell(session: Session, cell_id: int, actor: Operador) -> None:
    cell = find_cell(session, cell_id)
    if cell.activo is False:
        return

    if cell.codigo in CODIGOS_CELDAS_PREDETERMINADAS:
        _deactivate(session, cell, actor, "predeterminada")
        session.commit()
        return

    if _has_estancias(session, cell.id):
        _deactivate(session, cell, actor, "con_estancias")
        session.commit()
        return

    try:
        with session.begin_nested():
            session.delete(cell)
            session.flush()
    except IntegrityError as error:
        code = getattr(error.orig, "sqlstate", None)
        if code != "23503":
            raise
        # Una estancia se creó entre la comprobación y el borrado físico.
        cell = find_cell(session, cell_id)
        _deactivate(session, cell, actor, "con_estancias")
        session.commit()
        return

    registrar_auditoria(
        session,
        actor,
        "ELIMINAR",
        "celda",
        cell.id,
        {"codigo": cell.codigo, "tipo": cell.tipo},
    )
    session.commit()
