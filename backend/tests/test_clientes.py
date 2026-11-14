import importlib.util
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError
import sqlalchemy as sa

from app.database import get_session
from app.main import app
from app.schemas.cliente import ClienteActualizar, ClienteCrear
from app.security import get_current_user
from conftest import make_operator

PAGINA = {
    "items": [
        {
            "id": 1,
            "documento": "123456",
            "nombre": "Cliente Prueba",
            "telefono": "+57 00123",
            "correo": "cliente@example.com",
            "activo": True,
        }
    ],
    "total": 1,
    "offset": 0,
    "limit": 20,
}


def test_cliente_schema_exige_campos_y_correo_valido():
    with pytest.raises(ValidationError):
        ClienteCrear(documento="1", nombre="Prueba", telefono="001")
    with pytest.raises(ValidationError):
        ClienteCrear(
            documento=" ", nombre="Prueba", telefono="001", correo="a@b.co"
        )
    with pytest.raises(ValidationError):
        ClienteCrear(
            documento="1", nombre="Prueba", telefono="001", correo="sin-arroba"
        )
    with pytest.raises(ValidationError):
        ClienteCrear(
            documento="1", nombre="Prueba", telefono="001", correo="a@b.co", activo=1
        )
    cliente = ClienteCrear(
        documento=" 123456 ",
        nombre=" Cliente Prueba ",
        telefono=" +57 00123 ",
        correo=" cliente@example.com ",
    )
    assert cliente.model_dump() == {
        "documento": "123456",
        "nombre": "Cliente Prueba",
        "telefono": "+57 00123",
        "correo": "cliente@example.com",
        "activo": True,
    }


@pytest.mark.parametrize("field", ["documento", "nombre", "telefono", "correo", "activo"])
def test_cliente_patch_rechaza_nulos_explicitos(field):
    with pytest.raises(ValidationError):
        ClienteActualizar(**{field: None})


def test_clientes_api_requiere_autenticacion_y_roles():
    with TestClient(app) as client:
        assert client.get("/clientes").status_code == 401
        assert client.post("/clientes", json=PAGINA["items"][0]).status_code == 401


def test_operador_puede_crear_y_modificar_pero_no_eliminar_clientes(monkeypatch):
    from app.services import cliente as service

    operador = make_operator(operator_id=61, rol="OPERADOR")
    app.dependency_overrides[get_current_user] = lambda: operador
    session = MagicMock()

    def override():
        yield session

    app.dependency_overrides[get_session] = override

    item = MagicMock(
        id=1,
        documento="123456",
        nombre="Cliente Prueba",
        telefono="+57 00123",
        correo="cliente@example.com",
        activo=True,
    )
    monkeypatch.setattr(service, "create_cliente", lambda *args: item)
    monkeypatch.setattr(service, "get_cliente", lambda *args: item)
    monkeypatch.setattr(service, "update_cliente", lambda *args: item)
    monkeypatch.setattr(service, "list_clientes", lambda *args: PAGINA)

    try:
        with TestClient(app) as client:
            # 1. Consulta permitida (200)
            assert client.get("/clientes?offset=0&limit=20").status_code == 200
            
            payload = {
                "documento": "123456",
                "nombre": "Cliente Prueba",
                "telefono": "+57 00123",
                "correo": "cliente@example.com",
            }
            # 2. Creación por operador PERMITIDA (201)
            created = client.post("/clientes", json=payload)
            assert created.status_code == 201

            # 3. Edición por operador PERMITIDA (200)
            assert client.patch("/clientes/1", json={"nombre": "Otro"}).status_code == 200

            # 4. Eliminación por operador DENEGADA (403)
            assert client.delete("/clientes/1").status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_session, None)


def test_administrador_usa_el_crud_de_clientes(monkeypatch):
    from app.services import cliente as service

    admin = make_operator(operator_id=62, rol="ADMINISTRADOR")
    app.dependency_overrides[get_current_user] = lambda: admin
    session = MagicMock()

    def override():
        yield session

    app.dependency_overrides[get_session] = override
    item = MagicMock(
        id=1,
        documento="123456",
        nombre="Cliente Prueba",
        telefono="+57 00123",
        correo="cliente@example.com",
        activo=True,
    )
    monkeypatch.setattr(service, "create_cliente", lambda *args: item)
    monkeypatch.setattr(service, "get_cliente", lambda *args: item)
    monkeypatch.setattr(service, "update_cliente", lambda *args: item)
    monkeypatch.setattr(service, "delete_cliente", lambda *args: None)
    monkeypatch.setattr(service, "list_clientes", lambda *args: PAGINA)
    try:
        with TestClient(app) as client:
            created = client.post(
                "/clientes",
                json={
                    "documento": "123456",
                    "nombre": "Cliente Prueba",
                    "telefono": "+57 00123",
                    "correo": "cliente@example.com",
                },
            )
            assert created.status_code == 201
            assert created.json()["documento"] == "123456"
            assert client.get("/clientes").json() == PAGINA
            assert client.get("/clientes/1").json()["id"] == 1
            assert client.patch("/clientes/1", json={"activo": False}).status_code == 200
            assert client.delete("/clientes/1").status_code == 204
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_session, None)


def test_migracion_0006_crea_clientes_y_columna_sin_destruir_datos():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "clientes_migration", root / "migrations/versions/0006_clientes.py"
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "0006" and migration.down_revision == "0005"

    output = StringIO()
    config = Config(str(root / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "0005:0006", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE cliente" in sql
    assert "ALTER TABLE vehiculo ADD COLUMN cliente_id BIGINT" in sql
    assert "FOREIGN KEY(cliente_id) REFERENCES cliente (id) ON DELETE RESTRICT" in sql
    assert "CREATE INDEX ix_vehiculo_cliente ON vehiculo (cliente_id)" in sql
    assert "DROP" not in sql