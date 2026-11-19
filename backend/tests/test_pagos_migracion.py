import importlib.util
from datetime import date, datetime, timezone
from decimal import Decimal
from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from app.models import Base, Cliente, Pago, PagoDetalle, Tarifa

RAIZ = Path(__file__).resolve().parents[1]


def _cargar_migracion():
    spec = importlib.util.spec_from_file_location(
        "pagos_migration", RAIZ / "migrations/versions/0010_pagos.py"
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _aplicar_migracion(monkeypatch, migration, metadata):
    """Aplica el DDL de la revisión sobre un MetaData en memoria."""

    def create_table(name, *args):
        return sa.Table(name, metadata, *args)

    def add_column(table_name, column):
        metadata.tables[table_name].append_column(column)

    def create_index(name, table_name, columns, **kwargs):
        sa.Index(name, *(metadata.tables[table_name].c[c] for c in columns), **kwargs)

    monkeypatch.setattr(migration.op, "create_table", create_table)
    monkeypatch.setattr(migration.op, "add_column", add_column)
    monkeypatch.setattr(migration.op, "create_index", create_index)
    monkeypatch.setattr(migration.op, "execute", lambda *args, **kwargs: None)
    migration.upgrade()


def _metadata_con_referencias():
    metadata = sa.MetaData()
    sa.Table(
        "cliente",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True),
    )
    sa.Table(
        "operador",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True),
    )
    sa.Table(
        "vehiculo",
        metadata,
        sa.Column("id", sa.BigInteger(), primary_key=True),
    )
    return metadata


