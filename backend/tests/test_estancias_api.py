from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
import pytest

from app.database import get_session
from app.main import app
from app.models import Puerta
from app.schemas.celda import CeldaRespuesta
from app.schemas.estancia import (
    EstanciaAbiertaRespuesta,
    EstanciaRespuesta,
    FichoRespuesta,
    ReasignacionRespuesta,
)
from app.schemas.puerta import PuertaRespuesta
from app.schemas.vehiculo import VehiculoRespuesta
from app.security import get_current_user
from app.services.estancia import ServicioEstancia
from app.services.reasignacion import ServicioReasignacion
from conftest import make_operator


@pytest.fixture(autouse=True)
def authenticated(authenticate):
    authenticate()
    session = MagicMock()

    def override():
        yield session

    app.dependency_overrides[get_session] = override
    yield
    app.dependency_overrides.pop(get_session, None)


def test_openapi_y_salud():
    with TestClient(app) as client:
        schema = client.get('/openapi.json').json()
        for path, method in [
            ('/estancias/entrada', 'post'),
            ('/estancias/salida', 'post'),
            ('/estancias/vehiculo/{placa}', 'get'),
            ('/estancias/{id}/ficho', 'get'),
            ('/estancias/{id}/reasignar', 'post'),
            ('/estancias/{id}', 'patch'),
            ('/estancias/{id}', 'delete'),
            ('/puertas', 'get'),
        ]:
            assert method in schema['paths'][path]
        assert client.get('/health').json() == {'status': 'ok'}


@pytest.mark.parametrize('payload', [
    {},
    {'placa': ' '},
    {'placa': None, 'puerta_entrada_id': 1},
    {'placa': 'TEST', 'puerta_entrada_id': 0},
    {'placa': 'TEST', 'puerta_entrada_id': True},
    {'placa': 'TEST', 'puerta_entrada_id': '1'},
    {'placa': 'TEST', 'puerta_entrada_id': 9223372036854775808},
    {'placa': 'TEST', 'puerta_entrada_id': 1, 'celda_id': 1},
    {'placa': 'TEST', 'puerta_entrada_id': 1, 'ficho_codigo': 'AC-20260101-0001'},
])
def test_entrada_invalida(payload):
    with TestClient(app) as client:
        assert client.post('/estancias/entrada', json=payload).status_code == 422


def test_salida_exige_ficho_y_puerta_sin_campos_extra():
    base = {'ficho_codigo': 'AC-20260101-0001', 'puerta_salida_id': 1}
    with TestClient(app) as client:
        for extra in (
            {'placa': 'TEST'}, {'celda_id': 1}, {'salida': '2026-01-01'},
            {'id': 1}, {'operador_id': 1},
        ):
            assert client.post('/estancias/salida', json={**base, **extra}).status_code == 422
        for invalido in (
            {'ficho_codigo': 'ABC'},
            {'ficho_codigo': 'AC-2026-0001'},
            {'ficho_codigo': ' '},
            {'ficho_codigo': 'AC-20260101-00001'},
            {'puerta_salida_id': 0},
            {'puerta_salida_id': True},
        ):
            assert client.post(
                '/estancias/salida', json={**base, **invalido}
            ).status_code == 422
        assert client.get('/estancias/vehiculo/%20%20').status_code == 422


@pytest.mark.parametrize("rol", ["ADMINISTRADOR", "OPERADOR"])
def test_entrada_y_salida_usan_al_usuario_autenticado(monkeypatch, rol):
    actor = make_operator(operator_id=31, rol=rol)
    app.dependency_overrides[get_current_user] = lambda: actor
    ahora = datetime.now(timezone.utc)
    capturados = []

    def entrada(self, data, operador):
        capturados.append(("ENTRADA", operador, data))
        return EstanciaAbiertaRespuesta(
            id=1,
            vehiculo_id=1,
            celda_id=1,
            entrada=ahora,
            salida=None,
            operador_entrada_id=operador.id,
            operador_salida_id=None,
            celda=CeldaRespuesta(id=1, codigo="C-01", tipo="AUTOMOVIL", activo=True),
        )

    def salida(self, data, operador):
        capturados.append(("SALIDA", operador, data))
        return EstanciaRespuesta(
            id=1,
            vehiculo_id=1,
            celda_id=1,
            entrada=ahora,
            salida=ahora,
            operador_entrada_id=operador.id,
            operador_salida_id=operador.id,
        )

    monkeypatch.setattr(ServicioEstancia, "entrada", entrada)
    monkeypatch.setattr(ServicioEstancia, "salida", salida)
    with TestClient(app) as client:
        created = client.post(
            '/estancias/entrada', json={'placa': 'ABC123', 'puerta_entrada_id': 1}
        )
        closed = client.post(
            '/estancias/salida',
            json={'ficho_codigo': 'ac-20260101-0001', 'puerta_salida_id': 2},
        )

    assert created.status_code == 201
    assert closed.status_code == 200
    assert [accion for accion, _operador, _data in capturados] == ["ENTRADA", "SALIDA"]
    assert all(operador is actor for _accion, operador, _data in capturados)
    assert capturados[0][2].puerta_entrada_id == 1
    assert capturados[1][2].ficho_codigo == 'AC-20260101-0001'
    assert capturados[1][2].puerta_salida_id == 2
    assert created.json()['operador_entrada_id'] == actor.id
    assert closed.json()['operador_salida_id'] == actor.id


