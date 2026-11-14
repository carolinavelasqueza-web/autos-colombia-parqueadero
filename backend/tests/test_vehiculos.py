from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.schemas.vehiculo import (
    VehiculoActualizar,
    VehiculoCrear,
    VehiculoRespuesta,
)
from app.services.vehiculo import VehiculoError, delete_vehicle
from conftest import make_operator


@pytest.mark.parametrize("field", ["placa", "color", "modelo", "marca", "tipo", "cliente_id"])
def test_patch_rejects_explicit_null(field):
    with pytest.raises(ValidationError):
        VehiculoActualizar(**{field: None})


@pytest.mark.parametrize("field", ["placa", "color", "marca", "tipo"])
def test_patch_rejects_blank_text(field):
    with pytest.raises(ValidationError):
        VehiculoActualizar(**{field: " \t\n"})


def test_patch_only_supplied_fields_and_no_id():
    assert VehiculoActualizar(placa=" abc123 ").model_dump(exclude_unset=True) == {"placa": "ABC123"}
    assert VehiculoActualizar().model_dump(exclude_unset=True) == {}
    with pytest.raises(ValidationError):
        VehiculoActualizar(id=1)


def test_creation_requires_every_field():
    with pytest.raises(ValidationError):
        VehiculoCrear(placa="ABC123")
    with pytest.raises(ValidationError):
        VehiculoCrear(
            placa="ABC123",
            color="Azul",
            modelo=2025,
            marca="Marca",
            tipo="AUTOMOVIL",
        )


def test_creation_and_legacy_response_require_valid_client_binding():
    created = VehiculoCrear(
        placa="ABC123",
        color="Azul",
        modelo=2025,
        marca="Marca",
        tipo="AUTOMOVIL",
        cliente_id=7,
    )
    assert created.cliente_id == 7
    for cliente_id in (0, True, "7", None):
        with pytest.raises(ValidationError):
            VehiculoCrear(
                placa="ABC123",
                color="Azul",
                modelo=2025,
                marca="Marca",
                tipo="AUTOMOVIL",
                cliente_id=cliente_id,
            )
    legacy = VehiculoRespuesta(
        id=1,
        placa="ABC123",
        color="Azul",
        modelo=2025,
        marca="Marca",
        tipo="AUTOMOVIL",
        cliente_id=None,
        cliente=None,
    )
    assert legacy.cliente_id is None and legacy.cliente is None


def test_delete_foreign_key_conflict_rolls_back_without_related_deletes():
    session = MagicMock()
    vehicle = session.get.return_value
    driver_error = Exception("private database details")
    driver_error.sqlstate = "23503"
    driver_error.diag = SimpleNamespace(constraint_name="some_foreign_key")
    session.commit.side_effect = IntegrityError("DELETE", {}, driver_error)
    with pytest.raises(VehiculoError) as result:
        delete_vehicle(session, 1, make_operator())
    assert result.value.status_code == 409
    assert "private" not in result.value.detail
    session.rollback.assert_called_once()
    session.delete.assert_called_once_with(vehicle)