def test_revision_y_sql_offline_agrega_sin_destruir():
    migration = _cargar_migracion()
    assert migration.revision == "0010"
    assert migration.down_revision == "0009"

    output = StringIO()
    config = Config(str(RAIZ / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "0009:0010", sql=True)
    sql = output.getvalue()

    assert "ALTER TABLE cliente ADD COLUMN fecha_vencimiento DATE" in sql
    assert "CREATE SEQUENCE pago_recibo_seq" in sql
    assert "CREATE TABLE tarifa" in sql
    assert "CREATE TABLE pago" in sql
    assert "CREATE TABLE pago_detalle" in sql
    assert "NUMERIC(12, 2)" in sql
    assert "CHECK (valor > 0)" in sql
    assert "CHECK (monto > 0)" in sql
    assert "CHECK (meses BETWEEN 1 AND 12)" in sql
    assert "CHECK (periodo_hasta >= periodo_desde)" in sql
    assert (
        "CREATE UNIQUE INDEX uq_tarifa_vigente ON tarifa (tipo) "
        "WHERE vigente_hasta IS NULL" in sql
    )
    assert (
        "CREATE UNIQUE INDEX uq_pago_referencia_vigente ON pago (referencia) "
        "WHERE estado = 'VIGENTE' AND referencia IS NOT NULL" in sql
    )
    assert "ON DELETE RESTRICT" in sql
    assert "DROP" not in sql


def test_migracion_coincide_con_los_modelos(monkeypatch):
    migration = _cargar_migracion()
    metadata = _metadata_con_referencias()
    _aplicar_migracion(monkeypatch, migration, metadata)

    assert {"tarifa", "pago", "pago_detalle"} <= set(metadata.tables)
    assert "fecha_vencimiento" in metadata.tables["cliente"].c
    assert str(metadata.tables["cliente"].c.fecha_vencimiento.type) == "DATE"
    assert metadata.tables["cliente"].c.fecha_vencimiento.nullable is True

    dialect = postgresql.dialect()
    for nombre in ("tarifa", "pago", "pago_detalle"):
        esperado = Base.metadata.tables[nombre]
        actual = metadata.tables[nombre]

        assert [c.name for c in actual.columns] == [c.name for c in esperado.columns]
        for columna in actual.columns:
            modelo = esperado.c[columna.name]
            assert str(columna.type) == str(modelo.type)
            assert columna.nullable == modelo.nullable

        def checks(tabla):
            return {
                (restriccion.name, str(restriccion.sqltext))
                for restriccion in tabla.constraints
                if isinstance(restriccion, sa.CheckConstraint)
            }

        assert checks(actual) == checks(esperado)

        def unicas(tabla):
            return {
                (restriccion.name, tuple(restriccion.columns.keys()))
                for restriccion in tabla.constraints
                if isinstance(restriccion, sa.UniqueConstraint)
            }

        assert unicas(actual) == unicas(esperado)

        assert {str(CreateIndex(indice).compile(dialect=dialect)) for indice in actual.indexes} == {
            str(CreateIndex(indice).compile(dialect=dialect)) for indice in esperado.indexes
        }
        assert all(
            fk.ondelete == "RESTRICT" for fk in actual.foreign_keys
        )


def test_estructura_monetaria_y_fechas():
    tarifa = Base.metadata.tables["tarifa"]
    pago = Base.metadata.tables["pago"]
    detalle = Base.metadata.tables["pago_detalle"]

    for columna in (
        tarifa.c.valor,
        pago.c.monto,
        detalle.c.tarifa_aplicada,
        detalle.c.subtotal,
    ):
        assert isinstance(columna.type, sa.Numeric)
        assert (columna.type.precision, columna.type.scale) == (12, 2)
        assert not isinstance(columna.type, sa.Float)

    assert tarifa.c.vigente_desde.type.timezone is True
    assert tarifa.c.vigente_hasta.type.timezone is True
    assert pago.c.fecha.type.timezone is True
    assert pago.c.anulado_en.type.timezone is True
    assert str(pago.c.estado.server_default.arg) == "'VIGENTE'"
    assert str(pago.c.reactivo_cliente.server_default.arg) == "false"

    assert {c.name for c in pago.c if c.nullable} == {
        "referencia",
        "vencimiento_anterior",
        "motivo",
        "anulado_por",
        "anulado_en",
    }
    assert {c.name for c in tarifa.c if c.nullable} == {"vigente_hasta"}
    assert {c.name for c in detalle.c if c.nullable} == set()


def test_cliente_solo_acepta_fecha_o_nulo():
    cliente = Cliente(
        documento="1",
        nombre="Prueba",
        telefono="001",
        correo="a@b.co",
        fecha_vencimiento=date(2026, 12, 31),
    )
    assert cliente.fecha_vencimiento == date(2026, 12, 31)
    assert Cliente(documento="1", nombre="P", telefono="1", correo="a@b.co").fecha_vencimiento is None
    with pytest.raises(ValueError):
        Cliente(
            documento="1",
            nombre="Prueba",
            telefono="001",
            correo="a@b.co",
            fecha_vencimiento=datetime(2026, 12, 31, 10, tzinfo=timezone.utc),
        )
    with pytest.raises(ValueError):
        Cliente(
            documento="1",
            nombre="Prueba",
            telefono="001",
            correo="a@b.co",
            fecha_vencimiento="2026-12-31",
        )


def test_tarifa_valida_tipo_monto_y_vigencia():
    ahora = datetime(2026, 1, 1, tzinfo=timezone.utc)
    tarifa = Tarifa(tipo="MOTO", valor=Decimal("15000.00"), vigente_desde=ahora)
    assert tarifa.valor == Decimal("15000.00")
    assert Tarifa(tipo="AUTOMOVIL", valor=15000).valor == Decimal("15000")
    assert Tarifa(tipo="CAMIONETA", valor="15000.50").valor == Decimal("15000.50")

    for tipo in ("CAMION", "moto", "", " "):
        with pytest.raises(ValueError):
            Tarifa(tipo=tipo, valor=Decimal("1"))
    for valor in (0, -1, Decimal("0"), 1.5, True, "abc", Decimal("1.001")):
        with pytest.raises(ValueError):
            Tarifa(tipo="MOTO", valor=valor)
    with pytest.raises(ValueError):
        Tarifa(
            tipo="MOTO",
            valor=Decimal("1"),
            vigente_desde=datetime(2026, 1, 1),
        )
    with pytest.raises(ValueError):
        Tarifa(
            tipo="MOTO",
            valor=Decimal("1"),
            vigente_desde=ahora,
            vigente_hasta=datetime(2026, 2, 1),
        )


def test_pago_valida_campos_y_normaliza_referencia():
    base = dict(
        cliente_id=1,
        meses=1,
        metodo="TRANSFERENCIA",
        referencia="  abc-1  ",
        monto=Decimal("150000.00"),
        numero_recibo="RC-000001",
        periodo_desde=date(2026, 1, 1),
        periodo_hasta=date(2026, 2, 1),
        operador_id=1,
        estado="VIGENTE",
        reactivo_cliente=False,
    )
    pago = Pago(**base)
    assert pago.referencia == "ABC-1"
    assert pago.estado == "VIGENTE"
    assert pago.reactivo_cliente is False

    for meses in (0, 13, True, "1"):
        with pytest.raises(ValueError):
            Pago(**{**base, "meses": meses})
    for recibo in ("RC-1", "rc-000001", "RC-0000001"):
        with pytest.raises(ValueError):
            Pago(**{**base, "numero_recibo": recibo})
    for monto in (0, Decimal("0"), 1.5, "x"):
        with pytest.raises(ValueError):
            Pago(**{**base, "monto": monto})
    for metodo in ("CHEQUE", ""):
        with pytest.raises(ValueError):
            Pago(**{**base, "metodo": metodo})
    with pytest.raises(ValueError):
        Pago(**{**base, "referencia": "x" * 101})
    with pytest.raises(ValueError):
        Pago(**{**base, "estado": "PENDIENTE"})
    with pytest.raises(ValueError):
        Pago(**{**base, "reactivo_cliente": 1})
    with pytest.raises(ValueError):
        Pago(**{**base, "fecha": datetime(2026, 1, 1)})
    with pytest.raises(ValueError):
        Pago(**{**base, "periodo_desde": datetime(2026, 1, 1)})


def test_pago_detalle_valida_placa_tipo_y_montos():
    detalle = PagoDetalle(
        pago_id=1,
        vehiculo_id=1,
        placa=" abc123 ",
        tipo="MOTO",
        tarifa_aplicada=Decimal("15000.00"),
        subtotal=Decimal("30000.00"),
    )
    assert detalle.placa == "ABC123"
    for placa in ("", " ", None):
        with pytest.raises(ValueError):
            PagoDetalle(
                pago_id=1,
                vehiculo_id=1,
                placa=placa,
                tipo="MOTO",
                tarifa_aplicada=Decimal("1"),
                subtotal=Decimal("1"),
            )
    with pytest.raises(ValueError):
        PagoDetalle(
            pago_id=1,
            vehiculo_id=1,
            placa="ABC123",
            tipo="CAMION",
            tarifa_aplicada=Decimal("1"),
            subtotal=Decimal("1"),
        )
    for campo in ("tarifa_aplicada", "subtotal"):
        datos = {
            "pago_id": 1,
            "vehiculo_id": 1,
            "placa": "ABC123",
            "tipo": "MOTO",
            "tarifa_aplicada": Decimal("1"),
            "subtotal": Decimal("1"),
        }
        datos[campo] = Decimal("0")
        with pytest.raises(ValueError):
            PagoDetalle(**datos)