def test_operador_no_puede_corregir_ni_anular_estancias():
    operador = make_operator(operator_id=32, rol="OPERADOR")
    app.dependency_overrides[get_current_user] = lambda: operador
    with TestClient(app) as client:
        assert client.patch('/estancias/1', json={'celda_id': 2}).status_code == 403
        assert client.delete('/estancias/1').status_code == 403


def test_administrador_corrige_y_anula_con_su_operador_id(monkeypatch):
    actor = make_operator(operator_id=45, rol="ADMINISTRADOR")
    app.dependency_overrides[get_current_user] = lambda: actor
    ahora = datetime.now(timezone.utc)
    capturados = []

    def actualizar(self, estancia_id, data, operador):
        capturados.append(("ACTUALIZAR", estancia_id, data, operador))
        return EstanciaRespuesta(
            id=estancia_id,
            vehiculo_id=1,
            celda_id=data.celda_id,
            entrada=ahora,
            salida=None,
            operador_entrada_id=7,
            operador_salida_id=None,
        )

    def eliminar(self, estancia_id, operador):
        capturados.append(("ELIMINAR", estancia_id, operador))

    monkeypatch.setattr(ServicioEstancia, "actualizar", actualizar)
    monkeypatch.setattr(ServicioEstancia, "eliminar", eliminar)
    with TestClient(app) as client:
        corrected = client.patch('/estancias/9', json={'celda_id': 3})
        deleted = client.delete('/estancias/9')

    assert corrected.status_code == 200
    assert deleted.status_code == 204
    assert [accion for accion, *_resto in capturados] == ["ACTUALIZAR", "ELIMINAR"]
    assert capturados[0][1] == 9 and capturados[0][2].celda_id == 3
    assert capturados[0][3] is actor and capturados[1][2] is actor


@pytest.mark.parametrize('payload', [
    {'vehiculo_id': None},
    {'celda_id': None},
    {'entrada': None},
    {'salida': 'sin-zona'},
    {'entrada': '2026-01-01T00:00:00'},
    {'id': 1},
    {'operador_entrada_id': 1},
    {'operador_salida_id': 1},
    {'desconocido': 1},
])
def test_actualizacion_invalida(payload):
    with TestClient(app) as client:
        assert client.patch('/estancias/1', json=payload).status_code == 422


def test_actualizacion_acepta_salida_nula_para_reabrir(monkeypatch):
    actor = make_operator(operator_id=46, rol="ADMINISTRADOR")
    app.dependency_overrides[get_current_user] = lambda: actor
    recibidos = []

    def actualizar(self, estancia_id, data, operador):
        recibidos.append(data)
        return EstanciaRespuesta(
            id=estancia_id,
            vehiculo_id=1,
            celda_id=1,
            entrada=datetime.now(timezone.utc),
            salida=None,
            operador_entrada_id=7,
            operador_salida_id=None,
        )

    monkeypatch.setattr(ServicioEstancia, "actualizar", actualizar)
    with TestClient(app) as client:
        result = client.patch('/estancias/1', json={'salida': None})
    assert result.status_code == 200
    assert recibidos[0].model_dump(exclude_unset=True) == {'salida': None}

def _puerta(codigo="NORTE", ubicacion="Entrada Norte"):
    return PuertaRespuesta(id=1, codigo=codigo, ubicacion=ubicacion, activo=True)


