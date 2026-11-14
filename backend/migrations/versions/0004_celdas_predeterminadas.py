"""Siembra las 80 celdas predeterminadas del parqueadero.

Revision ID: 0004
Revises: 0003

La inserción es idempotente: si una celda ya existe, conserva su tipo actual.
El downgrade solo elimina las celdas sembradas que no tengan estancias asociadas.
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

CELDAS: tuple[tuple[str, str], ...] = tuple(
    [(f"C-{numero:02d}", "AUTOMOVIL") for numero in range(1, 71)]
    + [(f"M-{numero:02d}", "MOTO") for numero in range(1, 11)]
)


def _codigos_sql() -> str:
    return ", ".join(f"'{codigo}'" for codigo, _tipo in CELDAS)


def upgrade() -> None:
    values = ", ".join(
        f"('{codigo}', '{tipo}')" for codigo, tipo in CELDAS
    )
    op.execute(
        "INSERT INTO celda (codigo, tipo) VALUES "
        f"{values} ON CONFLICT (codigo) DO NOTHING"
    )


def downgrade() -> None:
    op.execute(
        f"DELETE FROM celda WHERE codigo IN ({_codigos_sql()}) "
        "AND NOT EXISTS ("
        "SELECT 1 FROM estancia WHERE estancia.celda_id = celda.id"
        ")"
    )
