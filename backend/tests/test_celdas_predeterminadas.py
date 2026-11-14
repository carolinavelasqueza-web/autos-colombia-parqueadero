from io import StringIO
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError

from app import main
from app.celdas_predeterminadas import (
    CELDAS_PREDETERMINADAS,
    CODIGOS_CELDAS_PREDETERMINADAS,
    TOTAL_CELDAS_PREDETERMINADAS,
)
from app.models import Celda
from app.schemas.celda import CeldaActualizar
from app.services import celda as service
from app.services.celda import CeldaError
from app.services.celda_seed import ensure_default_cells


def test_estructura_base_tiene_80_celdas():
    assert TOTAL_CELDAS_PREDETERMINADAS == 80
    assert len(CELDAS_PREDETERMINADAS) == 80
    assert len(CODIGOS_CELDAS_PREDETERMINADAS) == 80
    assert CELDAS_PREDETERMINADAS[0] == ("C-01", "AUTOMOVIL")
    assert CELDAS_PREDETERMINADAS[69] == ("C-70", "AUTOMOVIL")
    assert CELDAS_PREDETERMINADAS[70] == ("M-01", "MOTO")
    assert CELDAS_PREDETERMINADAS[79] == ("M-10", "MOTO")
    assert all(
        codigo == codigo.upper() and codigo == codigo.strip()
        for codigo, _tipo in CELDAS_PREDETERMINADAS
    )


def test_seed_es_idempotente_y_no_sobrescribe_existentes():
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = ["C-01"]

    assert ensure_default_cells(session) == 1
    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (codigo) DO NOTHING" in sql
    session.commit.assert_called_once()


def test_migracion_contiene_las_mismas_80_celdas():
    path = Path(__file__).resolve().parents[1] / "migrations/versions/0004_celdas_predeterminadas.py"
    spec = importlib.util.spec_from_file_location("celdas_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "0004"
    assert migration.down_revision == "0003"
    assert migration.CELDAS == CELDAS_PREDETERMINADAS


def test_migracion_offline_inserta_las_80_celdas_sin_conectar():
    output = StringIO()
    config = Config(
        str(Path(__file__).resolve().parents[1] / "alembic.ini"),
        output_buffer=output,
    )
    command.upgrade(config, "0003:0004", sql=True)
    sql = output.getvalue()
    assert sql.count("('C-") == 70
    assert sql.count("('M-") == 10
    assert "ON CONFLICT (codigo) DO NOTHING" in sql


def test_no_permite_recodificar_una_celda_base():
    session = MagicMock()
    session.get.return_value = Celda(id=1, codigo="C-01", tipo="AUTOMOVIL", activo=True)
    actor = MagicMock(id=1)

    with pytest.raises(CeldaError) as recodificar:
        service.update_cell(session, 1, CeldaActualizar(codigo="X-01"), actor)
    assert recodificar.value.status_code == 409


def test_eliminar_celda_base_la_desactiva_sin_borrarla():
    session = MagicMock()
    cell = Celda(id=1, codigo="C-01", tipo="AUTOMOVIL", activo=True)
    session.get.return_value = cell

    service.delete_cell(session, 1, MagicMock(id=1))

    assert cell.activo is False
    session.delete.assert_not_called()
    session.commit.assert_called_once()


def test_eliminar_celda_adicional_sin_historial_borra_fisicamente():
    session = MagicMock()
    cell = Celda(id=2, codigo="A-01", tipo="Libre", activo=True)
    session.get.return_value = cell
    session.scalar.return_value = False

    service.delete_cell(session, 2, MagicMock(id=1))

    session.delete.assert_called_once_with(cell)
    session.commit.assert_called_once()


def test_eliminar_celda_con_estancias_la_desactiva():
    session = MagicMock()
    cell = Celda(id=3, codigo="A-02", tipo="Libre", activo=True)
    session.get.return_value = cell
    session.scalar.return_value = True

    service.delete_cell(session, 3, MagicMock(id=1))

    assert cell.activo is False
    session.delete.assert_not_called()
    session.commit.assert_called_once()


def test_reactivar_celda_actualiza_estado_y_auditoria():
    session = MagicMock()
    cell = Celda(id=4, codigo="A-03", tipo="Libre", activo=False)
    session.get.return_value = cell

    service.update_cell(session, 4, CeldaActualizar(activo=True), MagicMock(id=1))

    assert cell.activo is True
    session.commit.assert_called_once()
    session.add.assert_called_once()
    auditoria = session.add.call_args.args[0]
    assert auditoria.accion == "ACTUALIZAR"
    assert auditoria.entidad == "celda"
    assert auditoria.entidad_id == 4
    assert auditoria.detalle == {
        "campos": ["activo"],
        "anteriores": {"activo": False},
        "nuevos": {"activo": True},
    }


def test_migracion_0005_agrega_activo_sin_conectar():
    output = StringIO()
    config = Config(
        str(Path(__file__).resolve().parents[1] / "alembic.ini"),
        output_buffer=output,
    )
    command.upgrade(config, "0004:0005", sql=True)
    sql = output.getvalue()
    assert "ALTER TABLE celda ADD COLUMN activo" in sql
    assert "BOOLEAN" in sql
    assert "DEFAULT true" in sql
    assert "NOT NULL" in sql


def test_el_arranque_ejecuta_el_seed(monkeypatch):
    llamadas = []
    monkeypatch.setenv("CELDAS_SEED_ON_STARTUP", "1")
    monkeypatch.setattr(main, "seed_default_cells", lambda: llamadas.append(1))
    with TestClient(main.app):
        pass
    assert llamadas == [1]


def test_un_fallo_del_seed_no_impide_health(monkeypatch):
    monkeypatch.setenv("CELDAS_SEED_ON_STARTUP", "1")

    def fallar():
        raise SQLAlchemyError("detalle privado")

    monkeypatch.setattr(main, "seed_default_cells", fallar)
    with TestClient(main.app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
