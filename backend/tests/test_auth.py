from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app import config
from app.database import get_session
from app.main import app
from app.models import Operador, Sesion
from app.schemas.auth import LoginRequest
from app.services.auth import (
    AuthError,
    authenticate,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    login,
    verify_password,
)
from conftest import make_operator

SECRET = "clave-de-prueba-con-mas-de-32-caracteres"


@pytest.fixture
def auth_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"JWT_SECRET_KEY={SECRET}\nJWT_EXPIRE_MINUTES=60\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_EXPIRE_MINUTES", raising=False)
    monkeypatch.setattr(config, "ENV_FILE", env_file)
    config.load_auth_settings.cache_clear()
    yield
    config.load_auth_settings.cache_clear()


@pytest.fixture
def api_session(auth_env):
    session = MagicMock()
    session.scalar.return_value = None

    def override():
        yield session

    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app) as client:
            yield client, session
    finally:
        app.dependency_overrides.pop(get_session, None)


def make_sesion(
    operador_id: int = 1,
    *,
    expira_en: datetime | None = None,
    revocada_en: datetime | None = None,
) -> Sesion:
    return Sesion(
        operador_id=operador_id,
        token_hash="a" * 64,
        expira_en=expira_en or datetime.now(timezone.utc) + timedelta(hours=1),
        revocada_en=revocada_en,
    )


def test_password_hash_is_bcrypt_and_verifies():
    password_hash = hash_password("clave-segura")
    assert password_hash.startswith("$2b$")
    assert "clave-segura" not in password_hash
    assert verify_password("clave-segura", password_hash) is True
    assert verify_password("otra-clave", password_hash) is False


@pytest.mark.parametrize("password", ["", "corta", "x" * 73])
def test_hash_password_rejects_invalid_values(password):
    with pytest.raises(ValueError):
        hash_password(password)


def test_token_contains_user_and_role(auth_env):
    operator = make_operator(operator_id=9, rol="ADMINISTRADOR")
    token, expires_in = create_access_token(operator)
    payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    assert payload["sub"] == "9"
    assert payload["user_id"] == 9
    assert payload["rol"] == "ADMINISTRADOR"
    assert expires_in == 3600
    assert decode_access_token(token)["user_id"] == 9


