from functools import wraps

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models import Cliente, Operador, Vehiculo
from app.schemas.vehiculo import VehiculoActualizar, VehiculoCrear
from app.services.auditoria import auditar

CAMPOS_AUDITADOS = (
    "placa",
    "color",
    "modelo",
    "marca",
    "tipo",
    "cliente_id",
)


class VehiculoError(Exception):
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
                if code == "23505" and constraint == "uq_vehiculo_placa":
                    raise VehiculoError(409, "Ya existe un vehículo con esa placa.") from None
                if code == "23503":
                    raise VehiculoError(409, "El vehículo tiene registros relacionados y no se puede eliminar.") from None
                if code in {"23502", "23514"}:
                    raise VehiculoError(422, "Los datos incumplen las restricciones del vehículo.") from None
                raise VehiculoError(409, "La operación entra en conflicto con los datos existentes.") from None
            except SQLAlchemyError:
                session.rollback()
                raise VehiculoError(503, "No se pudo completar la operación con la base de datos.") from None

        return wrapped

    return decorar(operation) if operation is not None else decorar


def _load_vehicle(session: Session, vehicle_id: int) -> Vehiculo:
    vehicle = session.scalar(
        select(Vehiculo)
        .options(selectinload(Vehiculo.cliente))
        .where(Vehiculo.id == vehicle_id)
    )
    if vehicle is None:
        raise VehiculoError(404, "Vehículo no encontrado.")
    return vehicle


def find_vehicle(session: Session, vehicle_id: int) -> Vehiculo:
    vehicle = session.get(
        Vehiculo, vehicle_id, options=[selectinload(Vehiculo.cliente)]
    )
    if vehicle is None:
        raise VehiculoError(404, "Vehículo no encontrado.")
    return vehicle


def _require_cliente(session: Session, cliente_id: int) -> Cliente:
    cliente = session.get(Cliente, cliente_id)
    if cliente is None:
        raise VehiculoError(404, "Cliente no encontrado.")
    return cliente


@database_operation(commit=True)
@auditar(
    accion="CREAR",
    entidad="vehiculo",
    modelo=Vehiculo,
    campos=CAMPOS_AUDITADOS,
)
def create_vehicle(session: Session, data: VehiculoCrear, actor: Operador) -> Vehiculo:
    _require_cliente(session, data.cliente_id)
    vehicle = Vehiculo(**data.model_dump())
    session.add(vehicle)
    session.flush()
    return _load_vehicle(session, vehicle.id)


@database_operation
def list_vehicles(session: Session, offset: int, limit: int) -> dict:
    total = session.scalar(select(func.count()).select_from(Vehiculo))
    items = list(
        session.scalars(
            select(Vehiculo)
            .options(selectinload(Vehiculo.cliente))
            .order_by(Vehiculo.id)
            .offset(offset)
            .limit(limit)
        )
    )
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@database_operation
def get_vehicle(session: Session, vehicle_id: int) -> Vehiculo:
    return _load_vehicle(session, vehicle_id)


@database_operation(commit=True)
@auditar(
    accion="ACTUALIZAR",
    entidad="vehiculo",
    id_arg="vehicle_id",
    modelo=Vehiculo,
    campos=CAMPOS_AUDITADOS,
)
def update_vehicle(
    session: Session, vehicle_id: int, data: VehiculoActualizar, actor: Operador
) -> Vehiculo:
    vehicle = find_vehicle(session, vehicle_id)
    changes = data.model_dump(exclude_unset=True)
    if "cliente_id" in changes:
        _require_cliente(session, changes["cliente_id"])
    changed = []
    for key, value in changes.items():
        if getattr(vehicle, key) != value:
            setattr(vehicle, key, value)
            changed.append(key)
    if not changed:
        return vehicle
    session.flush()
    return _load_vehicle(session, vehicle.id)


@database_operation(commit=True)
@auditar(
    accion="ELIMINAR",
    entidad="vehiculo",
    id_arg="vehicle_id",
    modelo=Vehiculo,
    campos=CAMPOS_AUDITADOS,
)
def delete_vehicle(session: Session, vehicle_id: int, actor: Operador) -> None:
    vehicle = find_vehicle(session, vehicle_id)
    session.delete(vehicle)
