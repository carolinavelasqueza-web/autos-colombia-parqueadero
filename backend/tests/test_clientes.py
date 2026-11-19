import importlib.util
from datetime import date
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
from app.models import Cliente
from app.schemas.cliente import (
    ClienteActualizar,
    ClienteCrear,
    ClienteRespuesta,
    MensualidadRespuesta,
)
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
            "fecha_vencimiento": None,
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
        fecha_vencimiento=None,
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
        fecha_vencimiento=None,
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


# ---------------------------------------------------------------- mensualidad y alertas

HOY = date(2026, 11, 18)


def _cliente(vencimiento=None, activo=True, id_=1, documento="123456"):
    return Cliente(
        id=id_,
        documento=documento,
        nombre="Cliente Prueba",
        telefono="+57 00123",
        correo="cliente@example.com",
        activo=activo,
        fecha_vencimiento=vencimiento,
    )


@pytest.fixture(params=["ADMINISTRADOR", "OPERADOR"])
def api_rol(request, authenticate):
    session = MagicMock()

    def override():
        yield session

    app.dependency_overrides[get_session] = override
    authenticate(make_operator(operator_id=10, rol=request.param))
    try:
        with TestClient(app) as client:
            yield client, session
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_cliente_respuesta_expone_la_fecha_de_vencimiento():
    respuesta = ClienteRespuesta.model_validate(
        _cliente(vencimiento=date(2027, 1, 18))
    )

    assert respuesta.fecha_vencimiento == date(2027, 1, 18)
    assert "fecha_vencimiento" in ClienteRespuesta.model_fields
    assert "fecha_vencimiento" not in ClienteActualizar.model_fields


@pytest.mark.parametrize(
    "valor", [None, "2027-01-18", date(2027, 1, 18), {"anio": 2027}]
)
def test_patch_rechaza_fecha_vencimiento(valor):
    with pytest.raises(ValidationError) as error:
        ClienteActualizar(fecha_vencimiento=valor)

    assert "solo lectura" in str(error.value)


def test_patch_api_rechaza_fecha_vencimiento(api_rol, monkeypatch):
    client, _ = api_rol
    from app.services import cliente as service

    llamado = False

    def actualizar(*args, **kwargs):
        nonlocal llamado
        llamado = True

    monkeypatch.setattr(service, "update_cliente", actualizar)

    response = client.patch(
        "/clientes/1", json={"fecha_vencimiento": "2027-01-18"}
    )

    assert response.status_code == 422
    assert llamado is False


def test_schema_mensualidad_valida_el_contrato():
    cuerpo = MensualidadRespuesta.model_validate(
        {
            "cliente": _cliente(vencimiento=date(2026, 11, 20)),
            "estado": "POR_VENCER",
        }
    )

    assert cuerpo.estado == "POR_VENCER"
    with pytest.raises(ValidationError):
        MensualidadRespuesta.model_validate(
            {
                "cliente": _cliente(vencimiento=date(2026, 11, 20)),
                "estado": "OTRO",
            }
        )


@pytest.mark.parametrize(
    "vencimiento,esperado",
    [
        (None, "SIN_PAGO"),
        (date(2026, 11, 17), "VENCIDA"),
        (date(2026, 11, 18), "POR_VENCER"),
        (date(2026, 11, 23), "POR_VENCER"),
        (date(2026, 11, 24), "AL_DIA"),
    ],
)
def test_get_mensualidad_reutiliza_el_dominio(monkeypatch, vencimiento, esperado):
    from app.services import cliente as service

    cliente = _cliente(vencimiento=vencimiento)
    session = MagicMock()
    session.get.return_value = cliente
    monkeypatch.setattr(service, "hoy_bogota", lambda: HOY)

    resultado = service.get_mensualidad(session, 1)

    assert resultado == {"cliente": cliente, "estado": esperado}


def test_get_mensualidad_inexistente_devuelve_404():
    from app.services import cliente as service

    session = MagicMock()
    session.get.return_value = None

    with pytest.raises(service.ClienteError) as error:
        service.get_mensualidad(session, 99)

    assert error.value.status_code == 404
    assert error.value.detail == "Cliente no encontrado."


