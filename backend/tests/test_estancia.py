from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
import importlib.util

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models import Base, Estancia, Operador

ENTRADA = datetime(2026, 10, 19, 10, tzinfo=timezone.utc)


def test_cerrar_asigna_fecha_relacion_e_id_sin_sesion():
    estancia = Estancia(entrada=ENTRADA)
    operador = Operador(id=7, nombre="Prueba", telefono="001")
    assert estancia.esta_abierta() is True
    # Misma hora absoluta con otro huso: la igualdad está permitida.
    salida = ENTRADA.astimezone(timezone(timedelta(hours=-5)))
    estancia.cerrar(salida, operador)
    assert estancia.esta_abierta() is False
    assert estancia.salida == salida
    assert estancia.operador_salida is operador
    assert estancia.operador_salida_id == 7
    with pytest.raises(ValueError, match="cerrada"):
        estancia.cerrar(ENTRADA + timedelta(hours=1), operador)
    assert estancia.salida == salida


@pytest.mark.parametrize("salida", [None, "2026-10-19", datetime(2026, 10, 19), ENTRADA - timedelta(microseconds=1)])
def test_rechaza_fecha_invalida_sin_cambiar_estado(salida):
    estancia = Estancia(entrada=ENTRADA)
    with pytest.raises(ValueError):
        estancia.cerrar(salida, Operador(id=7))
    assert estancia.esta_abierta()
    assert estancia.operador_salida is None
    assert estancia.operador_salida_id is None


@pytest.mark.parametrize("entrada", [None, datetime(2026, 10, 19)])
def test_cerrar_requiere_entrada_cargada_con_zona(entrada):
    with pytest.raises(ValueError, match="entrada"):
        Estancia(entrada=entrada).cerrar(ENTRADA, Operador(id=7))


@pytest.mark.parametrize("operador", [None, 7, Operador(nombre="Sin persistir", telefono="001")])
def test_operador_invalido_no_deja_cierre_parcial(operador):
    estancia = Estancia(entrada=ENTRADA)
    with pytest.raises(ValueError, match="operador"):
        estancia.cerrar(ENTRADA, operador)
    assert estancia.salida is None
    assert estancia.operador_salida_id is None


def test_relaciones_y_columnas():
    mapper = sa.inspect(Estancia)
    assert mapper.relationships.operador_entrada.local_columns == {Estancia.__table__.c.operador_entrada_id}
    assert mapper.relationships.operador_salida.local_columns == {Estancia.__table__.c.operador_salida_id}
    assert mapper.relationships.puerta_entrada.local_columns == {Estancia.__table__.c.puerta_entrada_id}
    assert mapper.relationships.puerta_salida.local_columns == {Estancia.__table__.c.puerta_salida_id}
    for relation in mapper.relationships:
        assert not relation.cascade.delete and not relation.cascade.delete_orphan
    table = Estancia.__table__
    assert {c.name for c in table.c if c.nullable} == {
        "salida",
        "operador_salida_id",
        "ficho_codigo",
        "ficho_usado_en",
        "puerta_entrada_id",
        "puerta_salida_id",
    }
    assert isinstance(table.c.id.type, sa.BigInteger) and table.c.id.identity.always
    assert table.c.entrada.type.timezone and table.c.salida.type.timezone
    assert str(table.c.entrada.server_default.arg) == "now()"
    assert len(table.foreign_keys) == 6
    assert all(fk.ondelete == "RESTRICT" for fk in table.foreign_keys)


