import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.models import Base, Celda, Cliente, Operador, Vehiculo


def test_normalizes_unique_identifiers_on_creation_and_assignment():
    vehicle = Vehiculo(placa=" \tabc123\n", color="Azul", modelo=2025, marca="Marca", tipo="MOTO")
    cell = Celda(codigo=" a-01 ", tipo="Libre")
    assert vehicle.placa == "ABC123"
    assert cell.codigo == "A-01"
    vehicle.placa = " xyz789 "
    cell.codigo = " b-02 "
    assert vehicle.placa == "XYZ789"
    assert cell.codigo == "B-02"


@pytest.mark.parametrize("model,attribute", [
    (Vehiculo, "placa"), (Vehiculo, "color"), (Vehiculo, "marca"),
    (Vehiculo, "tipo"), (Celda, "codigo"), (Celda, "tipo"),
    (Operador, "nombre"), (Operador, "telefono"),
])
@pytest.mark.parametrize("value", ["", " \t\n", None])
def test_rejects_empty_text(model, attribute, value):
    with pytest.raises(ValueError):
        model(**{attribute: value})


@pytest.mark.parametrize("value", [0, 10000, True, "2025", 2025.5, None])
def test_rejects_invalid_year(value):
    with pytest.raises(ValueError):
        Vehiculo(modelo=value)


@pytest.mark.parametrize("value", ["MOTO", "AUTOMOVIL", "CAMIONETA"])
def test_vehicle_types(value):
    assert Vehiculo(tipo=value).tipo == value


def test_rejects_unknown_type_and_preserves_phone_text():
    with pytest.raises(ValueError):
        Vehiculo(tipo="CAMION")
    assert Operador(telefono="+57 00123").telefono == "+57 00123"
    assert Celda(tipo="Categoría futura").tipo == "Categoría futura"


def test_operator_auth_fields_and_role_validation():
    operator = Operador(
        nombre="Prueba",
        telefono="001",
        usuario=" Admin.User ",
        contrasena_hash="hash",
        rol="ADMINISTRADOR",
        activo=True,
    )
    assert operator.usuario == "admin.user"
    for rol in ("admin", "ROOT", None):
        with pytest.raises(ValueError):
            Operador(rol=rol)
    for activo in (0, 1, "true", None):
        with pytest.raises(ValueError):
            Operador(activo=activo)
    with pytest.raises(ValueError):
        Operador(usuario="ab")
    with pytest.raises(ValueError):
        Operador(contrasena_hash=" \t")


def test_audit_table_structure():
    table = Base.metadata.tables["auditoria"]
    assert {c.name for c in table.c if c.nullable} == {"entidad_id", "detalle"}
    foreign_key = next(iter(table.foreign_keys))
    assert foreign_key.ondelete == "RESTRICT"
    assert {index.name for index in table.indexes} == {
        "ix_auditoria_operador_fecha", "ix_auditoria_entidad_fecha"
    }


def test_required_columns_and_identity():
    for name in ("celda", "operador"):
        table = Base.metadata.tables[name]
        assert all(not column.nullable for column in table.columns)
        assert isinstance(table.c.id.type, sa.BigInteger)
        assert table.c.id.identity.always is True
    cliente = Base.metadata.tables["cliente"]
    assert {column.name for column in cliente.columns if column.nullable} == {
        "fecha_vencimiento"
    }
    assert isinstance(cliente.c.id.type, sa.BigInteger)
    assert cliente.c.id.identity.always is True
    vehicle = Base.metadata.tables["vehiculo"]
    assert {column.name for column in vehicle.columns if column.nullable} == {"cliente_id"}
    assert isinstance(vehicle.c.id.type, sa.BigInteger)
    assert vehicle.c.id.identity.always is True


def test_cliente_validaciones_y_relacion_con_vehiculos():
    cliente = Cliente(
        documento=" 123456 ",
        nombre=" Cliente Prueba ",
        telefono=" +57 00123 ",
        correo=" persona@example.com ",
        activo=True,
    )
    assert cliente.documento == "123456"
    assert cliente.nombre == "Cliente Prueba"
    assert cliente.telefono == "+57 00123"
    assert cliente.correo == "persona@example.com"
    for correo in ("sin-arroba", "a@b", "a @b.com", " "):
        with pytest.raises(ValueError):
            Cliente(
                documento="1",
                nombre="Prueba",
                telefono="001",
                correo=correo,
            )
    for activo in (0, 1, "true", None):
        with pytest.raises(ValueError):
            Cliente(
                documento="1",
                nombre="Prueba",
                telefono="001",
                correo="a@b.co",
                activo=activo,
            )
    mapper = sa.inspect(Vehiculo)
    assert mapper.relationships.cliente.local_columns == {Vehiculo.__table__.c.cliente_id}
    assert mapper.relationships.cliente.mapper.class_ is Cliente
    assert next(iter(Vehiculo.__table__.c.cliente_id.foreign_keys)).ondelete == "RESTRICT"


def test_celda_activo_por_defecto_y_validacion_booleana():
    table = Base.metadata.tables["celda"]
    assert table.c.activo.nullable is False
    assert str(table.c.activo.server_default.arg) == "true"
    assert Celda(activo=True).activo is True
    assert Celda(activo=False).activo is False
    for value in (0, 1, "true", None):
        with pytest.raises(ValueError):
            Celda(activo=value)


def test_migration_matches_models_without_connecting(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "migrations/versions/0001_modelos_iniciales.py"
    spec = importlib.util.spec_from_file_location("initial_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    metadata = sa.MetaData()
    monkeypatch.setattr(migration.op, "create_table", lambda name, *args: sa.Table(name, metadata, *args))
    migration.upgrade()
    assert set(metadata.tables) == {"vehiculo", "celda", "operador"}
    initial_columns = {
        "vehiculo": ["id", "placa", "color", "modelo", "marca", "tipo"],
        "celda": ["id", "codigo", "tipo"],
        "operador": ["id", "nombre", "telefono"],
    }
    initial_unique = {"vehiculo": {("placa",)}, "celda": {("codigo",)}, "operador": set()}
    for name, table in metadata.tables.items():
        model_table = Base.metadata.tables[name]
        assert [c.name for c in table.columns] == initial_columns[name]
        for column in table.columns:
            model_column = model_table.c[column.name]
            assert (str(column.type), column.nullable) == (str(model_column.type), model_column.nullable)

        def constraints(t):
            return {(c.name, str(c.sqltext)) for c in t.constraints if isinstance(c, sa.CheckConstraint)}
        migrated_names = {c.name for c in table.constraints if isinstance(c, sa.CheckConstraint)}
        assert constraints(table) == {
            item for item in constraints(model_table) if item[0] in migrated_names
        }

        def unique_columns(t):
            return {tuple(c.columns.keys()) for c in t.constraints if isinstance(c, sa.UniqueConstraint)}
        assert unique_columns(table) == initial_unique[name]
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert "BIGINT GENERATED ALWAYS AS IDENTITY" in ddl
