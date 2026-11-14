"""Agrega la baja lógica a las celdas del parqueadero.

Revision ID: 0005
Revises: 0004

Las celdas preexistentes quedan activas. El downgrade elimina la columna y
devuelve la disponibilidad anterior; no borra filas.
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "celda",
        sa.Column(
            "activo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("celda", "activo")
