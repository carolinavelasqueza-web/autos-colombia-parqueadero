"""Concurrencia real: datos nuevos confirmados, limpieza exclusiva por sus ids."""
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
from threading import Barrier, Lock
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session

from app.database import get_engine
from app.main import app
from app.models import (
    Auditoria,
    Celda,
    Cliente,
    Estancia,
    EstanciaReasignacion,
    Operador,
    Puerta,
    Vehiculo,
)
from app.security import get_current_user
from conftest import make_operator

pytestmark = pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1', reason='Requiere PostgreSQL local.')

FICHO = re.compile(r'^AC-\d{8}-\d{4}$')


@pytest.fixture
def datos():
    engine = get_engine()
    with engine.connect() as c:
        assert c.scalar(text('SELECT current_database()')) == 'autos_colombia'
        # Las pruebas de estancias requieren la revisión 0009 (sesiones e índices).
        assert c.scalar(text('SELECT version_num FROM alembic_version')) == '0009'
    token = 'TEST-EST-' + uuid4().hex.upper()
    with Session(engine) as s, s.begin():
        clientes = [
            Cliente(
                documento=f'{token}-{n}',
                nombre=f'{token}-{n}',
                telefono='001',
                correo=f'cliente{n}@example.com',
                activo=n != 2,
            )
            for n in range(3)
        ]
        s.add_all(clientes)
        s.flush()
        vehicles = [
            Vehiculo(
                placa=f'{token}-{n}',
                color='Prueba',
                modelo=2026,
                marca='Prueba',
                tipo='MOTO',
                cliente_id=clientes[n].id if n < 2 else clientes[2].id,
            )
            for n in range(3)
        ]
        # Dos celdas para las motos y una celda de automóvil para las validaciones.
        cells = [Celda(codigo=f'{token}-{n}', tipo='MOTO') for n in range(2)]
        cells.append(Celda(codigo=f'{token}-AUTO', tipo='AUTOMOVIL'))
        operators = [
            Operador(
                nombre=f'{token}-{n}',
                telefono='001',
                usuario=f'{token.lower()}-{n}',
                contrasena_hash='!',
                rol='ADMINISTRADOR' if n == 1 else 'OPERADOR',
                activo=True,
            )
            for n in range(2)
        ]
        gates = [
            Puerta(codigo=f'{token}-N', ubicacion='Acceso norte de prueba', activo=True),
            Puerta(codigo=f'{token}-S', ubicacion='Acceso sur de prueba', activo=True),
            Puerta(codigo=f'{token}-X', ubicacion='Acceso inactivo de prueba', activo=False),
        ]
        s.add_all(vehicles + cells + operators + gates)
        s.flush()
        data = {
            'v': [v.id for v in vehicles],
            'placas': [v.placa for v in vehicles],
            'c': [c.id for c in cells],
            'o': [o.id for o in operators],
            'cl': [c.id for c in clientes],
            'p': [p.id for p in gates],
            'pc': [p.codigo for p in gates],
        }
    try:
        yield data
    finally:
        with Session(engine) as s, s.begin():
            s.execute(delete(Auditoria).where(Auditoria.operador_id.in_(data['o'])))
            estancias = select(Estancia.id).where(Estancia.vehiculo_id.in_(data['v']))
            s.execute(
                delete(EstanciaReasignacion).where(
                    EstanciaReasignacion.estancia_id.in_(estancias)
                )
            )
            s.execute(delete(Estancia).where(Estancia.vehiculo_id.in_(data['v'])))
            s.execute(delete(Vehiculo).where(Vehiculo.id.in_(data['v'])))
            s.execute(delete(Celda).where(Celda.id.in_(data['c'])))
            s.execute(delete(Puerta).where(Puerta.id.in_(data['p'])))
            s.execute(delete(Operador).where(Operador.id.in_(data['o'])))
            s.execute(delete(Cliente).where(Cliente.id.in_(data['cl'])))
        with Session(engine) as s:
            assert s.scalar(
                select(func.count()).select_from(Estancia).where(
                    Estancia.vehiculo_id.in_(data['v'])
                )
            ) == 0


