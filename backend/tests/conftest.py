import os
from unittest.mock import MagicMock

import pytest

# Las pruebas unitarias no deben conectarse a PostgreSQL ni modificar la base.
os.environ["CELDAS_SEED_ON_STARTUP"] = "0"

from app.main import app
from app.models import Operador
from app.security import get_current_user


def make_operator(
    operator_id: int = 1,
    rol: str = "ADMINISTRADOR",
    activo: bool = True,
    usuario: str | None = None,
) -> Operador:
    return Operador(
        id=operator_id,
        nombre=f"Operador {operator_id}",
        telefono="001",
        usuario=usuario or f"operador{operator_id}",
        contrasena_hash="!",
        rol=rol,
        activo=activo,
    )


@pytest.fixture
def authenticate():
    """Sustituye la dependencia real para probar rutas sin PostgreSQL ni JWT."""
    def _authenticate(operator: Operador | None = None) -> Operador:
        current = operator or make_operator()
        app.dependency_overrides[get_current_user] = lambda: current
        return current

    yield _authenticate
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.scalar.return_value = 0
    return session