def test_ficho_devuelve_el_comprobante_para_ambos_roles(monkeypatch):
    ahora = datetime.now(timezone.utc)
    comprobante = FichoRespuesta(
        id=7,
        ficho_codigo="AC-20260101-0007",
        entrada=ahora,
        salida=None,
        ficho_usado_en=None,
        vehiculo=VehiculoRespuesta(
            id=1,
            placa="ABC123",
            color="Azul",
            modelo=2026,
            marca="Marca",
            tipo="MOTO",
            cliente_id=None,
            cliente=None,
        ),
        celda=CeldaRespuesta(id=5, codigo="M-01", tipo="MOTO", activo=True),
        puerta_entrada=_puerta(),
        puerta_salida=None,
        operador_entrada_id=31,
        operador_salida_id=None,
    )
    for rol in ("ADMINISTRADOR", "OPERADOR"):
        actor = make_operator(operator_id=31, rol=rol)
        app.dependency_overrides[get_current_user] = lambda: actor
        monkeypatch.setattr(ServicioEstancia, "ficho", lambda self, estancia_id: comprobante)
        with TestClient(app) as client:
            respuesta = client.get("/estancias/7/ficho")
        assert respuesta.status_code == 200
        assert respuesta.json()["ficho_codigo"] == "AC-20260101-0007"
        assert respuesta.json()["puerta_entrada"]["codigo"] == "NORTE"


def test_ficho_inexistente_devuelve_404(monkeypatch):
    def ficho(self, estancia_id):
        from app.services.estancia import EstanciaError
        raise EstanciaError(404, "Estancia no encontrada.")

    monkeypatch.setattr(ServicioEstancia, "ficho", ficho)
    with TestClient(app) as client:
        assert client.get("/estancias/9/ficho").status_code == 404


def test_reasignacion_disponible_para_operador_y_administrador(monkeypatch):
    ahora = datetime.now(timezone.utc)
    anterior = CeldaRespuesta(id=5, codigo="M-01", tipo="MOTO", activo=True)
    nueva = CeldaRespuesta(id=6, codigo="M-02", tipo="MOTO", activo=True)
    for rol in ("OPERADOR", "ADMINISTRADOR"):
        actor = make_operator(operator_id=33, rol=rol)
        app.dependency_overrides[get_current_user] = lambda: actor
        capturado = {}

        def reasignar(self, estancia_id, data, operador):
            capturado.update(estancia_id=estancia_id, data=data, operador=operador)
            return ReasignacionRespuesta(
                id=1,
                estancia_id=estancia_id,
                celda_anterior=anterior,
                celda_nueva=nueva,
                operador_id=operador.id,
                fecha=ahora,
                motivo=data.motivo,
                estancia=EstanciaAbiertaRespuesta(
                    id=estancia_id,
                    vehiculo_id=1,
                    celda_id=nueva.id,
                    entrada=ahora,
                    salida=None,
                    operador_entrada_id=31,
                    operador_salida_id=None,
                    celda=nueva,
                    puerta_entrada=_puerta(),
                ),
            )

        monkeypatch.setattr(ServicioReasignacion, "reasignar", reasignar)
        with TestClient(app) as client:
            respuesta = client.post(
                "/estancias/7/reasignar",
                json={"celda_nueva_id": 6, "motivo": "  Falla de iluminacion  "},
            )
        assert respuesta.status_code == 200
        assert respuesta.json()["celda_nueva"]["codigo"] == "M-02"
        assert capturado["estancia_id"] == 7
        assert capturado["operador"] is actor
        assert capturado["data"].motivo == "Falla de iluminacion"


def test_reasignacion_rechaza_payload_invalido():
    with TestClient(app) as client:
        assert client.post("/estancias/1/reasignar", json={}).status_code == 422
        assert client.post(
            "/estancias/1/reasignar", json={"celda_nueva_id": 0}
        ).status_code == 422
        assert client.post(
            "/estancias/1/reasignar", json={"celda_nueva_id": 1, "otro": 2}
        ).status_code == 422


def test_puertas_lista_activas_y_protege_inactivas():
    coneccion = MagicMock()
    coneccion.scalars.return_value = [
        Puerta(id=1, codigo="NORTE", ubicacion="Entrada Norte", activo=True)
    ]

    def override():
        yield coneccion

    app.dependency_overrides[get_session] = override
    with TestClient(app) as client:
        listado = client.get("/puertas")
        assert listado.status_code == 200
        assert listado.json()[0]["codigo"] == "NORTE"

    operador = make_operator(operator_id=34, rol="OPERADOR")
    app.dependency_overrides[get_current_user] = lambda: operador
    with TestClient(app) as client:
        assert client.get("/puertas?incluir_inactivas=true").status_code == 403
