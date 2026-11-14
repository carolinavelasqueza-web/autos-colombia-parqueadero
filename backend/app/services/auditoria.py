import inspect
from collections.abc import Callable, Iterable, Mapping
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from functools import wraps
from typing import Any

from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy.orm import Session

from app.models import Auditoria, Operador

__all__ = [
    "auditar",
    "registrar_auditoria",
    "serializar_valor",
    "snapshot_entidad",
]


def serializar_valor(value: Any) -> Any:
    """Convierte valores de dominio a JSON estable y sin tipos exóticos."""
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat() if value.tzinfo else value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def snapshot_entidad(
    entidad: Any, campos: Iterable[str] | None = None
) -> dict[str, Any]:
    """Extrae un diccionario serializable de las columnas de una entidad."""
    if campos is not None:
        nombres = list(campos)
    else:
        try:
            mapper = sqlalchemy_inspect(entidad).mapper
            nombres = [atributo.key for atributo in mapper.column_attrs]
        except Exception:
            # Los dobles de prueba sin mapper no deben romper la auditoría.
            nombres = [nombre for nombre in vars(entidad) if not nombre.startswith("_")]
    return {
        nombre: serializar_valor(getattr(entidad, nombre, None))
        for nombre in nombres
    }


def registrar_auditoria(
    session: Session,
    actor: Operador,
    accion: str,
    entidad: str,
    entidad_id: int | None = None,
    detalle: dict[str, Any] | None = None,
) -> None:
    """Añade la auditoría a la transacción actual; el servicio que llama confirma."""
    if actor.id is None:
        raise ValueError("El operador autenticado debe tener un id para auditar.")
    session.add(
        Auditoria(
            operador_id=actor.id,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            detalle=detalle,
        )
    )


def _resolver_session(bound: inspect.BoundArguments, args: tuple[Any, ...]) -> Session | None:
    session = bound.arguments.get("session")
    if session is not None:
        return session
    if args:
        return getattr(args[0], "session", None)
    return None


def auditar(
    *,
    accion: str,
    entidad: str,
    id_arg: str | None = None,
    modelo: type | None = None,
    campos: Iterable[str] | None = None,
    actor_arg: str = "actor",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Registra automáticamente cambios de estado en ``auditoria``.

    El decorador no confirma ni revierte la transacción: añade la fila de
    auditoría y deja que el servicio o su envoltorio hagan ``commit``. Debe
    aplicarse a operaciones que terminan en ``flush``, no que confirman por sí
    mismas.
    """

    def decorador(operation: Callable[..., Any]) -> Callable[..., Any]:
        signature = inspect.signature(operation)

        @wraps(operation)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            bound = signature.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            session = _resolver_session(bound, args)
            if session is None:
                raise TypeError("La operación auditada debe recibir una sesión.")
            actor = bound.arguments.get(actor_arg)
            if actor is None or getattr(actor, "id", None) is None:
                raise ValueError("El operador autenticado debe tener un id para auditar.")

            entidad_id = bound.arguments.get(id_arg) if id_arg else None
            anteriores: dict[str, Any] | None = None
            if modelo is not None and entidad_id is not None:
                previo = session.get(modelo, entidad_id)
                if previo is not None:
                    anteriores = snapshot_entidad(previo, campos)

            resultado = operation(*args, **kwargs)
            if modelo is None:
                return resultado

            if accion == "ELIMINAR":
                # Fuerza el DELETE antes de comprobar si la entidad sigue viva.
                session.flush()

            objetivo = resultado
            if objetivo is None and entidad_id is not None:
                objetivo = session.get(modelo, entidad_id)

            if objetivo is None:
                if anteriores is not None:
                    registrar_auditoria(
                        session,
                        actor,
                        accion,
                        entidad,
                        entidad_id,
                        {"anteriores": anteriores},
                    )
                return resultado

            nuevos = snapshot_entidad(objetivo, campos)
            objetivo_id = getattr(objetivo, "id", None) or entidad_id
            if accion == "CREAR":
                detalle = {"nuevos": nuevos}
            else:
                anteriores = anteriores or {}
                cambiados = [
                    campo for campo in nuevos if anteriores.get(campo) != nuevos[campo]
                ]
                if not cambiados:
                    return resultado
                detalle = {
                    "campos": cambiados,
                    "anteriores": {campo: anteriores.get(campo) for campo in cambiados},
                    "nuevos": {campo: nuevos[campo] for campo in cambiados},
                }

            registrar_auditoria(
                session, actor, accion, entidad, objetivo_id, detalle
            )
            return resultado

        return wrapped

    return decorador


def auditar_cambio(
    session: Session,
    actor: Operador,
    accion: str,
    entidad: str,
    entidad_id: int | None,
    anteriores: Mapping[str, Any] | None = None,
    nuevos: Mapping[str, Any] | None = None,
    contexto: Mapping[str, Any] | None = None,
) -> None:
    """Variante explícita para servicios con detalles de dominio propios."""
    detalle: dict[str, Any] = {}
    if anteriores is not None:
        detalle["anteriores"] = {
            clave: serializar_valor(valor) for clave, valor in anteriores.items()
        }
    if nuevos is not None:
        detalle["nuevos"] = {
            clave: serializar_valor(valor) for clave, valor in nuevos.items()
        }
    if contexto:
        detalle["contexto"] = dict(contexto)
    registrar_auditoria(session, actor, accion, entidad, entidad_id, detalle or None)