def _cargar_migracion(root: Path, nombre: str, modulo: str):
    spec = importlib.util.spec_from_file_location(
        modulo, root / "migrations/versions" / nombre
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _aplicar_migracion(monkeypatch, migration, metadata):
    """Simula las operaciones DDL de Alembic sobre un MetaData en memoria."""

    def create_table(name, *args):
        return sa.Table(name, metadata, *args)

    def add_column(table_name, column):
        metadata.tables[table_name].append_column(column)

    def create_index(name, table_name, columns, **kwargs):
        sa.Index(
            name, *(metadata.tables[table_name].c[c] for c in columns), **kwargs
        )

    def create_foreign_key(name, source, referent, local_cols, remote_cols, **kwargs):
        metadata.tables[source].append_constraint(
            sa.ForeignKeyConstraint(
                local_cols,
                [f"{referent}.{column}" for column in remote_cols],
                name=name,
                **kwargs,
            )
        )

    def create_unique_constraint(name, table_name, columns):
        metadata.tables[table_name].append_constraint(
            sa.UniqueConstraint(*columns, name=name)
        )

    def create_check_constraint(name, table_name, condition):
        metadata.tables[table_name].append_constraint(
            sa.CheckConstraint(condition, name=name)
        )

    monkeypatch.setattr(migration.op, "create_table", create_table)
    monkeypatch.setattr(migration.op, "add_column", add_column)
    monkeypatch.setattr(migration.op, "create_index", create_index)
    monkeypatch.setattr(migration.op, "create_foreign_key", create_foreign_key)
    monkeypatch.setattr(migration.op, "create_unique_constraint", create_unique_constraint)
    monkeypatch.setattr(migration.op, "create_check_constraint", create_check_constraint)
    monkeypatch.setattr(migration.op, "execute", lambda *args, **kwargs: None)
    migration.upgrade()


def test_migracion_coincide_con_modelo_y_compila_sql(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    metadata = sa.MetaData()
    revisiones = [
        ("0001_modelos_iniciales.py", "initial_tables_migration"),
        ("0002_estancia.py", "estancia_migration"),
        ("0007_fichos.py", "fichos_migration"),
        ("0008_puertas_reasignacion.py", "puertas_migration"),
        ("0009_seguridad_auditoria.py", "seguridad_auditoria_migration"),
    ]
    for nombre, modulo in revisiones:
        _aplicar_migracion(monkeypatch, _cargar_migracion(root, nombre, modulo), metadata)

    fichos = _cargar_migracion(root, "0007_fichos.py", "fichos_migration")
    puertas = _cargar_migracion(root, "0008_puertas_reasignacion.py", "puertas_migration")
    seguridad = _cargar_migracion(
        root, "0009_seguridad_auditoria.py", "seguridad_auditoria_migration"
    )
    assert (fichos.revision, fichos.down_revision) == ("0007", "0006")
    assert (puertas.revision, puertas.down_revision) == ("0008", "0007")
    assert (seguridad.revision, seguridad.down_revision) == ("0009", "0008")

    dialect = postgresql.dialect()

    def ddl_parts(table):
        # El orden de declaración de CHECK/FK no cambia la estructura.
        return sorted(line.strip().rstrip(",") for line in
                      str(CreateTable(table).compile(dialect=dialect)).splitlines())

    for nombre in ("estancia", "puerta", "estancia_reasignacion", "sesion"):
        expected = Base.metadata.tables[nombre]
        actual = metadata.tables[nombre]
        assert ddl_parts(actual) == ddl_parts(expected)
        assert {str(CreateIndex(i).compile(dialect=dialect)) for i in actual.indexes} == {
            str(CreateIndex(i).compile(dialect=dialect)) for i in expected.indexes
        }


def test_alembic_offline_solo_agrega_estancia():
    output = StringIO()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "0001:0002", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE estancia" in sql
    assert "CREATE TABLE vehiculo" not in sql
    assert "DROP TABLE" not in sql
    assert sql.count("WHERE salida IS NULL") == 2
    assert sql.count("ON DELETE RESTRICT") == 4
    assert "TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL" in sql
    assert "CHECK (salida >= entrada)" in sql
    assert "CHECK ((salida IS NULL) = (operador_salida_id IS NULL))" in sql
    assert "CREATE INDEX ix_estancia_vehiculo_entrada ON estancia (vehiculo_id, entrada)" in sql
