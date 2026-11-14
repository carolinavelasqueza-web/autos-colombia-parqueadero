from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Operador, ROLES_OPERADOR, Sesion
from app.services.auth import (
    AuthError,
    decode_access_token,
    hash_token,
)

bearer_scheme = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[Session, Depends(get_session)]
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


@dataclass(frozen=True)
class SesionActual:
    operador: Operador
    sesion: Sesion


def _unauthorized(detail: str) -> AuthError:
    return AuthError(401, detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_session(
    credentials: BearerCredentials, session: DatabaseSession
) -> SesionActual:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Se requiere autenticación.")
    payload = decode_access_token(credentials.credentials)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise _unauthorized("Token no válido.") from None
    if payload.get("user_id") is not None and payload.get("user_id") != user_id:
        raise _unauthorized("Token no válido.")

    sesion = session.scalar(
        select(Sesion).where(Sesion.token_hash == hash_token(credentials.credentials))
    )
    if (
        sesion is None
        or sesion.operador_id != user_id
        or not sesion.esta_vigente(datetime.now(timezone.utc))
    ):
        raise _unauthorized("Sesión no válida.")

    operator = session.get(Operador, user_id)
    if operator is None or not operator.activo or operator.rol not in ROLES_OPERADOR:
        raise _unauthorized("Sesión no válida.")
    return SesionActual(operador=operator, sesion=sesion)


def get_current_user(
    actual: Annotated[SesionActual, Depends(get_current_session)],
) -> Operador:
    return actual.operador


CurrentUser = Annotated[Operador, Depends(get_current_user)]
CurrentSesion = Annotated[SesionActual, Depends(get_current_session)]


def require_role(roles: list[str]):
    allowed = frozenset(roles)

    def dependency(current_user: Annotated[Operador, Depends(get_current_user)]) -> Operador:
        if current_user.rol not in allowed:
            raise AuthError(403, "No tienes permisos para esta operación.")
        return current_user

    return dependency