def test_listar_alertas_filtra_activos_y_ordenapor_vencimiento(monkeypatch):
    from app.services import cliente as service

    vencido = _cliente(id_=1, vencimiento=date(2026, 11, 10))
    por_vencer = _cliente(id_=2, vencimiento=date(2026, 11, 20))
    session = MagicMock()
    session.scalar.return_value = 2
    session.scalars.return_value = [vencido, por_vencer]
    monkeypatch.setattr(service, "hoy_bogota", lambda: HOY)

    resultado = service.listar_alertas(session, offset=10, limit=5)

    assert resultado["total"] == 2
    assert resultado["offset"] == 10
    assert resultado["limit"] == 5
    assert resultado["items"] == [
        {"cliente": vencido, "estado": "VENCIDA"},
        {"cliente": por_vencer, "estado": "POR_VENCER"},
    ]

    conteo = session.scalar.call_args.args[0]
    assert "count" in str(conteo).lower()
    assert "cliente.activo IS true" in str(conteo)
    assert "cliente.fecha_vencimiento IS NOT NULL" in str(conteo)
    assert date(2026, 11, 23) in conteo.compile().params.values()

    consulta = session.scalars.call_args.args[0]
    sentencia = str(consulta)
    assert "cliente.activo IS true" in sentencia
    assert "cliente.fecha_vencimiento IS NOT NULL" in sentencia
    assert "ORDER BY cliente.fecha_vencimiento ASC, cliente.id ASC" in sentencia
    assert "LIMIT" in sentencia and "OFFSET" in sentencia
    parametros = list(consulta.compile().params.values())
    assert parametros[-2:] == [5, 10]


def test_listar_alertas_expone_pagina_por_ambos_roles(api_rol, monkeypatch):
    client, _ = api_rol
    from app.services import cliente as service

    capturado = {}

    def listar(session, offset, limit):
        capturado.update({"offset": offset, "limit": limit})
        return {
            "items": [
                {
                    "cliente": _cliente(vencimiento=date(2026, 11, 20)),
                    "estado": "POR_VENCER",
                }
            ],
            "total": 1,
            "offset": offset,
            "limit": limit,
        }

    monkeypatch.setattr(service, "listar_alertas", listar)

    response = client.get("/clientes/mensualidad/alertas?offset=2&limit=7")

    assert response.status_code == 200
    assert capturado == {"offset": 2, "limit": 7}
    body = response.json()
    assert body["total"] == 1
    assert body["offset"] == 2
    assert body["limit"] == 7
    assert body["items"][0]["estado"] == "POR_VENCER"
    assert body["items"][0]["cliente"]["fecha_vencimiento"] == "2026-11-20"


@pytest.mark.parametrize("params", [{"limit": 101}, {"limit": 0}, {"offset": -1}])
def test_alertas_rechaza_paginacion_invalida(api_rol, params):
    client, _ = api_rol
    assert client.get("/clientes/mensualidad/alertas", params=params).status_code == 422


def test_get_mensualidad_por_ambos_roles(api_rol, monkeypatch):
    client, _ = api_rol
    from app.services import cliente as service

    capturado = {}

    def obtener(session, cliente_id):
        capturado["cliente_id"] = cliente_id
        return {
            "cliente": _cliente(vencimiento=date(2026, 11, 10)),
            "estado": "VENCIDA",
        }

    monkeypatch.setattr(service, "get_mensualidad", obtener)

    response = client.get("/clientes/1/mensualidad")

    assert response.status_code == 200
    assert capturado == {"cliente_id": 1}
    body = response.json()
    assert body["estado"] == "VENCIDA"
    assert body["cliente"]["id"] == 1
    assert body["cliente"]["fecha_vencimiento"] == "2026-11-10"


def test_get_mensualidad_traduce_cliente_no_encontrado(api_rol, monkeypatch):
    client, _ = api_rol
    from app.services import cliente as service

    def fallar(session, cliente_id):
        raise service.ClienteError(404, "Cliente no encontrado.")

    monkeypatch.setattr(service, "get_mensualidad", fallar)

    response = client.get("/clientes/99/mensualidad")

    assert response.status_code == 404
    assert response.json() == {"detail": "Cliente no encontrado."}


def test_mensualidad_y_alertas_requieren_autenticacion():
    with TestClient(app) as client:
        assert client.get("/clientes/1/mensualidad").status_code == 401
        assert client.get("/clientes/mensualidad/alertas").status_code == 401


def test_openapi_expone_mensualidad_y_alertas():
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    assert "get" in schema["paths"]["/clientes/{id}/mensualidad"]
    assert "get" in schema["paths"]["/clientes/mensualidad/alertas"]
    assert "MensualidadRespuesta" in schema["components"]["schemas"]
    assert "ClientesMensualidadPagina" in schema["components"]["schemas"]
