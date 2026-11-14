from functools import wraps

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Operador
from app.schemas.operador import OperadorActualizar, OperadorCrear
from app.services.auditoria import registrar_auditoria
from app.services.auth import hash_password


class OperadorError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def database_operation(operation):
    """Centraliza rollback y mensajes públicos sin detalles del driver."""
    @wraps(operation)
    def wrapped(session: Session, *args, **kwargs):
        try:
            return operation(session, *args, **kwargs)
        except IntegrityError as error:
            session.rollback()
            code = getattr(error.orig, "sqlstate", None)
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if code == "23505" and constraint == "uq_operador_usuario":
                raise OperadorError(409, "Ya existe un usuario con ese nombre.") from None
            if code == "23503":
                raise OperadorError(409, "El operador tiene registros relacionados y no se puede eliminar.") from None
            if code in {"23502", "23514"}:
                raise OperadorError(422, "Los datos incumplen las restricciones del operador.") from None
            raise OperadorError(409, "La operación entra en conflicto con los datos existentes.") from None
        except SQLAlchemyError:
            session.rollback()
            raise OperadorError(503, "No se pudo completar la operación con la base de datos.") from None
    return wrapped


def find_operator(session: Session, operator_id: int) -> Operador:
    operator = session.get(Operador, operator_id)
    if operator is None:
        raise OperadorError(404, "Operador no encontrado.")
    return operator


def _other_active_admins(session: Session, operator_id: int) -> int:
    return session.scalar(
        select(func.count()).select_from(Operador).where(
            Operador.rol == "ADMINISTRADOR",
            Operador.activo.is_(True),
            Operador.id != operator_id,
        )
    ) or 0


def _check_admin_transition(session: Session, operator: Operador, actor: Operador, new_rol: str, new_activo: bool) -> None:
    changes_access = new_rol != operator.rol or new_activo != operator.activo
    if not changes_access:
        return
    if operator.id == actor.id and (new_rol != "ADMINISTRADOR" or not new_activo):
        raise OperadorError(409, "No puedes desactivar ni quitarte el rol de administrador.")
    if operator.rol == "ADMINISTRADOR" and (new_rol != "ADMINISTRADOR" or not new_activo):
        if _other_active_admins(session, operator.id) == 0:
            raise OperadorError(409, "Debe existir al menos un administrador activo.")


@database_operation
def create_operator(session: Session, data: OperadorCrear, actor: Operador) -> Operador:
    try:
        password_hash = hash_password(data.contrasena)
    except ValueError as error:
        raise OperadorError(422, str(error)) from None
    operator = Operador(
        nombre=data.nombre,
        telefono=data.telefono,
        usuario=data.usuario,
        contrasena_hash=password_hash,
        rol=data.rol,
        activo=data.activo,
    )
    session.add(operator)
    session.flush()
    registrar_auditoria(
        session,
        actor,
        "CREAR",
        "operador",
        operator.id,
        {"rol": operator.rol, "activo": operator.activo},
    )
    session.commit()
    session.refresh(operator)
    return operator


@database_operation
def list_operators(
    session: Session,
    offset: int,
    limit: int,
    activo: bool | None = True,
    incluir_inactivos: bool = False,
) -> dict:
    query = select(Operador)
    count_query = select(func.count()).select_from(Operador)
    if not incluir_inactivos and activo is not None:
        query = query.where(Operador.activo == activo)
        count_query = count_query.where(Operador.activo == activo)
    total = session.scalar(count_query)
    items = list(session.scalars(query.order_by(Operador.id).offset(offset).limit(limit)))
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@database_operation
def get_operator(session: Session, operator_id: int) -> Operador:
    return find_operator(session, operator_id)


@database_operation
def update_operator(session: Session, operator_id: int, data: OperadorActualizar, actor: Operador) -> Operador:
    operator = find_operator(session, operator_id)
    changes = data.model_dump(exclude_unset=True)
    password = changes.pop("contrasena", None)
    new_rol = changes.get("rol", operator.rol)
    new_activo = changes.get("activo", operator.activo)
    _check_admin_transition(session, operator, actor, new_rol, new_activo)

    changed: list[str] = []
    old_rol, old_activo = operator.rol, operator.activo
    if password is not None:
        try:
            operator.contrasena_hash = hash_password(password)
        except ValueError as error:
            raise OperadorError(422, str(error)) from None
        changed.append("contrasena")
    for key, value in changes.items():
        if getattr(operator, key) != value:
            setattr(operator, key, value)
            changed.append(key)

    if not changed:
        return operator

    if changed == ["contrasena"]:
        action = "CAMBIO_CONTRASENA"
    elif "activo" in changed and operator.activo != old_activo:
        action = "ACTIVAR" if operator.activo else "DESACTIVAR"
    else:
        action = "ACTUALIZAR"
    detail = {"campos": changed}
    if "rol" in changed:
        detail.update({"rol_anterior": old_rol, "rol_nuevo": operator.rol})
    if "activo" in changed:
        detail.update({"activo_anterior": old_activo, "activo_nuevo": operator.activo})
    registrar_auditoria(session, actor, action, "operador", operator.id, detail)
    session.commit()
    session.refresh(operator)
    return operator


@database_operation
def deactivate_operator(session: Session, operator_id: int, actor: Operador) -> None:
    operator = find_operator(session, operator_id)
    if not operator.activo:
        return
    _check_admin_transition(session, operator, actor, operator.rol, False)
    operator.activo = False
    registrar_auditoria(
        session,
        actor,
        "DESACTIVAR",
        "operador",
        operator.id,
        {"activo_anterior": True, "activo_nuevo": False},
    )
    session.commit()


def delete_operator(session: Session, operator_id: int, actor: Operador) -> None:
    """Compatibilidad: el borrado físico se sustituye por inhabilitación lógica."""
    deactivate_operator(session, operator_id, actor)