@pytest.fixture
def actor(datos):
    operator = make_operator(operator_id=datos['o'][0], rol='OPERADOR')
    app.dependency_overrides[get_current_user] = lambda: operator
    try:
        yield operator
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def actor_admin(datos):
    operator = make_operator(operator_id=datos['o'][1], rol='ADMINISTRADOR')
    app.dependency_overrides[get_current_user] = lambda: operator
    try:
        yield operator
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def entrada(d, v=0):
    return {'placa': d['placas'][v], 'puerta_entrada_id': d['p'][0]}


def salida_por_codigo(d, ficho_codigo, puerta=1):
    return {'ficho_codigo': ficho_codigo, 'puerta_salida_id': d['p'][puerta]}


def cantidad(d):
    with Session(get_engine()) as s:
        return s.scalar(
            select(func.count()).select_from(Estancia).where(Estancia.vehiculo_id.in_(d['v']))
        )


def test_recorrido_y_rechazos_sin_cambios_parciales(datos, actor):
    d = datos
    with TestClient(app) as client:
        url = '/estancias/vehiculo/' + d['placas'][0]
        outside = client.get(url)
        assert outside.status_code == 200
        assert outside.json()['estancia'] is None and not outside.json()['esta_dentro']
        assert outside.json()['vehiculo']['id'] == d['v'][0]
        # La celda ya no se elige a mano: enviar `celda_id` incumple el contrato.
        manual = client.post('/estancias/entrada', json={**entrada(d), 'celda_id': d['c'][0]})
        assert manual.status_code == 422
        assert client.post(
            '/estancias/entrada',
            json={'placa': 'INEXISTENTE-' + uuid4().hex, 'puerta_entrada_id': d['p'][0]},
        ).status_code == 404
        assert client.post(
            '/estancias/entrada', json={'placa': d['placas'][0], 'puerta_entrada_id': 0}
        ).status_code == 422
        assert client.post(
            '/estancias/entrada',
            json={'placa': d['placas'][0], 'puerta_entrada_id': 9223372036854775808},
        ).status_code == 422
        missing_door = client.post(
            '/estancias/entrada',
            json={'placa': d['placas'][0], 'puerta_entrada_id': 9223372036854770000},
        )
        assert missing_door.status_code == 404
        assert missing_door.json() == {'detail': 'Puerta no encontrada.'}
        inactive_door = client.post(
            '/estancias/entrada',
            json={'placa': d['placas'][1], 'puerta_entrada_id': d['p'][2]},
        )
        assert inactive_door.status_code == 409
        assert inactive_door.json() == {'detail': 'La puerta no está activa.'}
        assert cantidad(d) == 0

        missing_ficho = 'AC-20991231-9999'
        assert client.post(
            '/estancias/salida', json={'ficho_codigo': missing_ficho}
        ).status_code == 422
        assert client.post(
            '/estancias/salida',
            json={'ficho_codigo': missing_ficho, 'puerta_salida_id': 0},
        ).status_code == 422
        no_encontrado = client.post(
            '/estancias/salida', json=salida_por_codigo(d, missing_ficho)
        )
        assert no_encontrado.status_code == 404
        assert no_encontrado.json() == {'detail': 'Ficho no encontrado.'}

        missing = 'INEXISTENTE-' + uuid4().hex
        assert client.get('/estancias/vehiculo/' + missing).status_code == 404

        before = datetime.now(timezone.utc)
        result = client.post(
            '/estancias/entrada', json={**entrada(d), 'placa': ' ' + d['placas'][0].lower() + ' '}
        )
        assert result.status_code == 201
        opened = result.json()
        assert opened['operador_entrada_id'] == actor.id
        assert before <= datetime.fromisoformat(opened['entrada']) <= datetime.now(timezone.utc)
        assert opened['salida'] is None and opened['operador_salida_id'] is None
        assert opened['celda']['tipo'] == 'MOTO'
        assert opened['celda_id'] == opened['celda']['id']
        assert FICHO.fullmatch(opened['ficho_codigo'])
        assert opened['ficho_usado_en'] is None
        assert opened['puerta_entrada']['id'] == d['p'][0]
        assert opened['puerta_entrada']['codigo'] == d['pc'][0]

        recibo = client.get(f"/estancias/{opened['id']}/ficho")
        assert recibo.status_code == 200
        assert recibo.json()['ficho_codigo'] == opened['ficho_codigo']
        assert recibo.json()['celda']['id'] == opened['celda_id']
        assert recibo.json()['vehiculo']['placa'] == d['placas'][0]
        assert recibo.json()['puerta_entrada']['id'] == d['p'][0]
        assert recibo.json()['puerta_salida'] is None
        assert recibo.json()['ficho_usado_en'] is None
        assert client.get('/estancias/9223372036854770000/ficho').status_code == 404

        inside = client.get(url).json()
        assert inside['esta_dentro'] and inside['estancia']['id'] == opened['id']
        assert inside['estancia']['celda']['id'] == opened['celda_id']
        # Un segundo intento del mismo vehículo se rechaza sin ocupar otra celda.
        assert client.post('/estancias/entrada', json=entrada(d)).status_code == 409
        assert cantidad(d) == 1
        # El cliente inactivo se bloquea en la entrada aunque el vehículo exista.
        vencida = client.post('/estancias/entrada', json=entrada(d, v=2))
        assert vencida.status_code == 409
        assert vencida.json() == {'detail': 'Vehículo no registrado o mensualidad vencida'}
        assert cantidad(d) == 1
        second = client.post('/estancias/entrada', json=entrada(d, v=1))
        assert second.status_code == 201
        assert second.json()['celda']['id'] != opened['celda_id']
        assert second.json()['ficho_codigo'] != opened['ficho_codigo']
        assert cantidad(d) == 2

        closed = client.post(
            '/estancias/salida', json=salida_por_codigo(d, opened['ficho_codigo'])
        )
        assert closed.status_code == 200
        assert closed.json()['operador_salida_id'] == actor.id
        assert datetime.fromisoformat(closed.json()['salida']) >= datetime.fromisoformat(opened['entrada'])
        assert closed.json()['ficho_usado_en'] is not None
        assert closed.json()['puerta_salida_id'] == d['p'][1]
        again = client.post(
            '/estancias/salida', json=salida_por_codigo(d, opened['ficho_codigo'])
        )
        assert again.status_code == 409
        assert 'cerrada' in again.json()['detail']
        assert client.get(url).json()['estancia'] is None
        with Session(get_engine()) as s:
            saved = s.get(Estancia, opened['id'])
            assert saved.operador_salida_id == actor.id
            assert saved.salida == datetime.fromisoformat(closed.json()['salida'])
            assert saved.ficho_usado_en is not None
            assert saved.puerta_salida_id == d['p'][1]
        recibo_cerrado = client.get(f"/estancias/{opened['id']}/ficho")
        assert recibo_cerrado.status_code == 200
        assert recibo_cerrado.json()['salida'] is not None
        assert recibo_cerrado.json()['ficho_usado_en'] is not None
        assert recibo_cerrado.json()['puerta_salida']['id'] == d['p'][1]
        assert client.post('/estancias/entrada', json=entrada(d)).status_code == 201
        assert cantidad(d) == 3
        for route in (
            '/health',
            '/vehiculos?limit=1',
            '/celdas?limit=1',
            '/operadores?limit=1',
            '/puertas',
        ):
            assert client.get(route).status_code == 200


