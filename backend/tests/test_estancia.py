from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
import importlib.util

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models import Base, Estancia, Operador

ENTRADA = datetime(2026, 10, 19, 10, tzinfo=timezone.utc)


def test_cerrar_asigna_fecha_relacion_e_id_sin_sesion():
    estancia = Estancia(entrada=ENTRADA)
    operador = Operador(id=7, nombre="Prueba", telefono="001")
    assert estancia.esta_abierta() is True
    # Misma hora absoluta con otro huso: la igualdad está permitida.
    salida = ENTRADA.astimezone(timezone(timedelta(hours=-5)))
    estancia.cerrar(salida, operador)
    assert estancia.esta_abierta() is False
    assert estancia.salida == salida
    assert estancia.operador_salida is operador
    assert estancia.operador_salida_id == 7
    with pytest.raises(ValueError, match="cerrada"):
        estancia.cerrar(ENTRADA + timedelta(hours=1), operador)
    assert estancia.salida == salida


@pytest.mark.parametrize("salida", [None, "2026-10-19", datetime(2026, 10, 19), ENTRADA - timedelta(microseconds=1)])
def test_rechaza_fecha_invalida_sin_cambiar_estado(salida):
    estancia = Estancia(entrada=ENTRADA)
    with pytest.raises(ValueError):
        estancia.cerrar(salida, Operador(id=7))
    assert estancia.esta_abierta()
    assert estancia.operador_salida is None
    assert estancia.operador_salida_id is None


@pytest.mark.parametrize("entrada", [None, datetime(2026, 10, 19)])
def test_cerrar_requiere_entrada_cargada_con_zona(entrada):
    with pytest.raises(ValueError, match="entrada"):
        Estancia(entrada=entrada).cerrar(ENTRADA, Operador(id=7))


@pytest.mark.parametrize("operador", [None, 7, Operador(nombre="Sin persistir", telefono="001")])
def test_operador_invalido_no_deja_cierre_parcial(operador):
    estancia = Estancia(entrada=ENTRADA)
    with pytest.raises(ValueError, match="operador"):
        estancia.cerrar(ENTRADA, operador)
    assert estancia.salida is None
    assert estancia.operador_salida_id is None


def test_relaciones_y_columnas():
    mapper = sa.inspect(Estancia)
    assert mapper.relationships.operador_entrada.local_columns == {Estancia.__table__.c.operador_entrada_id}
    assert mapper.relationships.operador_salida.local_columns == {Estancia.__table__.c.operador_salida_id}
    for relation in mapper.relationships:
        assert not relation.cascade.delete and not relation.cascade.delete_orphan
    table = Estancia.__table__
    assert {c.name for c in table.c if c.nullable} == {"salida", "operador_salida_id", "puerta_salida_id"}
    assert "id" in str(table.c.numero_recibo.computed.sqltext)
    assert isinstance(table.c.id.type, sa.BigInteger) and table.c.id.identity.always
    assert table.c.entrada.type.timezone and table.c.salida.type.timezone
    assert str(table.c.entrada.server_default.arg) == "now()"
    assert len(table.foreign_keys) == 6
    assert all(fk.ondelete == "RESTRICT" for fk in table.foreign_keys)


def test_migracion_0002_compila_sql(monkeypatch):
    """La revisión 0005 agrega puertas y recibo; la equivalencia final se prueba en PostgreSQL."""
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("estancia_migration", root / "migrations/versions/0002_estancia.py")
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    metadata = sa.MetaData()
    for name in ("vehiculo", "celda", "operador"):
        Base.metadata.tables[name].to_metadata(metadata)

    def create_index(name, table_name, columns, **kwargs):
        sa.Index(name, *(metadata.tables[table_name].c[c] for c in columns), **kwargs)

    monkeypatch.setattr(migration.op, "create_table", lambda name, *args: sa.Table(name, metadata, *args))
    monkeypatch.setattr(migration.op, "create_index", create_index)
    migration.upgrade()
    assert migration.revision == "0002" and migration.down_revision == "0001"
    dialect = postgresql.dialect()
    expected = Estancia.__table__
    actual = metadata.tables["estancia"]
    modelo = {c.name: str(c.type) for c in expected.columns}
    assert all(modelo[c.name] == str(c.type) for c in actual.columns)
    indices = {str(CreateIndex(i).compile(dialect=dialect)) for i in actual.indexes}
    assert any("uq_estancia_celda_abierta" in i for i in indices)
    assert "CREATE TABLE estancia" in str(CreateTable(actual).compile(dialect=dialect))


def test_alembic_offline_solo_agrega_estancia():
    output = StringIO()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "0001:0002", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE estancia" in sql
    assert "CREATE TABLE vehiculo" not in sql
    assert "DROP TABLE" not in sql
    assert sql.count("WHERE salida IS NULL") == 2
    assert sql.count("ON DELETE RESTRICT") == 4
    assert "TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL" in sql
    assert "CHECK (salida >= entrada)" in sql
    assert "CHECK ((salida IS NULL) = (operador_salida_id IS NULL))" in sql
    assert "CREATE INDEX ix_estancia_vehiculo_entrada ON estancia (vehiculo_id, entrada)" in sql
