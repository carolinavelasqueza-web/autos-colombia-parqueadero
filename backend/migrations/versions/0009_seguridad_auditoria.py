"""Persiste sesiones JWT y añade índices para reportes de ocupación.

Revision ID: 0009
Revises: 0008

La entidad de usuarios del proyecto es ``operador``; no existe una tabla
``usuario`` separada. La auditoría existente ya guarda operador, fecha y el
detalle JSONB con valores anteriores y nuevos, por lo que no requiere columnas
adicionales para el decorador ``@auditar``.
"""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sesion",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("operador_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "creada_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revocada_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["operador_id"],
            ["operador.id"],
            name="fk_sesion_operador",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("token_hash", name="uq_sesion_token_hash"),
        sa.CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$'",
            name="ck_sesion_token_hash_formato",
        ),
        sa.CheckConstraint("expira_en > creada_en", name="ck_sesion_fechas"),
        sa.CheckConstraint(
            "revocada_en IS NULL OR revocada_en >= creada_en",
            name="ck_sesion_revocada",
        ),
    )
    op.create_index(
        "ix_sesion_operador_creada", "sesion", ["operador_id", "creada_en"]
    )
    op.create_index(
        "ix_sesion_vigente",
        "sesion",
        ["expira_en"],
        postgresql_where=sa.text("revocada_en IS NULL"),
    )

    op.create_index("ix_estancia_entrada", "estancia", ["entrada"])
    op.create_index(
        "ix_estancia_salida",
        "estancia",
        ["salida"],
        postgresql_where=sa.text("salida IS NOT NULL"),
    )
    op.create_index(
        "ix_estancia_abierta_entrada",
        "estancia",
        ["entrada"],
        postgresql_where=sa.text("salida IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_estancia_abierta_entrada", table_name="estancia")
    op.drop_index("ix_estancia_salida", table_name="estancia")
    op.drop_index("ix_estancia_entrada", table_name="estancia")

    op.drop_index("ix_sesion_vigente", table_name="sesion")
    op.drop_index("ix_sesion_operador_creada", table_name="sesion")
    op.drop_table("sesion")