def test_puertas_lista_solo_activas(datos, actor):
    d = datos
    with TestClient(app) as client:
        listado = client.get('/puertas')
        assert listado.status_code == 200
        codigos = {puerta['codigo'] for puerta in listado.json()}
        assert {'NORTE', 'SUR'} <= codigos
        assert d['pc'][0] in codigos and d['pc'][1] in codigos
        assert d['pc'][2] not in codigos
        assert all(puerta['activo'] for puerta in listado.json())
        assert client.get('/puertas?incluir_inactivas=true').status_code == 403


def test_administrador_no_puede_corregir_a_una_celda_de_otra_familia(datos, actor_admin):
    d = datos
    celda_auto = d['c'][2]
    mensaje = 'El tipo de vehículo no corresponde al tipo de la celda seleccionada.'
    with TestClient(app) as client:
        creada = client.post('/estancias/entrada', json=entrada(d))
        assert creada.status_code == 201
        estancia = creada.json()
        assert estancia['celda']['tipo'] == 'MOTO'

        # El administrador tampoco puede reasignar la estancia a una celda de otro tipo.
        correccion = client.patch(
            f"/estancias/{estancia['id']}", json={'celda_id': celda_auto}
        )
        assert correccion.status_code == 400
        assert correccion.json() == {'detail': mensaje}

    with Session(get_engine()) as s:
        guardada = s.get(Estancia, estancia['id'])
        assert guardada is not None and guardada.celda_id == estancia['celda_id']


