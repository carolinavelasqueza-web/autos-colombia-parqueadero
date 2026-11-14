from unittest.mock import MagicMock

import pytest

from app.models import Auditoria
from app.services.auditoria import registrar_auditoria
from conftest import make_operator


@pytest.mark.parametrize("rol", ["ADMINISTRADOR", "OPERADOR"])
def test_auditoria_registra_al_operador_autenticado(rol):
    session = MagicMock()
    actor = make_operator(operator_id=42, rol=rol)

    registrar_auditoria(
        session,
        actor,
        "ENTRADA",
        "estancia",
        7,
        {"placa": "ABC123", "celda_id": 1},
    )

    row = session.add.call_args.args[0]
    assert isinstance(row, Auditoria)
    assert row.operador_id == actor.id
    assert row.accion == "ENTRADA"
    assert row.entidad == "estancia"
    assert row.entidad_id == 7
    assert row.detalle == {"placa": "ABC123", "celda_id": 1}


def test_auditoria_exige_operador_persistido():
    with pytest.raises(ValueError):
        registrar_auditoria(MagicMock(), make_operator(operator_id=None), "SALIDA", "estancia")
