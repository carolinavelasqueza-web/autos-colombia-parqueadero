"""Integración optativa sin DDL; todos los datos nuevos se revierten."""
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_engine, get_session
from app.main import app
from app.models import Celda, Estancia, Operador, Puerta, Vehiculo
from app.security import get_current_user
from app.services.auth import hash_password

pytestmark = pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Requiere PostgreSQL local.")


@pytest.fixture
def connection():
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            assert connection.scalar(text("SELECT current_database()")) == "autos_colombia"
            yield connection
        finally:
            transaction.rollback()


def test_celda_schema_and_constraints(connection):
    inspector = inspect(connection)
    columns = {c['name']: c for c in inspector.get_columns('celda')}
    assert set(columns) == {'id', 'codigo', 'tipo', 'activo'}
    assert str(columns['id']['type']) == 'BIGINT'
    assert columns['id']['identity']['always']
    assert all(not c['nullable'] for c in columns.values())
    assert str(columns['activo']['type']) == 'BOOLEAN'
    assert inspector.get_pk_constraint('celda')['constrained_columns'] == ['id']
    assert any(c['column_names'] == ['codigo'] for c in inspector.get_unique_constraints('celda'))
    code = 'SCHEMA-' + uuid4().hex.upper()
    connection.execute(text('INSERT INTO celda(codigo,tipo) VALUES (:code,:type)'), {'code':code,'type':'Libre'})
    for code_value, kind, state in [(code,'Otro','23505'), (' lowercase ','Libre','23514'),
                                    (' \t','Libre','23514'), (code+'X',' \t','23514'),
                                    (None,'Libre','23502'), (code+'Y',None,'23502')]:
        with pytest.raises(IntegrityError) as error:
            with connection.begin_nested():
                connection.execute(text('INSERT INTO celda(codigo,tipo) VALUES (:code,:type)'), {'code':code_value,'type':kind})
        assert error.value.orig.sqlstate == state


def test_crud_celdas(connection):
    with Session(bind=connection, join_transaction_mode='create_savepoint') as session:
        admin = Operador(
            nombre="Admin de prueba",
            telefono="000",
            usuario=f"admin-{uuid4().hex}",
            contrasena_hash=hash_password("clave-segura"),
            rol="ADMINISTRADOR",
            activo=True,
        )
        session.add(admin)
        session.flush()

        def override():
            yield session

        app.dependency_overrides[get_session] = override
        app.dependency_overrides[get_current_user] = lambda: admin
        try:
            with TestClient(app) as client:
                code = 'CELL-' + uuid4().hex.upper()
                payload = {'codigo': f' {code.lower()} ', 'tipo': ' Categoría libre '}
                result = client.post('/celdas', json=payload)
                assert result.status_code == 201
                item = result.json()
                assert item['codigo'] == code and item['tipo'] == 'Categoría libre'
                path = f"/celdas/{item['id']}"
                assert client.get(path).json() == item
                assert client.post('/celdas', json=payload).status_code == 409
                page = client.get('/celdas?offset=0&limit=1')
                assert page.status_code == 200 and len(page.json()['items']) == 1
                assert client.get('/celdas?limit=0').status_code == 422
                for invalid in ({'id':1}, {'codigo':None}, {'tipo':' \t'}, {'tipo':None}):
                    assert client.patch(path, json=invalid).status_code == 422
                assert client.post('/celdas', json={}).status_code == 422
                changed = client.patch(path, json={'tipo':'Otro tipo libre'})
                assert changed.status_code == 200 and changed.json()['tipo'] == 'Otro tipo libre'
                deleted = client.delete(path)
                assert deleted.status_code == 204 and deleted.content == b''
                assert client.get(path).status_code == 404
                assert client.patch(path, json={'tipo':'Libre'}).status_code == 404
                assert client.delete(path).status_code == 404
                assert client.get('/health').json() == {'status':'ok'}
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_session, None)