def test_expired_and_tampered_tokens_are_rejected(auth_env):
    operator = make_operator(operator_id=9)
    expired = jwt.encode(
        {
            "sub": "9",
            "user_id": 9,
            "rol": "ADMINISTRADOR",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(AuthError) as expired_error:
        decode_access_token(expired)
    assert expired_error.value.status_code == 401

    valid, _ = create_access_token(operator)
    with pytest.raises(AuthError) as tampered_error:
        decode_access_token(valid + "x")
    assert tampered_error.value.status_code == 401


def test_missing_jwt_configuration_returns_503(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("JWT_SECRET_KEY=CAMBIAR_PENDIENTE\n", encoding="utf-8")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.setattr(config, "ENV_FILE", env_file)
    config.load_auth_settings.cache_clear()
    try:
        with pytest.raises(AuthError) as error:
            create_access_token(make_operator())
        assert error.value.status_code == 503
    finally:
        config.load_auth_settings.cache_clear()


def test_authenticate_rejects_unknown_inactive_and_wrong_password(auth_env):
    session = MagicMock()
    session.scalar.return_value = None
    assert authenticate(session, "desconocido", "clave-segura") is None

    inactive = make_operator(activo=False)
    inactive.contrasena_hash = hash_password("clave-segura")
    session.scalar.return_value = inactive
    assert authenticate(session, "operador1", "clave-segura") is None

    active = make_operator()
    active.contrasena_hash = hash_password("clave-segura")
    session.scalar.return_value = active
    assert authenticate(session, "operador1", "incorrecta") is None
    assert authenticate(session, " OPERADOR1 ", "clave-segura") is active


def test_login_returns_token_and_audits(api_session):
    client, session = api_session
    operator = make_operator(rol="OPERADOR")
    operator.contrasena_hash = hash_password("clave-segura")
    session.scalar.return_value = operator

    result = client.post(
        "/api/v1/auth/login",
        json={"usuario": " OPERADOR1 ", "contrasena": "clave-segura"},
    )
    assert result.status_code == 200
    body = result.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    assert decode_access_token(body["access_token"])["rol"] == "OPERADOR"
    assert session.add.call_count == 2
    primera, segunda = (llamada.args[0] for llamada in session.add.call_args_list)
    assert isinstance(primera, Sesion)
    assert primera.operador_id == operator.id
    assert primera.token_hash == hash_token(body["access_token"])
    assert segunda.__class__.__name__ == "Auditoria"
    session.flush.assert_called_once()
    session.commit.assert_called_once()


def test_login_rejects_bad_credentials_without_details(api_session):
    client, session = api_session
    session.scalar.return_value = None
    result = client.post(
        "/api/v1/auth/login",
        json={"usuario": "desconocido", "contrasena": "clave-segura"},
    )
    assert result.status_code == 401
    assert result.json() == {"detail": "Credenciales inválidas."}
    assert result.headers["www-authenticate"] == "Bearer"
    session.commit.assert_not_called()


def test_login_service_rolls_back_on_database_error(auth_env):
    session = MagicMock()
    session.scalar.side_effect = SQLAlchemyError("private")
    with pytest.raises(AuthError) as error:
        login(session, LoginRequest(usuario="operador1", contrasena="clave-segura"))
    assert error.value.status_code == 503
    session.rollback.assert_called_once()


def test_me_requires_token(api_session):
    client, _ = api_session
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_current_user(api_session):
    client, session = api_session
    operator = make_operator(operator_id=7, rol="ADMINISTRADOR")
    session.scalar.return_value = make_sesion(7)
    session.get.return_value = operator
    token, _ = create_access_token(operator)
    result = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert result.status_code == 200
    assert result.json() == {
        "id": 7,
        "nombre": "Operador 7",
        "usuario": "operador7",
        "rol": "ADMINISTRADOR",
        "activo": True,
    }


def test_deactivated_user_with_valid_token_is_rejected(api_session):
    client, session = api_session
    operator = make_operator(operator_id=7)
    token, _ = create_access_token(operator)
    session.scalar.return_value = make_sesion(7)
    session.get.return_value = make_operator(operator_id=7, activo=False)
    assert client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    ).status_code == 401


def test_revoked_expired_or_mismatched_session_is_rejected(api_session):
    client, session = api_session
    operator = make_operator(operator_id=7)
    token, _ = create_access_token(operator)
    headers = {"Authorization": f"Bearer {token}"}

    session.scalar.return_value = make_sesion(
        7, revocada_en=datetime.now(timezone.utc)
    )
    session.get.return_value = operator
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401

    session.scalar.return_value = make_sesion(
        7, expira_en=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401

    session.scalar.return_value = make_sesion(8)
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_logout_revokes_session_and_audits(api_session):
    client, session = api_session
    operator = make_operator(operator_id=7)
    sesion = make_sesion(7)
    session.scalar.return_value = sesion
    session.get.return_value = operator
    token, _ = create_access_token(operator)
    headers = {"Authorization": f"Bearer {token}"}

    result = client.post("/api/v1/auth/logout", headers=headers)
    assert result.status_code == 204
    assert sesion.revocada_en is not None
    assert session.commit.call_count == 1
    auditada = session.add.call_args.args[0]
    assert auditada.__class__.__name__ == "Auditoria"
    assert auditada.accion == "LOGOUT"

    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 401


def test_logout_requires_token(api_session):
    client, _ = api_session
    assert client.post("/api/v1/auth/logout").status_code == 401


def test_operator_cannot_manage_users_or_cells(api_session):
    client, session = api_session
    operator = make_operator(operator_id=4, rol="OPERADOR")
    session.scalar.return_value = make_sesion(4)
    session.get.return_value = operator
    token, _ = create_access_token(operator)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/operadores", json={}, headers=headers).status_code == 403
    assert client.post("/celdas", json={}, headers=headers).status_code == 403
    assert client.patch("/celdas/1", json={"tipo": "Libre"}, headers=headers).status_code == 403
    assert client.delete("/operadores/4", headers=headers).status_code == 403
    assert client.delete("/celdas/1", headers=headers).status_code == 403
    assert client.get("/celdas?incluir_inactivas=true", headers=headers).status_code == 403
    assert client.patch("/estancias/1", json={"celda_id": 2}, headers=headers).status_code == 403
    assert client.delete("/estancias/1", headers=headers).status_code == 403


def test_cell_mutations_require_authentication(api_session):
    client, _ = api_session
    assert client.post("/celdas", json={"codigo": "A-01", "tipo": "Libre"}).status_code == 401
    assert client.patch("/celdas/1", json={"tipo": "Libre"}).status_code == 401
    assert client.delete("/celdas/1").status_code == 401
    assert client.patch("/estancias/1", json={"celda_id": 2}).status_code == 401
    assert client.delete("/estancias/1").status_code == 401


def test_administrator_can_manage_users_and_cells(api_session):
    client, session = api_session
    admin = make_operator(operator_id=1, rol="ADMINISTRADOR")
    session.scalar.return_value = make_sesion(1)
    session.get.return_value = admin
    token, _ = create_access_token(admin)
    headers = {"Authorization": f"Bearer {token}"}
    # La validación del cuerpo llega a 422, lo que demuestra que el rol fue admitido.
    assert client.post("/operadores", json={}, headers=headers).status_code == 422
    assert client.post("/celdas", json={}, headers=headers).status_code == 422
    assert client.patch("/estancias/1", json={"entrada": None}, headers=headers).status_code == 422


def test_database_role_change_applies_immediately(api_session):
    client, session = api_session
    admin = make_operator(operator_id=1, rol="ADMINISTRADOR")
    token, _ = create_access_token(admin)
    session.scalar.return_value = make_sesion(1)
    session.get.return_value = make_operator(operator_id=1, rol="OPERADOR")
    result = client.post(
        "/celdas",
        json={"codigo": "A-01", "tipo": "Libre"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert result.status_code == 403


def test_deactivated_operator_in_database_cannot_login(api_session):
    client, session = api_session
    operator = make_operator(activo=False)
    operator.contrasena_hash = hash_password("clave-segura")
    session.scalar.return_value = operator
    result = client.post(
        "/api/v1/auth/login",
        json={"usuario": "operador1", "contrasena": "clave-segura"},
    )
    assert result.status_code == 401
