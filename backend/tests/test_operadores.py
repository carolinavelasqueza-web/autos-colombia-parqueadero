"""Errores HTTP y rollback sin depender de PostgreSQL."""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import get_session
from app.main import app
from app.models import Operador
from app.services.operador import OperadorError, deactivate_operator
from conftest import make_operator

VALID_PAYLOAD = {
    "nombre": "Prueba",
    "telefono": "001",
    "usuario": "prueba",
    "contrasena": "clave-segura",
    "rol": "OPERADOR",
    "activo": True,
}


@pytest.fixture
def api(authenticate):
    session = MagicMock()
    session.scalar.return_value = 0
    session.get.return_value = make_operator(operator_id=2, rol="OPERADOR")

    def override():
        yield session

    app.dependency_overrides[get_session] = override
    authenticate(make_operator(operator_id=1))
    try:
        with TestClient(app) as client:
            yield client, session
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.parametrize("field", ["nombre", "telefono", "usuario", "contrasena", "rol", "activo"])
@pytest.mark.parametrize("value", [None, "", " \t\n", 123, True, []])
def test_invalid_fields_are_422_without_writes(api, field, value):
    if field == "activo" and value is True:
        pytest.skip("activo=True es un valor válido")
    client, session = api
    payload = {**VALID_PAYLOAD, field: value}
    assert client.post("/operadores", json=payload).status_code == 422
    assert client.patch("/operadores/2", json={field: value}).status_code == 422
    session.commit.assert_not_called()


@pytest.mark.parametrize("payload", [
    {},
    {"nombre": "Prueba"},
    {**VALID_PAYLOAD, "usuario": "ab"},
    {**VALID_PAYLOAD, "usuario": "Con Espacios"},
    {**VALID_PAYLOAD, "contrasena": "corta"},
    {**VALID_PAYLOAD, "rol": "admin"},
    {**VALID_PAYLOAD, "id": 1},
])
def test_creation_requires_valid_fields_and_forbids_id(api, payload):
    client, session = api
    assert client.post("/operadores", json=payload).status_code == 422
    session.commit.assert_not_called()


def test_response_never_exposes_password(api):
    client, session = api
    session.get.return_value = Operador(
        id=2,
        nombre="Prueba",
        telefono="001",
        usuario="prueba",
        contrasena_hash="$2b$12$hash-privado",
        rol="OPERADOR",
        activo=True,
    )
    result = client.get("/operadores/2")
    assert result.status_code == 200
    assert "contrasena" not in result.text
    assert "hash-privado" not in result.text


def test_patch_forbids_id_and_unknown_fields(api):
    client, session = api
    for payload in ({"id": 2}, {"desconocido": "x"}, {"rol": "admin"}):
        assert client.patch("/operadores/2", json=payload).status_code == 422
    session.commit.assert_not_called()


@pytest.mark.parametrize("sqlstate, status", [("23503", 409), ("23502", 422), ("23514", 422)])
def test_database_conflicts_roll_back_and_hide_details(api, sqlstate, status):
    client, session = api
    driver_error = Exception("PRIVATE DRIVER DETAILS")
    driver_error.sqlstate = sqlstate
    session.commit.side_effect = IntegrityError("UPDATE", {}, driver_error)
    result = client.delete("/operadores/2")
    assert result.status_code == status
    assert "PRIVATE" not in result.text
    assert isinstance(result.json()["detail"], str)
    session.rollback.assert_called_once()
    session.delete.assert_not_called()


def test_admin_cannot_deactivate_self():
    session = MagicMock()
    admin = make_operator(operator_id=1)
    session.get.return_value = admin
    with pytest.raises(OperadorError) as error:
        deactivate_operator(session, 1, admin)
    assert error.value.status_code == 409
    session.commit.assert_not_called()


def test_last_active_admin_cannot_be_deactivated():
    session = MagicMock()
    session.get.return_value = make_operator(operator_id=2)
    session.scalar.return_value = 0
    with pytest.raises(OperadorError) as error:
        deactivate_operator(session, 2, make_operator(operator_id=1))
    assert error.value.status_code == 409
    session.commit.assert_not_called()


def test_admin_can_be_deactivated_when_another_admin_remains():
    session = MagicMock()
    target = make_operator(operator_id=2)
    session.get.return_value = target
    session.scalar.return_value = 1
    deactivate_operator(session, 2, make_operator(operator_id=1))
    assert target.activo is False
    session.commit.assert_called_once()


def test_database_failure_rolls_back_and_is_generic(api):
    client, session = api
    session.get.side_effect = SQLAlchemyError("PRIVATE DRIVER DETAILS")
    result = client.get("/operadores/2")
    assert result.status_code == 503
    assert "PRIVATE" not in result.text
    session.rollback.assert_called_once()