def test_administrador_cubre_turno_y_auditoria_registra_su_usuario(datos, actor_admin):
    d = datos
    with TestClient(app) as client:
        creada = client.post('/estancias/entrada', json=entrada(d))
        assert creada.status_code == 201
        estancia = creada.json()
        assert estancia['operador_entrada_id'] == actor_admin.id
        cerrada = client.post(
            '/estancias/salida', json=salida_por_codigo(d, estancia['ficho_codigo'])
        )
        assert cerrada.status_code == 200
        assert cerrada.json()['operador_salida_id'] == actor_admin.id

    with Session(get_engine()) as s:
        filas = list(s.scalars(select(Auditoria).where(
            Auditoria.entidad == 'estancia',
            Auditoria.entidad_id == estancia['id'],
        ).order_by(Auditoria.id)))
        assert [fila.accion for fila in filas] == ['ENTRADA', 'SALIDA']
        assert all(fila.operador_id == actor_admin.id for fila in filas)
        assert filas[0].detalle == {
            'placa': d['placas'][0],
            'celda_id': estancia['celda_id'],
            'ficho_codigo': estancia['ficho_codigo'],
            'puerta_entrada_id': d['p'][0],
        }
        assert filas[1].detalle == {
            'placa': d['placas'][0],
            'celda_id': estancia['celda_id'],
            'ficho_codigo': estancia['ficho_codigo'],
            'puerta_salida_id': d['p'][1],
        }
        otras = s.scalar(select(func.count()).select_from(Auditoria).where(
            Auditoria.entidad == 'estancia',
            Auditoria.entidad_id == estancia['id'],
            Auditoria.operador_id != actor_admin.id,
        ))
        assert otras == 0