def test_celda_con_estancia_se_desactiva_y_puede_reactivarse(connection):
    with Session(bind=connection, join_transaction_mode='create_savepoint') as session:
        admin = Operador(
            nombre="Admin de prueba",
            telefono="000",
            usuario=f"admin-{uuid4().hex}",
            contrasena_hash=hash_password("clave-segura"),
            rol="ADMINISTRADOR",
            activo=True,
        )
        puerta = Puerta(codigo=f"NORTE-{uuid4().hex[:6].upper()}", ubicacion="Entrada Norte Test", activo=True)
        session.add_all([admin, puerta])
        session.flush()

        def override():
            yield session

        app.dependency_overrides[get_session] = override
        app.dependency_overrides[get_current_user] = lambda: admin
        try:
            with TestClient(app) as client:
                cliente = client.post(
                    "/clientes",
                    json={
                        "documento": f"DOC-{uuid4().hex}",
                        "nombre": "Cliente de prueba",
                        "telefono": "000",
                        "correo": "cliente@example.com",
                    },
                ).json()
                code = 'CELL-' + uuid4().hex.upper()
                cell = client.post('/celdas', json={'codigo': code, 'tipo': 'MOTO'}).json()
                plate = 'TEST-' + uuid4().hex[:12].upper()
                second_plate = 'TEST-' + uuid4().hex[:12].upper()
                vehicle_ids = []
                for current in (plate, second_plate):
                    created = client.post(
                        '/vehiculos',
                        json={
                            'placa': current,
                            'color': 'Rojo',
                            'modelo': 2026,
                            'marca': 'Prueba',
                            'tipo': 'MOTO',
                            'cliente_id': cliente['id'],
                        },
                    )
                    assert created.status_code == 201
                    vehicle_ids.append(created.json()['id'])
                
                # La estancia se crea directamente para ocupar la celda concreta.
                session.add(
                    Estancia(
                        vehiculo_id=vehicle_ids[0],
                        celda_id=cell['id'],
                        operador_entrada_id=admin.id,
                        puerta_entrada_id=puerta.id,
                        entrada=datetime.now(timezone.utc),
                    )
                )
                session.flush()

                deleted = client.delete(f"/celdas/{cell['id']}")
                assert deleted.status_code == 204
                saved = client.get(f"/celdas/{cell['id']}").json()
                assert saved['activo'] is False

                listing = client.get('/celdas?offset=0&limit=100').json()['items']
                assert cell['id'] not in {item['id'] for item in listing}
                inactive = client.get('/celdas?incluir_inactivas=true&offset=0&limit=100')
                assert inactive.status_code == 200
                assert cell['id'] in {item['id'] for item in inactive.json()['items']}

                # Una celda inactiva no se asigna a nuevas entradas (se especifica puerta_entrada_id obligatorio).
                assigned = client.post(
                    '/estancias/entrada', 
                    json={'placa': second_plate, 'puerta_entrada_id': puerta.id}
                )
                assert assigned.status_code == 201
                assert assigned.json()['celda']['id'] != cell['id']

                reactivated = client.patch(f"/celdas/{cell['id']}", json={'activo': True})
                assert reactivated.status_code == 200
                assert reactivated.json()['activo'] is True
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_session, None)


def test_disponibilidad_cruza_celdas_activas_con_estancias_abiertas(connection):
    token = 'AVL-' + uuid4().hex[:10].upper()
    with Session(bind=connection, join_transaction_mode='create_savepoint') as session:
        admin = Operador(
            nombre=f'{token}-ADMIN',
            telefono='000',
            usuario=f'{token.lower()}-admin',
            contrasena_hash='!',
            rol='ADMINISTRADOR',
            activo=True,
        )
        puerta = Puerta(codigo=f"SUR-{uuid4().hex[:6].upper()}", ubicacion="Entrada Sur Test", activo=True)
        libre = Celda(codigo=f'{token}-1', tipo='AUTOMOVIL')
        ocupada = Celda(codigo=f'{token}-2', tipo='AUTOMOVIL')
        moto = Celda(codigo=f'{token}-3', tipo='MOTO')
        inactiva = Celda(codigo=f'{token}-4', tipo='MOTO', activo=False)
        session.add_all([admin, puerta, libre, ocupada, moto, inactiva])
        session.flush()
        vehiculo = Vehiculo(
            placa=f'{token}-V', color='Rojo', modelo=2026, marca='Prueba', tipo='AUTOMOVIL'
        )
        session.add(vehiculo)
        session.flush()
        session.add(
            Estancia(
                vehiculo_id=vehiculo.id,
                celda_id=ocupada.id,
                operador_entrada_id=admin.id,
                puerta_entrada_id=puerta.id,
                entrada=datetime.now(timezone.utc),
            )
        )
        session.flush()

        def override():
            yield session

        app.dependency_overrides[get_session] = override
        app.dependency_overrides[get_current_user] = lambda: admin
        try:
            with TestClient(app) as client:
                response = client.get('/celdas/disponibilidad')
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    body = response.json()
    por_id = {celda['id']: celda for celda in body['celdas']}
    assert por_id[libre.id]['disponible'] is True
    assert por_id[ocupada.id]['disponible'] is False
    assert por_id[moto.id]['disponible'] is True
    assert inactiva.id not in por_id
    assert body['disponibles'] + body['ocupadas'] == body['total'] == len(body['celdas'])
    assert body['ocupacion_porcentaje'] == round(body['ocupadas'] * 100 / body['total'], 1)
    automoviles = next(item for item in body['por_tipo'] if item['tipo'] == 'AUTOMOVIL')
    assert automoviles['total'] >= 2
    assert automoviles['ocupadas'] >= 1
    assert automoviles['disponibles'] + automoviles['ocupadas'] == automoviles['total']
    assert any(item['tipo'] == 'MOTO' for item in body['por_tipo'])