"""Agrega la fecha de vencimiento del cliente y las tablas de tarifas y pagos.

Revision ID: 0010
Revises: 0009

Las tarifas conservan historial: una fila con ``vigente_hasta`` nulo es la
vigente de su tipo. Los pagos referencian al cliente y guardan el detalle por
vehículo. La secuencia ``pago_recibo_seq`` genera el número ``RC-000001``.
"""

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cliente", sa.Column("fecha_vencimiento", sa.Date(), nullable=True)
    )

    op.execute(sa.text("CREATE SEQUENCE pago_recibo_seq START WITH 1 INCREMENT BY 1"))

    op.create_table(
        "tarifa",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "vigente_desde",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("vigente_hasta", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "tipo IN ('MOTO', 'AUTOMOVIL', 'CAMIONETA')", name="ck_tarifa_tipo"
        ),
        sa.CheckConstraint("valor > 0", name="ck_tarifa_valor_positivo"),
        sa.CheckConstraint(
            "vigente_hasta IS NULL OR vigente_hasta > vigente_desde",
            name="ck_tarifa_vigencia",
        ),
    )
    op.create_index(
        "uq_tarifa_vigente",
        "tarifa",
        ["tipo"],
        unique=True,
        postgresql_where=sa.text("vigente_hasta IS NULL"),
    )
    op.create_index("ix_tarifa_tipo_desde", "tarifa", ["tipo", "vigente_desde"])

    op.create_table(
        "pago",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("cliente_id", sa.BigInteger(), nullable=False),
        sa.Column("meses", sa.Integer(), nullable=False),
        sa.Column("metodo", sa.Text(), nullable=False),
        sa.Column("referencia", sa.Text(), nullable=True),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "estado",
            sa.Text(),
            server_default=sa.text("'VIGENTE'"),
            nullable=False,
        ),
        sa.Column("numero_recibo", sa.Text(), nullable=False),
        sa.Column("periodo_desde", sa.Date(), nullable=False),
        sa.Column("periodo_hasta", sa.Date(), nullable=False),
        sa.Column("vencimiento_anterior", sa.Date(), nullable=True),
        sa.Column(
            "reactivo_cliente",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("operador_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "fecha",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("anulado_por", sa.BigInteger(), nullable=True),
        sa.Column("anulado_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["cliente_id"],
            ["cliente.id"],
            name="fk_pago_cliente",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["operador_id"],
            ["operador.id"],
            name="fk_pago_operador",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["anulado_por"],
            ["operador.id"],
            name="fk_pago_anulado_por",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("meses BETWEEN 1 AND 12", name="ck_pago_meses"),
        sa.CheckConstraint(
            "metodo IN ('EFECTIVO', 'TRANSFERENCIA', 'TARJETA')",
            name="ck_pago_metodo",
        ),
        sa.CheckConstraint(
            "estado IN ('VIGENTE', 'ANULADO')", name="ck_pago_estado"
        ),
        sa.CheckConstraint("monto > 0", name="ck_pago_monto_positivo"),
        sa.CheckConstraint(
            "numero_recibo ~ '^RC-[0-9]{6}$'", name="ck_pago_recibo_formato"
        ),
        sa.CheckConstraint(
            "periodo_hasta >= periodo_desde", name="ck_pago_periodo"
        ),
        sa.CheckConstraint(
            "((metodo = 'EFECTIVO') AND referencia IS NULL) OR "
            "((metodo <> 'EFECTIVO') AND referencia IS NOT NULL)",
            name="ck_pago_referencia_metodo",
        ),
        sa.CheckConstraint(
            "referencia IS NULL OR "
            "(referencia ~ '[^[:space:]]' AND char_length(referencia) <= 100)",
            name="ck_pago_referencia_texto",
        ),
        sa.CheckConstraint(
            "(estado = 'ANULADO') = (motivo IS NOT NULL AND anulado_por IS NOT NULL "
            "AND anulado_en IS NOT NULL)",
            name="ck_pago_anulacion_completa",
        ),
        sa.CheckConstraint(
            "motivo IS NULL OR "
            "(motivo ~ '[^[:space:]]' AND char_length(motivo) <= 500)",
            name="ck_pago_motivo",
        ),
        sa.UniqueConstraint("numero_recibo", name="uq_pago_numero_recibo"),
    )
    op.create_index(
        "uq_pago_referencia_vigente",
        "pago",
        ["referencia"],
        unique=True,
        postgresql_where=sa.text("estado = 'VIGENTE' AND referencia IS NOT NULL"),
    )
    op.create_index("ix_pago_cliente_fecha", "pago", ["cliente_id", "fecha"])
    op.create_index("ix_pago_estado_fecha", "pago", ["estado", "fecha"])

    op.create_table(
        "pago_detalle",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("pago_id", sa.BigInteger(), nullable=False),
        sa.Column("vehiculo_id", sa.BigInteger(), nullable=False),
        sa.Column("placa", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("tarifa_aplicada", sa.Numeric(12, 2), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(
            ["pago_id"],
            ["pago.id"],
            name="fk_pago_detalle_pago",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vehiculo_id"],
            ["vehiculo.id"],
            name="fk_pago_detalle_vehiculo",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "tipo IN ('MOTO', 'AUTOMOVIL', 'CAMIONETA')",
            name="ck_pago_detalle_tipo",
        ),
        sa.CheckConstraint(
            "tarifa_aplicada > 0", name="ck_pago_detalle_tarifa_positiva"
        ),
        sa.CheckConstraint(
            "subtotal > 0", name="ck_pago_detalle_subtotal_positivo"
        ),
        sa.CheckConstraint(
            "placa ~ '[^[:space:]]'", name="ck_pago_detalle_placa_no_vacia"
        ),
        sa.CheckConstraint(
            "placa = upper(regexp_replace(placa, '^[[:space:]]+|[[:space:]]+$', '', 'g'))",
            name="ck_pago_detalle_placa_normalizada",
        ),
        sa.UniqueConstraint(
            "pago_id", "vehiculo_id", name="uq_pago_detalle_vehiculo"
        ),
    )
    op.create_index("ix_pago_detalle_pago", "pago_detalle", ["pago_id"])


def downgrade() -> None:
    op.drop_index("ix_pago_detalle_pago", table_name="pago_detalle")
    op.drop_table("pago_detalle")

    op.drop_index("ix_pago_estado_fecha", table_name="pago")
    op.drop_index("ix_pago_cliente_fecha", table_name="pago")
    op.drop_index("uq_pago_referencia_vigente", table_name="pago")
    op.drop_table("pago")

    op.drop_index("ix_tarifa_tipo_desde", table_name="tarifa")
    op.drop_index("uq_tarifa_vigente", table_name="tarifa")
    op.drop_table("tarifa")

    op.execute(sa.text("DROP SEQUENCE pago_recibo_seq"))

    op.drop_column("cliente", "fecha_vencimiento")