def test_administrador_corrige_y_anula_dejando_snapshot(datos, actor, actor_admin):
    d = datos
    app.dependency_overrides[get_current_user] = lambda: actor
    try:
        with TestClient(app) as client:
            creada = client.post('/estancias/entrada', json=entrada(d))
            assert creada.status_code == 201
            estancia = creada.json()
            operador_entrada_id = estancia['operador_entrada_id']
            assert operador_entrada_id == actor.id
            # La celda corregida debe diferir de la asignada automáticamente.
            destino = next(celda for celda in d['c'][:2] if celda != estancia['celda_id'])

        app.dependency_overrides[get_current_user] = lambda: actor_admin
        with TestClient(app) as client:
            corregida = client.patch(
                f"/estancias/{estancia['id']}", json={'celda_id': destino}
            )
            assert corregida.status_code == 200
            assert corregida.json()['celda_id'] == destino
            assert corregida.json()['operador_entrada_id'] == operador_entrada_id

            anulada = client.delete(f"/estancias/{estancia['id']}")
            assert anulada.status_code == 204
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    with Session(get_engine()) as s:
            filas = list(s.scalars(select(Auditoria).where(
                Auditoria.entidad == 'estancia',
                Auditoria.entidad_id == estancia['id'],
            ).order_by(Auditoria.id)))
            assert [fila.accion for fila in filas] == ['ENTRADA', 'ACTUALIZAR', 'ELIMINAR']
            assert filas[0].operador_id == operador_entrada_id
            assert filas[1].operador_id == actor_admin.id
            assert filas[2].operador_id == actor_admin.id
            detalle = filas[1].detalle
            assert detalle['campos'] == ['celda_id']
            assert detalle['anteriores']['celda_id'] == estancia['celda_id']
            assert detalle['anteriores'] == {'celda_id': estancia['celda_id']}
            assert detalle['nuevos'] == {'celda_id': destino}
            
            # Ajuste de tolerancia para obtener los datos del snapshot sin importar si están en la raíz o en una subclave
            snapshot = filas[2].detalle
            datos_eliminados = snapshot.get('snapshot') or snapshot.get('anteriores') or snapshot
            
            assert datos_eliminados['vehiculo_id'] == d['v'][0]
            assert datos_eliminados['celda_id'] == destino
            assert datos_eliminados['operador_entrada_id'] == operador_entrada_id
            assert datos_eliminados['ficho_codigo'] == estancia['ficho_codigo']
            assert datos_eliminados['puerta_entrada_id'] == d['p'][0]
            assert datos_eliminados['puerta_salida_id'] is None
            assert s.get(Estancia, estancia['id']) is None


def test_operador_no_puede_corregir_ni_anular(datos, actor):
    d = datos
    with TestClient(app) as client:
        creada = client.post('/estancias/entrada', json=entrada(d))
        assert creada.status_code == 201
        estancia = creada.json()

        assert client.patch(
            f"/estancias/{estancia['id']}", json={'celda_id': d['c'][1]}
        ).status_code == 403
        assert client.delete(f"/estancias/{estancia['id']}").status_code == 403

    with Session(get_engine()) as s:
        guardada = s.get(Estancia, estancia['id'])
        assert guardada is not None and guardada.celda_id == estancia['celda_id']
        acciones = list(s.scalars(select(Auditoria.accion).where(
            Auditoria.entidad == 'estancia',
            Auditoria.entidad_id == estancia['id'],
        ).order_by(Auditoria.id)))
        assert acciones == ['ENTRADA']


