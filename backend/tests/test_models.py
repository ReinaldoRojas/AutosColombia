import importlib.util
from unittest.mock import MagicMock
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.models import Base, Celda, Operador, Vehiculo


def test_normalizes_unique_identifiers_on_creation_and_assignment():
    vehicle = Vehiculo(placa=" \tabc123\n", color="Azul", modelo=2025, marca="Marca", tipo="MOTO")
    cell = Celda(codigo=" a-01 ", tipo="Libre")
    assert vehicle.placa == "ABC123"
    assert cell.codigo == "A-01"
    vehicle.placa = " xyz789 "
    cell.codigo = " b-02 "
    assert vehicle.placa == "XYZ789"
    assert cell.codigo == "B-02"


@pytest.mark.parametrize("model,attribute", [
    (Vehiculo, "placa"), (Vehiculo, "color"), (Vehiculo, "marca"),
    (Vehiculo, "tipo"), (Celda, "codigo"), (Celda, "tipo"),
    (Operador, "nombre"), (Operador, "telefono"),
])
@pytest.mark.parametrize("value", ["", " \t\n", None])
def test_rejects_empty_text(model, attribute, value):
    with pytest.raises(ValueError):
        model(**{attribute: value})


@pytest.mark.parametrize("value", [0, 10000, True, "2025", 2025.5, None])
def test_rejects_invalid_year(value):
    with pytest.raises(ValueError):
        Vehiculo(modelo=value)


@pytest.mark.parametrize("value", ["MOTO", "AUTOMOVIL", "CAMIONETA"])
def test_vehicle_types(value):
    assert Vehiculo(tipo=value).tipo == value


def test_rejects_unknown_type_and_preserves_phone_text():
    with pytest.raises(ValueError):
        Vehiculo(tipo="CAMION")
    assert Operador(telefono="+57 00123").telefono == "+57 00123"
    assert Celda(tipo="Categoría futura").tipo == "Categoría futura"


def test_required_columns_and_identity():
    for name in ("vehiculo", "celda", "operador"):
        table = Base.metadata.tables[name]
        assert all(not column.nullable for column in table.columns)
        assert isinstance(table.c.id.type, sa.BigInteger)
        assert table.c.id.identity.always is True


def test_migration_matches_models_without_connecting(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "migrations/versions/0001_modelos_iniciales.py"
    spec = importlib.util.spec_from_file_location("initial_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    metadata = sa.MetaData()
    monkeypatch.setattr(migration.op, "create_table", lambda name, *args: sa.Table(name, metadata, *args))
    migration.upgrade()
    assert set(metadata.tables) == {"vehiculo", "celda", "operador"}
    phone_path = path.with_name("0003_operador_telefono_unico.py")
    phone_spec = importlib.util.spec_from_file_location("phone_migration", phone_path)
    phone_migration = importlib.util.module_from_spec(phone_spec)
    phone_spec.loader.exec_module(phone_migration)
    operador = metadata.tables["operador"]
    bind = MagicMock()
    bind.execute.return_value.all.return_value = []
    monkeypatch.setattr(phone_migration.op, "get_bind", lambda: bind)
    monkeypatch.setattr(phone_migration.op, "create_unique_constraint",
                        lambda name, table, columns: operador.append_constraint(sa.UniqueConstraint(*columns, name=name)))
    monkeypatch.setattr(phone_migration.op, "create_check_constraint",
                        lambda name, table, text: operador.append_constraint(sa.CheckConstraint(text, name=name)))
    phone_migration.upgrade()
    assert phone_migration.down_revision == "0002"
    plate_path = path.with_name("0004_vehiculo_placa_colombiana.py")
    plate_spec = importlib.util.spec_from_file_location("plate_migration", plate_path)
    plate_migration = importlib.util.module_from_spec(plate_spec)
    plate_spec.loader.exec_module(plate_migration)
    vehiculo = metadata.tables["vehiculo"]
    monkeypatch.setattr(plate_migration.op, "get_bind", lambda: bind)
    monkeypatch.setattr(plate_migration.op, "execute", lambda *args: None)
    monkeypatch.setattr(plate_migration.op, "create_check_constraint",
                        lambda name, table, text: vehiculo.append_constraint(sa.CheckConstraint(text, name=name)))
    plate_migration.upgrade()
    assert plate_migration.down_revision == "0003"
    for name, table in metadata.tables.items():
        model_table = Base.metadata.tables[name]
        assert [(c.name, str(c.type), c.nullable) for c in table.columns] == [
            (c.name, str(c.type), c.nullable) for c in model_table.columns
        ]
        def constraints(t):
            return {(c.name, str(c.sqltext)) for c in t.constraints if isinstance(c, sa.CheckConstraint)}
        assert constraints(table) == constraints(model_table)
        def unique_columns(t):
            return {tuple(c.columns.keys()) for c in t.constraints if isinstance(c, sa.UniqueConstraint)}
        assert unique_columns(table) == unique_columns(model_table)
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert "BIGINT GENERATED ALWAYS AS IDENTITY" in ddl
