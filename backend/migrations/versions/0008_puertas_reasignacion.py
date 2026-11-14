"""Crea puertas, reasignaciones de celda y vincula la estancia con las puertas.

Revision ID: 0008
Revises: 0007

Las puertas son obligatorias en las nuevas entradas y salidas. Las estancias
heredadas conservan `puerta_entrada_id` y `puerta_salida_id` en `NULL`. El seed
inicial es idempotente y solo crea NORTE y SUR si no existen.
"""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "puerta",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("ubicacion", sa.Text(), nullable=False),
        sa.Column(
            "activo", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.UniqueConstraint("codigo", name="uq_puerta_codigo"),
        sa.CheckConstraint(
            "codigo ~ '[^[:space:]]'", name="ck_puerta_codigo_no_vacio"
        ),
        sa.CheckConstraint(
            "codigo = upper(regexp_replace(codigo, '^[[:space:]]+|[[:space:]]+$', '', 'g'))",
            name="ck_puerta_codigo_normalizado",
        ),
        sa.CheckConstraint(
            "ubicacion ~ '[^[:space:]]'", name="ck_puerta_ubicacion_no_vacia"
        ),
    )

    op.execute(
        sa.text(
            "INSERT INTO puerta (codigo, ubicacion) VALUES "
            "('NORTE', 'Entrada Norte'), ('SUR', 'Entrada Sur') "
            "ON CONFLICT (codigo) DO NOTHING"
        )
    )

    op.create_table(
        "estancia_reasignacion",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("estancia_id", sa.BigInteger(), nullable=False),
        sa.Column("celda_anterior_id", sa.BigInteger(), nullable=False),
        sa.Column("celda_nueva_id", sa.BigInteger(), nullable=False),
        sa.Column("operador_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "fecha",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["estancia_id"],
            ["estancia.id"],
            name="fk_reasignacion_estancia",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["celda_anterior_id"],
            ["celda.id"],
            name="fk_reasignacion_celda_anterior",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["celda_nueva_id"],
            ["celda.id"],
            name="fk_reasignacion_celda_nueva",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["operador_id"],
            ["operador.id"],
            name="fk_reasignacion_operador",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "motivo IS NULL OR motivo ~ '[^[:space:]]'",
            name="ck_reasignacion_motivo_no_vacio",
        ),
    )
    op.create_index(
        "ix_reasignacion_estancia_fecha",
        "estancia_reasignacion",
        ["estancia_id", "fecha"],
    )
    op.create_index(
        "ix_reasignacion_operador", "estancia_reasignacion", ["operador_id"]
    )

    op.add_column(
        "estancia", sa.Column("puerta_entrada_id", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "estancia", sa.Column("puerta_salida_id", sa.BigInteger(), nullable=True)
    )
    op.create_foreign_key(
        "fk_estancia_puerta_entrada",
        "estancia",
        "puerta",
        ["puerta_entrada_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_estancia_puerta_salida",
        "estancia",
        "puerta",
        ["puerta_salida_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_estancia_puerta_entrada", "estancia", ["puerta_entrada_id"]
    )
    op.create_index("ix_estancia_puerta_salida", "estancia", ["puerta_salida_id"])


def downgrade() -> None:
    op.drop_index("ix_estancia_puerta_salida", table_name="estancia")
    op.drop_index("ix_estancia_puerta_entrada", table_name="estancia")
    op.drop_constraint("fk_estancia_puerta_salida", "estancia", type_="foreignkey")
    op.drop_constraint("fk_estancia_puerta_entrada", "estancia", type_="foreignkey")
    op.drop_column("estancia", "puerta_salida_id")
    op.drop_column("estancia", "puerta_entrada_id")

    op.drop_index(
        "ix_reasignacion_operador", table_name="estancia_reasignacion"
    )
    op.drop_index(
        "ix_reasignacion_estancia_fecha", table_name="estancia_reasignacion"
    )
    op.drop_table("estancia_reasignacion")
    op.drop_table("puerta")
