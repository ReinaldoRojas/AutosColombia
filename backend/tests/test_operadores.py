"""Errores HTTP y rollback sin depender de PostgreSQL."""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import get_session
from app.main import app
from app.models import Operador
from app.schemas.operador import OperadorActualizar, OperadorCrear


@pytest.fixture
def api():
    session = MagicMock()
    session.get.return_value = Operador(id=1, nombre="Prueba", telefono="001")

    def override():
        yield session

    app.dependency_overrides[get_session] = override
    try:
        with TestClient(app) as client:
            yield client, session
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.mark.parametrize("field", ["nombre", "telefono"])
@pytest.mark.parametrize("value", [None, "", " \t\n", 123, True, []])
def test_invalid_fields_are_422_without_writes(api, field, value):
    client, session = api
    payload = {"nombre": "Prueba", "telefono": "001", field: value}
    assert client.post("/operadores", json=payload).status_code == 422
    assert client.patch("/operadores/1", json={field: value}).status_code == 422
    session.commit.assert_not_called()


@pytest.mark.parametrize("payload", [{}, {"nombre": "Prueba"}, {"telefono": "001"},
                                     {"nombre": "Prueba", "telefono": "001", "id": 1}])
def test_creation_requires_fields_and_forbids_id(api, payload):
    client, session = api
    assert client.post("/operadores", json=payload).status_code == 422
    session.commit.assert_not_called()


def test_patch_forbids_id_and_unknown_fields(api):
    client, session = api
    for payload in ({"id": 2}, {"rol": "admin"}):
        assert client.patch("/operadores/1", json=payload).status_code == 422
    session.commit.assert_not_called()


@pytest.mark.parametrize("sqlstate, status", [("23503", 409), ("23502", 422), ("23514", 422)])
def test_database_conflicts_roll_back_and_hide_details(api, sqlstate, status):
    client, session = api
    driver_error = Exception("PRIVATE DRIVER DETAILS")
    driver_error.sqlstate = sqlstate
    session.commit.side_effect = IntegrityError("DELETE", {}, driver_error)
    result = client.delete("/operadores/1")
    assert result.status_code == status
    assert "PRIVATE" not in result.text
    assert isinstance(result.json()["detail"], str)
    session.rollback.assert_called_once()
    session.delete.assert_called_once_with(session.get.return_value)


def test_database_failure_rolls_back_and_is_generic(api):
    client, session = api
    session.get.side_effect = SQLAlchemyError("PRIVATE DRIVER DETAILS")
    result = client.get("/operadores/1")
    assert result.status_code == 503
    assert "PRIVATE" not in result.text
    session.rollback.assert_called_once()


@pytest.mark.parametrize("entrada, esperado", [
    ("3226561122", "3226561122"),
    (" 322 656 1122 ", "3226561122"),
    ("322-656-1122", "3226561122"),
    ("+57 322 656 1122", "3226561122"),
    ("+573226561122", "3226561122"),
    ("57 3226561122", "3226561122"),
    ("0057 3226561122", "3226561122"),
    ("(601) 234 5678", "6012345678"),
    ("+57 (604) 234-5678", "6042345678"),
])
def test_telefono_colombiano_se_normaliza_a_diez_digitos(entrada, esperado):
    assert OperadorCrear(nombre="Prueba", telefono=entrada).telefono == esperado
    assert OperadorActualizar(telefono=entrada).telefono == esperado


@pytest.mark.parametrize("telefono", [
    "001", "00123", "+57 00123", "322656112", "32265611222", "2226561122",
    "6092345678", "6002345678", "+1 3226561122", "322656112a", "5733226561122",
    "12345678901",
])
def test_telefono_no_colombiano_es_422_sin_escrituras(api, telefono):
    client, session = api
    assert client.post("/operadores", json={"nombre": "Prueba", "telefono": telefono}).status_code == 422
    assert client.patch("/operadores/1", json={"telefono": telefono}).status_code == 422
    session.commit.assert_not_called()


def test_telefono_repetido_es_409_con_mensaje_claro(api):
    client, session = api
    driver_error = Exception("PRIVATE DRIVER DETAILS")
    driver_error.sqlstate = "23505"
    driver_error.diag = MagicMock(constraint_name="uq_operador_telefono")
    session.commit.side_effect = IntegrityError("INSERT", {}, driver_error)
    for result in (
        client.post("/operadores", json={"nombre": "Prueba", "telefono": "3226561122"}),
        client.patch("/operadores/1", json={"telefono": "3226561122"}),
    ):
        assert result.status_code == 409
        assert result.json() == {"detail": "Ya existe un operador con ese teléfono."}
    assert session.rollback.call_count == 2
