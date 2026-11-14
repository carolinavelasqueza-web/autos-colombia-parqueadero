import hashlib
import re
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import ConfigurationError, load_auth_settings
from app.models import Operador, ROLES_OPERADOR, Sesion, normalize_usuario, validate_password
from app.schemas.auth import LoginRequest, TokenRespuesta
from app.services.auditoria import registrar_auditoria

BCRYPT_ROUNDS = 12
# Hash de una contraseña aleatoria que no corresponde a ninguna cuenta.
_DUMMY_HASH = "$2b$12$WDe3CYD0J6gZNsq554mZdOyzKUEiHXavR15CV7QBSYCw34SEQCM0q"
_JTI_RE = re.compile(r"^[0-9a-f]{32}$")


def hash_token(token: str) -> str:
    """Devuelve el SHA-256 hexadecimal del token compacto."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthError(Exception):
    def __init__(self, status_code: int, detail: str, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self.detail = detail
        self.headers = headers


def hash_password(password: str) -> str:
    validate_password(password)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    if not isinstance(password, str) or not isinstance(password_hash, str):
        return False
    if not password or len(password.encode("utf-8")) > 72:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, TypeError, UnicodeEncodeError):
        return False


def authenticate(session: Session, usuario: str, contrasena: str) -> Operador | None:
    try:
        normalized = normalize_usuario(usuario)
    except ValueError:
        normalized = ""
    operator = (
        session.scalar(select(Operador).where(Operador.usuario == normalized))
        if normalized
        else None
    )
    if operator is None or not operator.activo:
        verify_password(contrasena, _DUMMY_HASH)
        return None
    if not verify_password(contrasena, operator.contrasena_hash):
        return None
    return operator


def create_access_token(operator: Operador) -> tuple[str, int]:
    try:
        settings = load_auth_settings()
    except ConfigurationError:
        raise AuthError(503, "Servicio de autenticación no configurado.") from None
    now = datetime.now(timezone.utc)
    expires_in = settings.expire_minutes * 60
    payload = {
        "sub": str(operator.id),
        "user_id": operator.id,
        "rol": operator.rol,
        "iat": now,
        "exp": now + timedelta(minutes=settings.expire_minutes),
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token, expires_in


def decode_access_token(token: str) -> dict:
    try:
        settings = load_auth_settings()
    except ConfigurationError:
        raise AuthError(503, "Servicio de autenticación no configurado.") from None
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
    except jwt.ExpiredSignatureError:
        raise AuthError(
            401, "La sesión ha expirado.", headers={"WWW-Authenticate": "Bearer"}
        ) from None
    except jwt.InvalidTokenError:
        raise AuthError(
            401, "Token no válido.", headers={"WWW-Authenticate": "Bearer"}
        ) from None
    if payload.get("rol") not in ROLES_OPERADOR:
        raise AuthError(401, "Token no válido.", headers={"WWW-Authenticate": "Bearer"})
    if not isinstance(payload.get("jti"), str) or not _JTI_RE.fullmatch(payload["jti"]):
        raise AuthError(401, "Token no válido.", headers={"WWW-Authenticate": "Bearer"})
    return payload


def login(session: Session, data: LoginRequest) -> TokenRespuesta:
    try:
        operator = authenticate(session, data.usuario, data.contrasena)
        if operator is None:
            raise AuthError(
                401, "Credenciales inválidas.", headers={"WWW-Authenticate": "Bearer"}
            )
        token, expires_in = create_access_token(operator)
        sesion = Sesion(
            operador_id=operator.id,
            token_hash=hash_token(token),
            expira_en=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        )
        session.add(sesion)
        session.flush()
        registrar_auditoria(
            session,
            operator,
            "LOGIN",
            "sesion",
            sesion.id,
            {"rol": operator.rol, "expira_en": sesion.expira_en.isoformat()},
        )
        session.commit()
        return TokenRespuesta(access_token=token, expires_in=expires_in)
    except AuthError:
        session.rollback()
        raise
    except SQLAlchemyError:
        session.rollback()
        raise AuthError(503, "No se pudo completar la operación con la base de datos.") from None


def logout(session: Session, sesion: Sesion, operator: Operador) -> None:
    """Revoca la sesión actual y registra la acción del operador."""
    try:
        if sesion.revocada_en is not None:
            return
        sesion.revocada_en = datetime.now(timezone.utc)
        registrar_auditoria(
            session,
            operator,
            "LOGOUT",
            "sesion",
            sesion.id,
            {"rol": operator.rol},
        )
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise AuthError(503, "No se pudo completar la operación con la base de datos.") from None
