"""Pruebas optativas en autos_colombia: sin DDL y rollback de todos los registros."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_engine, get_session
from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="Activa RUN_POSTGRES_TESTS=1 para probar PostgreSQL local.",
)


@pytest.fixture
def client():
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            assert connection.scalar(text("SELECT current_database()")) == "autos_colombia"
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) in {"0001", "0002", "0003", "0004"}
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                def override_session():
                    yield session
                app.dependency_overrides[get_session] = override_session
                try:
                    with TestClient(app) as api:
                        yield api
                finally:
                    app.dependency_overrides.pop(get_session, None)
        finally:
            transaction.rollback()


def test_crud_and_errors_in_postgres(client):
    letters = "".join(chr(65 + int(c, 16) % 26) for c in uuid4().hex[:3])
    payload = {"placa": f" {letters.lower()}-111 ", "color": "Azul", "modelo": 2025,
               "marca": "Prueba", "tipo": "AUTOMOVIL"}
    created = client.post("/vehiculos", json=payload)
    assert created.status_code == 201
    vehicle = created.json()
    first_id = vehicle["id"]
    assert vehicle["placa"] == f"{letters}111"
    assert vehicle["modelo"] == 2025
    assert client.get(f"/vehiculos/{first_id}").json() == vehicle
    assert client.post("/vehiculos", json=payload).status_code == 409
    # La sesión debe seguir siendo utilizable después del conflicto real de PostgreSQL.
    second = client.post("/vehiculos", json={**payload, "placa": f"{letters}222"})
    assert second.status_code == 201
    second_id = second.json()["id"]
    page = client.get("/vehiculos?offset=0&limit=1")
    assert page.status_code == 200
    assert len(page.json()["items"]) == 1
    assert page.json()["total"] >= 2
    assert page.json()["offset"] == 0 and page.json()["limit"] == 1
    ids = [client.get(f"/vehiculos?offset={i}&limit=1").json()["items"][0]["id"] for i in (0, 1)]
    assert ids[0] < ids[1]
    assert client.get("/vehiculos?offset=9223372036854775807").json()["items"] == []
    assert client.patch(f"/vehiculos/{second_id}", json={"placa": payload["placa"]}).status_code == 409
    assert client.get(f"/vehiculos/{second_id}").json()["placa"] == f"{letters}222"
    patched = client.patch(f"/vehiculos/{first_id}", json={"color": " Rojo ", "placa": f" {letters.lower()} 333 "})
    assert patched.status_code == 200
    assert patched.json()["color"] == "Rojo"
    assert patched.json()["placa"] == f"{letters}333"
    assert patched.json()["marca"] == "Prueba"
    for invalid in ({"color": None}, {"id": first_id}, {"placa": " "}, {"placa": "AAAAA"}, {"placa": "ABC-12"}, {"placa": "1234AB"}, {"tipo": "BUS"},
                    {"modelo": 0}, {"modelo": True}, {"modelo": "2025"}, {"marca": "\t"}):
        assert client.patch(f"/vehiculos/{first_id}", json=invalid).status_code == 422
    assert client.post("/vehiculos", json={}).status_code == 422
    assert client.post("/vehiculos", json={**payload, "color": None}).status_code == 422
    for query in ("limit=0", "limit=101", "offset=-1"):
        assert client.get(f"/vehiculos?{query}").status_code == 422
    assert client.get("/vehiculos/0").status_code == 422
    deleted = client.delete(f"/vehiculos/{first_id}")
    assert deleted.status_code == 204 and deleted.content == b""
    assert client.get(f"/vehiculos/{first_id}").status_code == 404
    assert client.patch(f"/vehiculos/{first_id}", json={"color": "Azul"}).status_code == 404
    assert client.delete(f"/vehiculos/{first_id}").status_code == 404
    assert client.delete(f"/vehiculos/{second_id}").status_code == 204
    assert client.get("/health").json() == {"status": "ok"}