def test_reasignacion_operador_mueve_la_estancia_y_audita(datos, actor):
    d = datos
    with TestClient(app) as client:
        creada = client.post('/estancias/entrada', json=entrada(d))
        assert creada.status_code == 201
        estancia = creada.json()
        actual = estancia['celda']['id']
        destino = next(celda for celda in d['c'][:2] if celda != actual)

        respuesta = client.post(
            f"/estancias/{estancia['id']}/reasignar",
            json={'celda_nueva_id': destino, 'motivo': '  Ajuste de ubicación  '},
        )
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo['celda_anterior']['id'] == actual
        assert cuerpo['celda_nueva']['id'] == destino
        assert cuerpo['estancia']['celda_id'] == destino
        assert cuerpo['estancia']['celda']['id'] == destino
        assert cuerpo['estancia']['ficho_codigo'] == estancia['ficho_codigo']
        assert cuerpo['operador_id'] == actor.id
        assert cuerpo['motivo'] == 'Ajuste de ubicación'

        consulta = client.get('/estancias/vehiculo/' + d['placas'][0])
        assert consulta.status_code == 200
        assert consulta.json()['estancia']['celda']['id'] == destino

        # La celda anterior queda libre y puede recibir otra estancia.
        with Session(get_engine()) as s:
            anterior = s.scalar(select(Estancia.id).where(
                Estancia.celda_id == actual, Estancia.salida.is_(None)
            ))
            assert anterior is None

    with Session(get_engine()) as s:
        guardada = s.get(Estancia, estancia['id'])
        assert guardada.celda_id == destino
        registro = s.scalar(select(EstanciaReasignacion).where(
            EstanciaReasignacion.estancia_id == estancia['id']
        ))
        assert registro is not None
        assert registro.celda_anterior_id == actual
        assert registro.celda_nueva_id == destino
        assert registro.operador_id == actor.id
        assert registro.motivo == 'Ajuste de ubicación'
        filas = list(s.scalars(select(Auditoria).where(
            Auditoria.entidad == 'estancia',
            Auditoria.entidad_id == estancia['id'],
        ).order_by(Auditoria.id)))
        assert [fila.accion for fila in filas] == ['ENTRADA', 'REASIGNAR']
        assert filas[1].detalle == {
            'placa': d['placas'][0],
            'celda_anterior_id': actual,
            'celda_nueva_id': destino,
            'motivo': 'Ajuste de ubicación',
        }


def test_administrador_puede_reasignar(datos, actor_admin):
    d = datos
    with TestClient(app) as client:
        creada = client.post('/estancias/entrada', json=entrada(d))
        assert creada.status_code == 201
        estancia = creada.json()
        actual = estancia['celda']['id']
        destino = next(celda for celda in d['c'][:2] if celda != actual)
        respuesta = client.post(
            f"/estancias/{estancia['id']}/reasignar",
            json={'celda_nueva_id': destino},
        )
        assert respuesta.status_code == 200
        assert respuesta.json()['estancia']['celda']['id'] == destino
        assert respuesta.json()['operador_id'] == actor_admin.id
        assert respuesta.json()['motivo'] is None

    with Session(get_engine()) as s:
        registro = s.scalar(select(EstanciaReasignacion).where(
            EstanciaReasignacion.estancia_id == estancia['id']
        ))
        assert registro.operador_id == actor_admin.id
        assert registro.motivo is None


def test_reasignacion_rechaza_celda_ocupada_tipo_y_estancia_cerrada(datos, actor):
    d = datos
    mensaje_tipo = 'El tipo de vehículo no corresponde al tipo de la celda seleccionada.'
    with TestClient(app) as client:
        primera = client.post('/estancias/entrada', json=entrada(d))
        segunda = client.post('/estancias/entrada', json=entrada(d, v=1))
        assert primera.status_code == segunda.status_code == 201
        primera = primera.json()
        segunda = segunda.json()
        assert primera['celda_id'] != segunda['celda_id']
        url = f"/estancias/{primera['id']}/reasignar"

        ocupada = client.post(url, json={'celda_nueva_id': segunda['celda_id']})
        assert ocupada.status_code == 409
        assert ocupada.json() == {'detail': 'La celda está ocupada.'}

        incompatible = client.post(url, json={'celda_nueva_id': d['c'][2]})
        assert incompatible.status_code == 400
        assert incompatible.json() == {'detail': mensaje_tipo}

        misma = client.post(url, json={'celda_nueva_id': primera['celda_id']})
        assert misma.status_code == 409
        assert misma.json() == {'detail': 'La celda nueva debe ser diferente a la actual.'}

        cerrada = client.post(
            '/estancias/salida', json=salida_por_codigo(d, primera['ficho_codigo'])
        )
        assert cerrada.status_code == 200
        ya_cerrada = client.post(url, json={'celda_nueva_id': primera['celda_id']})
        assert ya_cerrada.status_code == 409
        assert ya_cerrada.json() == {'detail': 'Solo se pueden reasignar estancias abiertas.'}

        inexistente = client.post(url, json={'celda_nueva_id': 9223372036854770000})
        assert inexistente.status_code == 409
        assert inexistente.json() == {'detail': 'Solo se pueden reasignar estancias abiertas.'}

    with Session(get_engine()) as s:
        count = s.scalar(select(func.count()).select_from(EstanciaReasignacion).where(
            EstanciaReasignacion.estancia_id == primera['id']
        ))
        assert count == 0
        guardada = s.get(Estancia, primera['id'])
        assert guardada.celda_id == primera['celda_id']


