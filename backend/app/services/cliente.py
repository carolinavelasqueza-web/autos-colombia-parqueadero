from functools import wraps

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Cliente, Operador
from app.schemas.cliente import ClienteActualizar, ClienteCrear
from app.services.auditoria import auditar, registrar_auditoria

CAMPOS_AUDITADOS = ("documento", "nombre", "telefono", "correo", "activo")


class ClienteError(Exception):
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
                if code == "23505" and constraint == "uq_cliente_documento":
                    raise ClienteError(409, "Ya existe un cliente con ese documento.") from None
                if code == "23503":
                    raise ClienteError(
                        409, "El cliente tiene registros relacionados y no se puede eliminar."
                    ) from None
                if code in {"23502", "23514"}:
                    raise ClienteError(422, "Los datos incumplen las restricciones del cliente.") from None
                raise ClienteError(409, "La operación entra en conflicto con los datos existentes.") from None
            except SQLAlchemyError:
                session.rollback()
                raise ClienteError(503, "No se pudo completar la operación con la base de datos.") from None

        return wrapped

    return decorar(operation) if operation is not None else decorar


def find_cliente(session: Session, cliente_id: int) -> Cliente:
    cliente = session.get(Cliente, cliente_id)
    if cliente is None:
        raise ClienteError(404, "Cliente no encontrado.")
    return cliente


@database_operation(commit=True)
@auditar(
    accion="CREAR",
    entidad="cliente",
    modelo=Cliente,
    campos=CAMPOS_AUDITADOS,
)
def create_cliente(session: Session, data: ClienteCrear, actor: Operador) -> Cliente:
    cliente = Cliente(**data.model_dump())
    session.add(cliente)
    session.flush()
    return cliente


@database_operation
def list_clientes(
    session: Session, offset: int, limit: int, activo: bool | None = None
) -> dict:
    query = select(Cliente)
    count_query = select(func.count()).select_from(Cliente)
    if activo is not None:
        query = query.where(Cliente.activo == activo)
        count_query = count_query.where(Cliente.activo == activo)
    total = session.scalar(count_query)
    items = list(
        session.scalars(query.order_by(Cliente.id).offset(offset).limit(limit))
    )
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@database_operation
def get_cliente(session: Session, cliente_id: int) -> Cliente:
    return find_cliente(session, cliente_id)


@database_operation(commit=True)
@auditar(
    accion="ACTUALIZAR",
    entidad="cliente",
    id_arg="cliente_id",
    modelo=Cliente,
    campos=CAMPOS_AUDITADOS,
)
def update_cliente(
    session: Session, cliente_id: int, data: ClienteActualizar, actor: Operador
) -> Cliente:
    cliente = find_cliente(session, cliente_id)
    changes = data.model_dump(exclude_unset=True)
    changed = False
    for key, value in changes.items():
        if getattr(cliente, key) != value:
            setattr(cliente, key, value)
            changed = True
    if changed:
        session.flush()
    return cliente


@database_operation
def delete_cliente(session: Session, cliente_id: int, actor: Operador) -> None:
    """Baja lógica: conserva vehículos, estancias y auditoría."""
    cliente = find_cliente(session, cliente_id)
    if cliente.activo is False:
        return
    cliente.activo = False
    registrar_auditoria(
        session,
        actor,
        "DESACTIVAR",
        "cliente",
        cliente.id,
        {"activo_anterior": True, "activo_nuevo": False, "motivo": "baja_logica"},
    )
    session.commit()
