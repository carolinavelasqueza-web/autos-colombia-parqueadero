"""Agrega el ficho de entrada y su marca de uso a la estancia.

Revision ID: 0007
Revises: 0006

El ficho identifica el comprobante impreso de una estancia. Es opcional para
conservar las estancias heredadas, pero la API lo exige en las nuevas entradas
y su formato queda validado por PostgreSQL.
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("estancia", sa.Column("ficho_codigo", sa.Text(), nullable=True))
    op.add_column(
        "estancia",
        sa.Column("ficho_usado_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "uq_estancia_ficho_codigo", "estancia", ["ficho_codigo"]
    )
    op.create_check_constraint(
        "ck_estancia_ficho_formato",
        "estancia",
        "ficho_codigo IS NULL OR ficho_codigo ~ '^AC-[0-9]{8}-[0-9]{4}$'",
    )
    op.create_check_constraint(
        "ck_estancia_ficho_uso",
        "estancia",
        "ficho_usado_en IS NULL OR ficho_codigo IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_estancia_ficho_fecha",
        "estancia",
        "ficho_usado_en IS NULL OR ficho_usado_en >= entrada",
    )


def downgrade() -> None:
    op.drop_constraint("ck_estancia_ficho_fecha", "estancia", type_="check")
    op.drop_constraint("ck_estancia_ficho_uso", "estancia", type_="check")
    op.drop_constraint("ck_estancia_ficho_formato", "estancia", type_="check")
    op.drop_constraint("uq_estancia_ficho_codigo", "estancia", type_="unique")
    op.drop_column("estancia", "ficho_usado_en")
    op.drop_column("estancia", "ficho_codigo")