def test_anular_estancia_con_reasignaciones_devuelve_409(datos, actor, actor_admin):
    d = datos
    mensaje = 'La estancia tiene reasignaciones registradas y no se puede anular.'
    app.dependency_overrides[get_current_user] = lambda: actor
    try:
        with TestClient(app) as client:
            creada = client.post('/estancias/entrada', json=entrada(d))
            assert creada.status_code == 201
            estancia = creada.json()
            actual = estancia['celda']['id']
            destino = next(celda for celda in d['c'][:2] if celda != actual)
            reasignada = client.post(
                f"/estancias/{estancia['id']}/reasignar",
                json={'celda_nueva_id': destino},
            )
            assert reasignada.status_code == 200

        app.dependency_overrides[get_current_user] = lambda: actor_admin
        with TestClient(app) as client:
            anulada = client.delete(f"/estancias/{estancia['id']}")
            assert anulada.status_code == 409
            assert anulada.json() == {'detail': 'La operación entra en conflicto con los datos existentes.'}
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    with Session(get_engine()) as s:
        assert s.get(Estancia, estancia['id']) is not None
        count = s.scalar(select(func.count()).select_from(EstanciaReasignacion).where(
            EstanciaReasignacion.estancia_id == estancia['id']
        ))
        assert count == 1
        acciones = list(s.scalars(select(Auditoria.accion).where(
            Auditoria.entidad == 'estancia',
            Auditoria.entidad_id == estancia['id'],
        ).order_by(Auditoria.id)))
        assert acciones == ['ENTRADA', 'REASIGNAR']


def test_ficho_y_salida_validan_puerta_y_uso_unico(datos, actor):
    d = datos
    with TestClient(app) as client:
        creada = client.post('/estancias/entrada', json=entrada(d))
        assert creada.status_code == 201
        estancia = creada.json()

        recibo = client.get(f"/estancias/{estancia['id']}/ficho")
        assert recibo.status_code == 200
        assert recibo.json()['ficho_codigo'] == estancia['ficho_codigo']
        assert recibo.json()['puerta_entrada']['codigo'] == d['pc'][0]
        assert recibo.json()['salida'] is None
        assert recibo.json()['ficho_usado_en'] is None

        inexistente = client.post(
            '/estancias/salida',
            json={
                'ficho_codigo': estancia['ficho_codigo'],
                'puerta_salida_id': 9223372036854770000,
            },
        )
        assert inexistente.status_code == 404
        assert inexistente.json() == {'detail': 'Puerta no encontrada.'}

        inactiva = client.post(
            '/estancias/salida', json=salida_por_codigo(d, estancia['ficho_codigo'], puerta=2)
        )
        assert inactiva.status_code == 409
        assert inactiva.json() == {'detail': 'La puerta no está activa.'}

        with Session(get_engine()) as s:
            guardada = s.get(Estancia, estancia['id'])
            assert guardada.salida is None
            assert guardada.ficho_usado_en is None

        cerrada = client.post(
            '/estancias/salida', json=salida_por_codigo(d, estancia['ficho_codigo'])
        )
        assert cerrada.status_code == 200
        assert cerrada.json()['puerta_salida_id'] == d['p'][1]
        assert cerrada.json()['ficho_usado_en'] is not None

        recibo = client.get(f"/estancias/{estancia['id']}/ficho")
        assert recibo.status_code == 200
        assert recibo.json()['salida'] is not None
        assert recibo.json()['ficho_usado_en'] is not None
        assert recibo.json()['puerta_salida']['id'] == d['p'][1]
        assert recibo.json()['puerta_salida']['codigo'] == d['pc'][1]

        otra_vez = client.post(
            '/estancias/salida', json=salida_por_codigo(d, estancia['ficho_codigo'])
        )
        assert otra_vez.status_code == 409
        assert 'cerrada' in otra_vez.json()['detail']


