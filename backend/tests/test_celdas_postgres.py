"""Integración optativa sin DDL; todos los datos nuevos se revierten."""
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_engine, get_session
from app.main import app

pytestmark = pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Requiere PostgreSQL local.")


@pytest.fixture
def connection():
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            assert connection.scalar(text("SELECT current_database()")) == "autos_colombia"
            yield connection
        finally:
            transaction.rollback()


def test_celda_schema_and_constraints(connection):
    inspector = inspect(connection)
    columns = {c['name']: c for c in inspector.get_columns('celda')}
    assert set(columns) == {'id', 'codigo', 'tipo'}
    assert str(columns['id']['type']) == 'BIGINT'
    assert columns['id']['identity']['always']
    assert all(not c['nullable'] for c in columns.values())
    assert inspector.get_pk_constraint('celda')['constrained_columns'] == ['id']
    assert any(c['column_names'] == ['codigo'] for c in inspector.get_unique_constraints('celda'))
    code = 'SCHEMA-' + uuid4().hex.upper()
    connection.execute(text('INSERT INTO celda(codigo,tipo) VALUES (:code,:type)'), {'code':code,'type':'MOTO'})
    for code_value, kind, state in [(code,'MOTO','23505'), (' lowercase ','MOTO','23514'),
                                    (' \t','MOTO','23514'), (code+'X',' \t','23514'),
                                    (code+'Z','Libre','23514'),
                                    (None,'MOTO','23502'), (code+'Y',None,'23502')]:
        with pytest.raises(IntegrityError) as error:
            with connection.begin_nested():
                connection.execute(text('INSERT INTO celda(codigo,tipo) VALUES (:code,:type)'), {'code':code_value,'type':kind})
        assert error.value.orig.sqlstate == state


def test_crud_celdas(connection):
    with Session(bind=connection, join_transaction_mode='create_savepoint') as session:
        def override():
            yield session
        app.dependency_overrides[get_session] = override
        try:
            with TestClient(app) as client:
                code = 'CELL-' + uuid4().hex.upper()
                payload = {'codigo': f' {code.lower()} ', 'tipo': 'MOTO'}
                result = client.post('/celdas', json=payload)
                assert result.status_code == 201
                item = result.json()
                assert item['codigo'] == code and item['tipo'] == 'MOTO'
                path = f"/celdas/{item['id']}"
                assert client.get(path).json() == item
                assert client.post('/celdas', json=payload).status_code == 409
                page = client.get('/celdas?offset=0&limit=1')
                assert page.status_code == 200 and len(page.json()['items']) == 1
                assert client.get('/celdas?limit=0').status_code == 422
                for invalid in ({'id':1}, {'codigo':None}, {'tipo':' \t'}, {'tipo':None}, {'tipo':'Libre'}):
                    assert client.patch(path, json=invalid).status_code == 422
                assert client.post('/celdas', json={}).status_code == 422
                changed = client.patch(path, json={'tipo':'CARRO_CAMIONETA'})
                assert changed.status_code == 200 and changed.json()['tipo'] == 'CARRO_CAMIONETA'
                deleted = client.delete(path)
                assert deleted.status_code == 204 and deleted.content == b''
                assert client.get(path).status_code == 404
                assert client.patch(path, json={'tipo':'MOTO'}).status_code == 404
                assert client.delete(path).status_code == 404
                assert client.get('/health').json() == {'status':'ok'}
        finally:
            app.dependency_overrides.pop(get_session, None)
