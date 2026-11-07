"""Alinea el esquema con el documento de diseño: RF-01 a RF-05.

Revision ID: 0005
Revises: 0004

- Crea PUERTA (Puerta 1 y Puerta 2) y CLIENTE.
- VEHICULO: tipo AUTOMOVIL pasa a CARRO; agrega cliente, línea, fecha de pago y vencimiento
  calculado (fecha de pago + 30 días). Los vehículos existentes quedan sin cliente ni pago y,
  por RF-04, no podrán ingresar hasta completar esos datos.
- CELDA: el tipo queda restringido a CARRO_CAMIONETA o MOTO. Los tipos libres existentes se
  convierten: si contienen «MOTO» pasan a MOTO y el resto a CARRO_CAMIONETA. Se crean las
  celdas 01 a 70 (carro/camioneta) y 71 a 80 (moto) que no existan (RN-05).
- ESTANCIA: agrega la puerta de entrada (las existentes se asignan a Puerta 1), la columna de
  puerta de salida del modelo relacional (la registrará RF-07) y el número de recibo E-000001
  derivado del id (RF-05).
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

TELEFONO = "^(3[0-9]{9}|60[1-8][0-9]{7})$"


def upgrade() -> None:
    op.create_table(
        "puerta",
        sa.Column("id", sa.SmallInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.UniqueConstraint("nombre", name="uq_puerta_nombre"),
    )
    op.execute("INSERT INTO puerta (nombre) VALUES ('Puerta 1'), ('Puerta 2')")

    op.create_table(
        "cliente",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("tipo_documento", sa.Text(), nullable=False),
        sa.Column("numero_documento", sa.Text(), nullable=False),
        sa.Column("nombres", sa.Text(), nullable=False),
        sa.Column("apellidos", sa.Text(), nullable=False),
        sa.Column("telefono", sa.Text(), nullable=False),
        sa.Column("correo", sa.Text(), nullable=True),
        sa.Column("fecha_registro", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("numero_documento", name="uq_cliente_documento"),
        sa.CheckConstraint("tipo_documento IN ('CC', 'CE', 'TI', 'PA', 'NIT')", name="ck_cliente_tipo_documento"),
        sa.CheckConstraint("numero_documento ~ '^[0-9A-Z]{3,20}$'", name="ck_cliente_documento_formato"),
        sa.CheckConstraint("nombres ~ '[^[:space:]]'", name="ck_cliente_nombres_no_vacios"),
        sa.CheckConstraint("apellidos ~ '[^[:space:]]'", name="ck_cliente_apellidos_no_vacios"),
        sa.CheckConstraint(f"telefono ~ '{TELEFONO}'", name="ck_cliente_telefono_colombiano"),
        sa.CheckConstraint("correo IS NULL OR correo ~ '^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$'",
                           name="ck_cliente_correo_formato"),
    )

    # VEHICULO
    op.drop_constraint("ck_vehiculo_tipo", "vehiculo", type_="check")
    op.execute("UPDATE vehiculo SET tipo = 'CARRO' WHERE tipo = 'AUTOMOVIL'")
    op.create_check_constraint("ck_vehiculo_tipo", "vehiculo", "tipo IN ('MOTO', 'CARRO', 'CAMIONETA')")
    op.add_column("vehiculo", sa.Column("cliente_id", sa.BigInteger(), nullable=True))
    op.add_column("vehiculo", sa.Column("linea", sa.Text(), nullable=True))
    op.add_column("vehiculo", sa.Column("fecha_pago", sa.Date(), nullable=True))
    op.add_column("vehiculo", sa.Column("fecha_vencimiento", sa.Date(), sa.Computed("fecha_pago + 30", persisted=True)))
    op.create_foreign_key("fk_vehiculo_cliente", "vehiculo", "cliente", ["cliente_id"], ["id"], ondelete="RESTRICT")
    op.create_check_constraint("ck_vehiculo_linea_no_vacia", "vehiculo", "linea IS NULL OR linea ~ '[^[:space:]]'")
    op.create_index("ix_vehiculo_cliente", "vehiculo", ["cliente_id"])

    # CELDA
    op.drop_constraint("ck_celda_tipo_no_vacio", "celda", type_="check")
    op.execute(
        "UPDATE celda SET tipo = CASE WHEN upper(tipo) LIKE '%MOTO%' THEN 'MOTO' ELSE 'CARRO_CAMIONETA' END "
        "WHERE tipo NOT IN ('CARRO_CAMIONETA', 'MOTO')"
    )
    op.create_check_constraint("ck_celda_tipo", "celda", "tipo IN ('CARRO_CAMIONETA', 'MOTO')")
    op.execute(
        "INSERT INTO celda (codigo, tipo) "
        "SELECT lpad(n::text, 2, '0'), CASE WHEN n <= 70 THEN 'CARRO_CAMIONETA' ELSE 'MOTO' END "
        "FROM generate_series(1, 80) AS n ON CONFLICT (codigo) DO NOTHING"
    )

    # ESTANCIA
    op.add_column("estancia", sa.Column("puerta_entrada_id", sa.SmallInteger(), nullable=True))
    op.add_column("estancia", sa.Column("puerta_salida_id", sa.SmallInteger(), nullable=True))
    op.execute("UPDATE estancia SET puerta_entrada_id = (SELECT id FROM puerta WHERE nombre = 'Puerta 1')")
    op.alter_column("estancia", "puerta_entrada_id", nullable=False)
    op.create_foreign_key("fk_estancia_puerta_entrada", "estancia", "puerta", ["puerta_entrada_id"], ["id"],
                          ondelete="RESTRICT")
    op.create_foreign_key("fk_estancia_puerta_salida", "estancia", "puerta", ["puerta_salida_id"], ["id"],
                          ondelete="RESTRICT")
    op.add_column("estancia", sa.Column(
        "numero_recibo", sa.Text(), sa.Computed("'E-' || lpad(id::text, 6, '0')", persisted=True)
    ))
    op.create_unique_constraint("uq_estancia_numero_recibo", "estancia", ["numero_recibo"])


def downgrade() -> None:
    # Reversión deliberada: elimina clientes, puertas y recibos.
    op.drop_constraint("uq_estancia_numero_recibo", "estancia", type_="unique")
    op.drop_column("estancia", "numero_recibo")
    op.drop_constraint("fk_estancia_puerta_salida", "estancia", type_="foreignkey")
    op.drop_constraint("fk_estancia_puerta_entrada", "estancia", type_="foreignkey")
    op.drop_column("estancia", "puerta_salida_id")
    op.drop_column("estancia", "puerta_entrada_id")
    op.drop_constraint("ck_celda_tipo", "celda", type_="check")
    op.create_check_constraint("ck_celda_tipo_no_vacio", "celda", "tipo ~ '[^[:space:]]'")
    op.drop_index("ix_vehiculo_cliente", table_name="vehiculo")
    op.drop_constraint("ck_vehiculo_linea_no_vacia", "vehiculo", type_="check")
    op.drop_constraint("fk_vehiculo_cliente", "vehiculo", type_="foreignkey")
    for column in ("fecha_vencimiento", "fecha_pago", "linea", "cliente_id"):
        op.drop_column("vehiculo", column)
    op.drop_constraint("ck_vehiculo_tipo", "vehiculo", type_="check")
    op.execute("UPDATE vehiculo SET tipo = 'AUTOMOVIL' WHERE tipo = 'CARRO'")
    op.create_check_constraint("ck_vehiculo_tipo", "vehiculo", "tipo IN ('MOTO', 'AUTOMOVIL', 'CAMIONETA')")
    op.drop_table("cliente")
    op.drop_table("puerta")