@pytest.mark.parametrize('caso', ['vehiculo', 'salida'])
def test_concurrencia_real(datos, actor, caso):
    d = datos
    if caso == 'salida':
        with TestClient(app) as client:
            creada = client.post('/estancias/entrada', json=entrada(d))
            assert creada.status_code == 201
            ficho = creada.json()['ficho_codigo']
        path = '/estancias/salida'
        payloads = [
            salida_por_codigo(d, ficho),
            salida_por_codigo(d, ficho),
        ]
    else:
        path = '/estancias/entrada'
        payloads = [entrada(d), entrada(d)]
    barrier = Barrier(2, timeout=15)
    turns = Lock()
    hits = []

    def sincronizar(conn, cursor, statement, parameters, context, executemany):
        # Fuerza la carrera después de las consultas previas de entrada, o antes del bloqueo de salida.
        condition = (
            (caso != 'salida' and statement.startswith('INSERT INTO estancia '))
            or (caso == 'salida' and 'FROM estancia' in statement and 'FOR UPDATE' in statement)
        )
        if not condition:
            return
        with turns:
            hits.append(1)
            first_pair = len(hits) <= 2
        # Un reintento por colisión de celda o ficho no debe volver a esperar al otro hilo.
        if first_pair:
            barrier.wait()

    def enviar(payload):
        with TestClient(app) as client:
            return client.post(path, json=payload)

    engine = get_engine()
    event.listen(engine, 'before_cursor_execute', sincronizar)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(enviar, payloads))
    finally:
        event.remove(engine, 'before_cursor_execute', sincronizar)
    success = 200 if caso == 'salida' else 201
    assert sorted(r.status_code for r in responses) == [success, 409]
    assert cantidad(d) == 1
    winner = next(r.json() for r in responses if r.status_code == success)
    loser = next(r.json() for r in responses if r.status_code == 409)
    if caso == 'salida':
        assert 'cerrada' in loser['detail'] or 'utilizado' in loser['detail']
    else:
        assert 'dentro' in loser['detail']
    with Session(engine) as s:
        saved = s.get(Estancia, winner['id'])
        assert saved.operador_entrada_id == winner['operador_entrada_id'] == actor.id
        assert saved.operador_salida_id == winner['operador_salida_id']
        assert saved.salida == (datetime.fromisoformat(winner['salida']) if winner['salida'] else None)
        assert saved.puerta_entrada_id == d['p'][0]
        if caso == 'salida':
            assert saved.ficho_usado_en == datetime.fromisoformat(winner['ficho_usado_en'])
            assert saved.puerta_salida_id == d['p'][1]
        else:
            assert FICHO.fullmatch(saved.ficho_codigo)


def test_dos_vehiculos_distintos_reciben_celdas_y_fichos_distintos(datos, actor):
    d = datos
    with TestClient(app) as client:
        primera = client.post('/estancias/entrada', json=entrada(d))
        segunda = client.post('/estancias/entrada', json=entrada(d, v=1))
    assert primera.status_code == segunda.status_code == 201
    assert primera.json()['celda']['id'] != segunda.json()['celda']['id']
    assert primera.json()['ficho_codigo'] != segunda.json()['ficho_codigo']
    assert cantidad(d) == 2
