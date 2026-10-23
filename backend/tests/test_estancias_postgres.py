"""Concurrencia real: datos nuevos confirmados, limpieza exclusiva por sus ids."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session

from app.database import get_engine
from app.main import app
from app.models import Celda, Estancia, Operador, Vehiculo

pytestmark = pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1', reason='Requiere PostgreSQL local.')


@pytest.fixture
def datos():
    engine = get_engine()
    with engine.connect() as c:
        assert c.scalar(text('SELECT current_database()')) == 'autos_colombia'
        assert c.scalar(text('SELECT version_num FROM alembic_version')) in ('0002', '0003', '0004')
    token = 'TEST-EST-' + uuid4().hex.upper()
    with Session(engine) as s, s.begin():
        letras = ''.join(chr(65 + int(c, 16) % 26) for c in uuid4().hex[:3])
        vehicles = [Vehiculo(placa=f'{letras}{n}{n}{n}', color='Prueba', modelo=2026, marca='Prueba', tipo='MOTO') for n in range(2)]
        cells = [Celda(codigo=f'{token}-{n}', tipo='Libre') for n in range(2)]
        operators = [Operador(nombre=f'{token}-{n}', telefono=f'3{int(uuid4().hex[:8], 16) % 10**9:09d}') for n in range(2)]
        s.add_all(vehicles + cells + operators)
        s.flush()
        data = {'v': [v.id for v in vehicles], 'placas': [v.placa for v in vehicles],
                'c': [c.id for c in cells], 'o': [o.id for o in operators]}
    try:
        yield data
    finally:
        with Session(engine) as s, s.begin():
            s.execute(delete(Estancia).where(Estancia.vehiculo_id.in_(data['v'])))
            s.execute(delete(Vehiculo).where(Vehiculo.id.in_(data['v'])))
            s.execute(delete(Celda).where(Celda.id.in_(data['c'])))
            s.execute(delete(Operador).where(Operador.id.in_(data['o'])))
        with Session(engine) as s:
            assert s.scalar(select(func.count()).select_from(Estancia).where(Estancia.vehiculo_id.in_(data['v']))) == 0


def entrada(d, v=0, c=0, o=0):
    return {'placa': d['placas'][v], 'celda_id': d['c'][c], 'operador_id': d['o'][o]}


def cantidad(d):
    with Session(get_engine()) as s:
        return s.scalar(select(func.count()).select_from(Estancia).where(Estancia.vehiculo_id.in_(d['v'])))


def test_recorrido_y_rechazos_sin_cambios_parciales(datos):
    d = datos
    with TestClient(app) as client:
        url = '/estancias/vehiculo/' + d['placas'][0]
        outside = client.get(url)
        assert outside.status_code == 200
        assert outside.json()['estancia'] is None and not outside.json()['esta_dentro']
        assert outside.json()['vehiculo']['id'] == d['v'][0]
        for field, value in [('placa', ''.join(chr(65 + int(c, 16) % 26) for c in uuid4().hex[:3]) + '999'), ('celda_id', 9223372036854775807), ('operador_id', 9223372036854775807)]:
            assert client.post('/estancias/entrada', json={**entrada(d), field: value}).status_code == 404
            assert cantidad(d) == 0
        missing = ''.join(chr(65 + int(c, 16) % 26) for c in uuid4().hex[:3]) + '999'
        assert client.get('/estancias/vehiculo/' + missing).status_code == 404
        assert client.post('/estancias/salida', json={'placa': missing, 'operador_id': d['o'][0]}).status_code == 404
        assert client.post('/estancias/salida', json={'placa': d['placas'][0], 'operador_id': 9223372036854775807}).status_code == 404
        before = datetime.now(timezone.utc)
        result = client.post('/estancias/entrada', json={**entrada(d), 'placa': ' ' + d['placas'][0].lower() + ' '})
        assert result.status_code == 201
        opened = result.json()
        assert before <= datetime.fromisoformat(opened['entrada']) <= datetime.now(timezone.utc)
        assert opened['salida'] is None and opened['operador_salida_id'] is None
        inside = client.get(url).json()
        assert inside['esta_dentro'] and inside['estancia']['id'] == opened['id']
        assert inside['estancia']['celda']['id'] == d['c'][0]
        for payload in (entrada(d, c=1), entrada(d, v=1)):
            assert client.post('/estancias/entrada', json=payload).status_code == 409
            assert cantidad(d) == 1
        closed = client.post('/estancias/salida', json={'placa': d['placas'][0], 'operador_id': d['o'][1]})
        assert closed.status_code == 200
        assert closed.json()['operador_salida_id'] == d['o'][1]
        assert datetime.fromisoformat(closed.json()['salida']) >= datetime.fromisoformat(opened['entrada'])
        assert client.post('/estancias/salida', json={'placa': d['placas'][0], 'operador_id': d['o'][0]}).status_code == 409
        assert client.get(url).json()['estancia'] is None
        with Session(get_engine()) as s:
            saved = s.get(Estancia, opened['id'])
            assert saved.operador_salida_id == d['o'][1]
            assert saved.salida == datetime.fromisoformat(closed.json()['salida'])
        assert client.post('/estancias/entrada', json=entrada(d, v=1)).status_code == 201
        assert cantidad(d) == 2
        for route in ('/health', '/vehiculos?limit=1', '/celdas?limit=1', '/operadores?limit=1'):
            assert client.get(route).status_code == 200


@pytest.mark.parametrize('caso', ['vehiculo', 'celda', 'salida'])
def test_concurrencia_real(datos, caso):
    d = datos
    if caso == 'salida':
        with TestClient(app) as client:
            assert client.post('/estancias/entrada', json=entrada(d)).status_code == 201
        path = '/estancias/salida'
        payloads = [{'placa': d['placas'][0], 'operador_id': o} for o in d['o']]
    else:
        path = '/estancias/entrada'
        payloads = [entrada(d), entrada(d, v=1 if caso == 'celda' else 0, c=1 if caso == 'vehiculo' else 0, o=1)]
    barrier = Barrier(2, timeout=15)

    def sincronizar(conn, cursor, statement, parameters, context, executemany):
        # Fuerza la carrera después de las consultas previas de entrada, o antes del bloqueo de salida.
        if (caso != 'salida' and statement.startswith('INSERT INTO estancia ')) or (
            caso == 'salida' and 'FROM estancia' in statement and 'FOR UPDATE' in statement
        ):
            barrier.wait()

    def enviar(payload):
        with TestClient(app) as client:
            return client.post(path, json=payload)

    engine = get_engine()
    event.listen(engine, 'before_cursor_execute', sincronizar)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(enviar, payloads))
    finally:
        event.remove(engine, 'before_cursor_execute', sincronizar)
    success = 200 if caso == 'salida' else 201
    assert sorted(r.status_code for r in responses) == [success, 409]
    assert cantidad(d) == 1
    winner = next(r.json() for r in responses if r.status_code == success)
    loser = next(r.json() for r in responses if r.status_code == 409)
    assert ('abierta' if caso == 'salida' else 'dentro' if caso == 'vehiculo' else 'ocupada') in loser['detail']
    with Session(engine) as s:
        saved = s.get(Estancia, winner['id'])
        assert saved.operador_entrada_id == winner['operador_entrada_id']
        assert saved.operador_salida_id == winner['operador_salida_id']
        assert saved.salida == (datetime.fromisoformat(winner['salida']) if winner['salida'] else None)
