"""Placa de vehículo en formato colombiano: ABC123 o ABC12D, sin separadores.

Revision ID: 0004
Revises: 0003

Quita guiones y espacios de las placas existentes (ABC-123 pasa a ABC123). Falla sin
modificar nada si alguna placa no es colombiana o si dos placas coincidirían al normalizarlas.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

FORMATO = "^[A-Z]{3}[0-9]{2}[0-9A-Z]$"
NORMALIZADA = "upper(regexp_replace(placa, '[[:space:]-]', '', 'g'))"


def upgrade() -> None:
    bind = op.get_bind()
    invalidas = bind.execute(sa.text(
        f"SELECT id, placa FROM vehiculo WHERE {NORMALIZADA} !~ :formato ORDER BY id"
    ), {"formato": FORMATO}).all()
    repetidas = bind.execute(sa.text(
        f"SELECT {NORMALIZADA} AS placa, array_agg(id ORDER BY id) FROM vehiculo "
        "GROUP BY 1 HAVING count(*) > 1"
    )).all()
    if invalidas or repetidas:
        raise RuntimeError(
            "Corrige los datos antes de migrar. "
            f"Placas no colombianas (id, placa): {[tuple(r) for r in invalidas]}. "
            f"Placas que coinciden al quitar separadores (placa, ids): {[tuple(r) for r in repetidas]}."
        )
    op.execute(f"UPDATE vehiculo SET placa = {NORMALIZADA} WHERE placa <> {NORMALIZADA}")
    op.create_check_constraint("ck_vehiculo_placa_colombiana", "vehiculo", f"placa ~ '{FORMATO}'")


def downgrade() -> None:
    op.drop_constraint("ck_vehiculo_placa_colombiana", "vehiculo", type_="check")
