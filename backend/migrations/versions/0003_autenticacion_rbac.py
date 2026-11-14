"""Añade credenciales, roles, estado activo y auditoría.

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("operador", sa.Column("usuario", sa.Text(), nullable=True))
    op.add_column("operador", sa.Column("contrasena_hash", sa.Text(), nullable=True))
    op.add_column(
        "operador",
        sa.Column("rol", sa.Text(), nullable=False, server_default=sa.text("'OPERADOR'")),
    )
    op.add_column(
        "operador",
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # Las cuentas heredadas quedan deshabilitadas y sin contraseña utilizable.
    op.execute(
        "UPDATE operador "
        "SET usuario = 'operador-' || id, contrasena_hash = '!', rol = 'OPERADOR', activo = false"
    )
    op.alter_column("operador", "usuario", existing_type=sa.Text(), nullable=False)
    op.alter_column("operador", "contrasena_hash", existing_type=sa.Text(), nullable=False)

    op.create_unique_constraint("uq_operador_usuario", "operador", ["usuario"])
    op.create_check_constraint(
        "ck_operador_usuario_no_vacio", "operador", "usuario ~ '[^[:space:]]'"
    )
    op.create_check_constraint(
        "ck_operador_usuario_normalizado",
        "operador",
        "usuario = lower(regexp_replace(usuario, '^[[:space:]]+|[[:space:]]+$', '', 'g'))",
    )
    op.create_check_constraint(
        "ck_operador_usuario_longitud", "operador", "char_length(usuario) BETWEEN 3 AND 50"
    )
    op.create_check_constraint(
        "ck_operador_contrasena_no_vacia", "operador", "contrasena_hash ~ '[^[:space:]]'"
    )
    op.create_check_constraint(
        "ck_operador_rol", "operador", "rol IN ('ADMINISTRADOR', 'OPERADOR')"
    )

    op.create_table(
        "auditoria",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("operador_id", sa.BigInteger(), nullable=False),
        sa.Column("accion", sa.Text(), nullable=False),
        sa.Column("entidad", sa.Text(), nullable=False),
        sa.Column("entidad_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "fecha",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("detalle", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["operador_id"],
            ["operador.id"],
            name="fk_auditoria_operador",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("accion ~ '[^[:space:]]'", name="ck_auditoria_accion_no_vacia"),
        sa.CheckConstraint("entidad ~ '[^[:space:]]'", name="ck_auditoria_entidad_no_vacia"),
    )
    op.create_index(
        "ix_auditoria_operador_fecha", "auditoria", ["operador_id", "fecha"]
    )
    op.create_index(
        "ix_auditoria_entidad_fecha", "auditoria", ["entidad", "entidad_id", "fecha"]
    )


def downgrade() -> None:
    op.drop_index("ix_auditoria_entidad_fecha", table_name="auditoria")
    op.drop_index("ix_auditoria_operador_fecha", table_name="auditoria")
    op.drop_table("auditoria")

    op.drop_constraint("ck_operador_rol", "operador", type_="check")
    op.drop_constraint("ck_operador_contrasena_no_vacia", "operador", type_="check")
    op.drop_constraint("ck_operador_usuario_longitud", "operador", type_="check")
    op.drop_constraint("ck_operador_usuario_normalizado", "operador", type_="check")
    op.drop_constraint("ck_operador_usuario_no_vacio", "operador", type_="check")
    op.drop_constraint("uq_operador_usuario", "operador", type_="unique")
    op.drop_column("operador", "activo")
    op.drop_column("operador", "rol")
    op.drop_column("operador", "contrasena_hash")
    op.drop_column("operador", "usuario")
