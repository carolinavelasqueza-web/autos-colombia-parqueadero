"""Crea clientes y vincula cada vehículo con su propietario.

Revision ID: 0006
Revises: 0005

El vínculo es opcional para conservar los vehículos heredados; las nuevas
altas exigen un cliente desde la API y la interfaz. No se siembran clientes.
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cliente",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("documento", sa.Text(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("telefono", sa.Text(), nullable=False),
        sa.Column("correo", sa.Text(), nullable=False),
        sa.Column(
            "activo", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.UniqueConstraint("documento", name="uq_cliente_documento"),
        sa.CheckConstraint(
            "documento ~ '[^[:space:]]'", name="ck_cliente_documento_no_vacio"
        ),
        sa.CheckConstraint("nombre ~ '[^[:space:]]'", name="ck_cliente_nombre_no_vacio"),
        sa.CheckConstraint(
            "telefono ~ '[^[:space:]]'", name="ck_cliente_telefono_no_vacio"
        ),
        sa.CheckConstraint(
            "correo ~ '[^[:space:]]'", name="ck_cliente_correo_no_vacio"
        ),
        sa.CheckConstraint(
            "correo ~ '^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$'",
            name="ck_cliente_correo_formato",
        ),
    )

    op.add_column("vehiculo", sa.Column("cliente_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_vehiculo_cliente",
        "vehiculo",
        "cliente",
        ["cliente_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_vehiculo_cliente", "vehiculo", ["cliente_id"])


def downgrade() -> None:
    op.drop_index("ix_vehiculo_cliente", table_name="vehiculo")
    op.drop_constraint("fk_vehiculo_cliente", "vehiculo", type_="foreignkey")
    op.drop_column("vehiculo", "cliente_id")
    op.drop_table("cliente")
