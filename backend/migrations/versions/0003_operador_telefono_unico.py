"""Teléfono de operador único y en formato colombiano (10 dígitos).

Revision ID: 0003
Revises: 0002

Falla sin modificar datos si hay teléfonos repetidos o con otro formato.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

FORMATO = "^(3[0-9]{9}|60[1-8][0-9]{7})$"


def upgrade() -> None:
    bind = op.get_bind()
    repetidos = bind.execute(sa.text(
        "SELECT telefono, array_agg(id ORDER BY id) FROM operador GROUP BY telefono HAVING count(*) > 1"
    )).all()
    invalidos = bind.execute(sa.text(
        "SELECT id, telefono FROM operador WHERE telefono !~ :formato ORDER BY id"
    ), {"formato": FORMATO}).all()
    if repetidos or invalidos:
        raise RuntimeError(
            "Corrige los datos antes de migrar. "
            f"Teléfonos repetidos (teléfono, ids): {[tuple(r) for r in repetidos]}. "
            f"Teléfonos con formato no colombiano (id, teléfono): {[tuple(r) for r in invalidos]}."
        )
    op.create_unique_constraint("uq_operador_telefono", "operador", ["telefono"])
    op.create_check_constraint("ck_operador_telefono_colombiano", "operador", f"telefono ~ '{FORMATO}'")


def downgrade() -> None:
    op.drop_constraint("ck_operador_telefono_colombiano", "operador", type_="check")
    op.drop_constraint("uq_operador_telefono", "operador", type_="unique")
