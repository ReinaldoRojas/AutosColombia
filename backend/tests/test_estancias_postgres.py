"""Flujo real de entrada y salida en PostgreSQL: datos confirmados y limpieza exclusiva por sus ids.

Cubre HU-01 a HU-05: cliente con vehículos, consulta, mensualidad, asignación automática según el
tipo de celda y recibo, además de la concurrencia entre las dos puertas (RNF-01).
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session

from app.database import get_engine, get_session
from app.main import app
from app.models import Celda, Cliente, Estancia, Operador, Vehiculo
from app.services.mensualidad import hoy_colombia

pytestmark = pytest.mark.skipif(os.getenv('RUN_POSTGRES_TESTS') != '1', reason='Requiere PostgreSQL local.')


def placa(sufijo: str = '123') -> str:
    return ''.join(chr(65 + int(c, 16) % 26) for c in uuid4().hex[:3]) + sufijo


def documento() -> str:
    return str(int(uuid4().hex[:12], 16))[:12]


def telefono() -> str:
    return f'3{int(uuid4().hex[:8], 16) % 10**9:09d}'


@pytest.fixture
def datos():
    engine = get_engine()
    with engine.connect() as c:
        assert c.scalar(text('SELECT current_database()')) == 'autos_colombia'
        assert c.scalar(text('SELECT version_num FROM alembic_version')) == '0005'
    hoy = hoy_colombia()
    with Session(engine) as s, s.begin():
        cliente = Cliente(tipo_documento='CC', numero_documento=documento(), nombres='Laura', apellidos='Prueba',
                          telefono=telefono())
        s.add(cliente)
        s.flush()

        def vehiculo(tipo, pago, con_cliente=True, sufijo='123'):
            return Vehiculo(placa=placa(sufijo), color='Gris', modelo=2021, marca='Mazda', linea='3', tipo=tipo,
                            cliente_id=cliente.id if con_cliente else None, fecha_pago=pago)

        vehiculos = {
            'carro': vehiculo('CARRO', hoy - timedelta(days=13)),
            'camioneta': vehiculo('CAMIONETA', hoy),
            'moto': vehiculo('MOTO', hoy - timedelta(days=30), sufijo='12A'),
            'vencido': vehiculo('CARRO', hoy - timedelta(days=33)),
            'sin_cliente': vehiculo('CARRO', None, con_cliente=False),
        }
        operadores = [Operador(nombre=f'Prueba {n}', telefono=telefono()) for n in range(2)]
        s.add_all(list(vehiculos.values()) + operadores)
        s.flush()
        data = {'cliente': cliente.id, 'o': [o.id for o in operadores],
                'id': {k: v.id for k, v in vehiculos.items()}, 'placa': {k: v.placa for k, v in vehiculos.items()}}
    try:
        yield data
    finally:
        ids = list(data['id'].values())
        with Session(engine) as s, s.begin():
            s.execute(delete(Estancia).where(Estancia.vehiculo_id.in_(ids)))
            s.execute(delete(Vehiculo).where(Vehiculo.id.in_(ids)))
            s.execute(delete(Cliente).where(Cliente.id == data['cliente']))
            s.execute(delete(Operador).where(Operador.id.in_(data['o'])))


def entrada(d, clave='carro', o=0, puerta=1):
    return {'placa': d['placa'][clave], 'operador_id': d['o'][o], 'puerta_id': puerta}


def abiertas(d) -> int:
    with Session(get_engine()) as s:
        return s.scalar(select(func.count()).select_from(Estancia).where(
            Estancia.vehiculo_id.in_(d['id'].values()), Estancia.salida.is_(None)))


def test_consulta_valida_mensualidad_y_cupo(datos):
    d = datos
    with TestClient(app) as client:
        vigente = client.get('/estancias/vehiculo/' + d['placa']['carro'].lower()).json()
        assert vigente['mensualidad']['estado'] == 'VIGENTE' and vigente['puede_ingresar']
        assert vigente['cliente']['id'] == d['cliente'] and vigente['cupo']['tipo_celda'] == 'CARRO_CAMIONETA'
        assert client.get('/estancias/vehiculo/' + d['placa']['moto']).json()['mensualidad']['estado'] == 'VENCE_HOY'
        for clave, estado in (('vencido', 'VENCIDA'), ('sin_cliente', 'SIN_CLIENTE')):
            body = client.get('/estancias/vehiculo/' + d['placa'][clave]).json()
            assert body['mensualidad']['estado'] == estado and not body['puede_ingresar']
            rechazo = client.post('/estancias/entrada', json=entrada(d, clave))
            assert rechazo.status_code == 409 and rechazo.json()['detail'] == body['motivo']
        no_registrado = client.get('/estancias/vehiculo/' + placa('999'))
        assert no_registrado.status_code == 404 and 'no registrado' in no_registrado.json()['detail']
        assert abiertas(d) == 0


def test_recorrido_entrada_recibo_y_salida(datos):
    d = datos
    with TestClient(app) as client:
        for field, value in (('operador_id', 9223372036854775807), ('puerta_id', 32767)):
            assert client.post('/estancias/entrada', json={**entrada(d), field: value}).status_code == 404
        assert abiertas(d) == 0

        # RF-05: celda automática del tipo del vehículo, registro abierto y recibo.
        carro = client.post('/estancias/entrada', json=entrada(d, puerta=2))
        assert carro.status_code == 201
        carro = carro.json()
        assert carro['celda']['tipo'] == 'CARRO_CAMIONETA' and carro['abierta']
        assert carro['numero_recibo'] == f"E-{carro['id']:06d}"
        assert carro['puerta_entrada']['id'] == 2 and carro['cliente'] == 'Laura Prueba'
        assert carro['operador_entrada']['id'] == d['o'][0]
        repetida = client.post('/estancias/entrada', json=entrada(d))
        assert repetida.status_code == 409
        assert repetida.json()['detail'] == f"El vehículo ya se encuentra en la celda {carro['celda']['codigo']}."
        consulta = client.get('/estancias/vehiculo/' + d['placa']['carro']).json()
        assert consulta['esta_dentro'] and not consulta['puede_ingresar']
        assert consulta['estancia']['numero_recibo'] == carro['numero_recibo']
        # Una moto nunca va a una celda de carro, ni al revés.
        moto = client.post('/estancias/entrada', json=entrada(d, 'moto')).json()
        assert moto['celda']['tipo'] == 'MOTO'
        camioneta = client.post('/estancias/entrada', json=entrada(d, 'camioneta', o=1)).json()
        assert camioneta['celda']['tipo'] == 'CARRO_CAMIONETA' and camioneta['celda']['id'] != carro['celda']['id']

        recibo = client.get('/estancias/recibo/' + carro['numero_recibo'].lower().replace('-', ''))
        assert recibo.status_code == 200 and recibo.json()['placa'] == d['placa']['carro']
        assert client.get('/estancias/recibo/E-999999999').status_code == 404

        # Salida por placa: cierra con operador y puerta, y la celda vuelve a estar libre.
        salida = client.post('/estancias/salida', json={'placa': d['placa']['carro'], 'operador_id': d['o'][1]})
        assert salida.status_code == 200
        body = salida.json()
        assert not body['abierta'] and body['operador_salida']['id'] == d['o'][1]
        sin_ingreso = client.post('/estancias/salida', json={'placa': d['placa']['carro'], 'operador_id': d['o'][0]})
        assert sin_ingreso.status_code == 409 and 'no tiene un ingreso abierto' in sin_ingreso.json()['detail']
        assert client.get('/estancias/vehiculo/' + d['placa']['carro']).json()['puede_ingresar']
        assert abiertas(d) == 2


def test_cupo_lleno_por_tipo(datos):
    """HU-06 sin alterar datos ajenos: todo ocurre en una transacción que se revierte."""
    d = datos
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode='create_savepoint') as session:
                # Ocupa todas las celdas de moto libres con vehículos temporales del mismo cliente.
                libres = session.scalars(select(Celda).where(Celda.tipo == 'MOTO', ~select(Estancia.id).where(
                    Estancia.celda_id == Celda.id, Estancia.salida.is_(None)).exists())).all()
                for celda in libres:
                    temporal = Vehiculo(placa=placa('12Z'), color='X', modelo=2020, marca='X', linea='X', tipo='MOTO',
                                        cliente_id=d['cliente'], fecha_pago=hoy_colombia())
                    session.add(temporal)
                    session.flush()
                    session.add(Estancia(vehiculo_id=temporal.id, celda_id=celda.id, operador_entrada_id=d['o'][0],
                                         puerta_entrada_id=1))
                session.commit()  # libera el savepoint; la transacción exterior se revierte al final

                def override():
                    yield session
                app.dependency_overrides[get_session] = override
                try:
                    with TestClient(app) as client:
                        consulta = client.get('/estancias/vehiculo/' + d['placa']['moto']).json()
                        assert consulta['cupo']['disponibles'] == 0 and not consulta['puede_ingresar']
                        lleno = client.post('/estancias/entrada', json=entrada(d, 'moto'))
                        assert lleno.status_code == 409
                        assert lleno.json()['detail'].startswith('No hay celdas disponibles para motos (')
                        # Un carro sí entra: los cupos son independientes por tipo.
                        assert client.post('/estancias/entrada', json=entrada(d, 'carro')).status_code == 201
                        moto_adentro = session.scalars(select(Vehiculo.placa).join(
                            Estancia, Estancia.vehiculo_id == Vehiculo.id).where(
                            Vehiculo.tipo == 'MOTO', Estancia.salida.is_(None))).first()
                        session.commit()  # cierra la lectura para que el servicio abra su propia transacción
                        assert client.post('/estancias/salida', json={'placa': moto_adentro,
                                                                      'operador_id': d['o'][0]}).status_code == 200
                        assert client.post('/estancias/entrada', json=entrada(d, 'moto')).status_code == 201
                finally:
                    app.dependency_overrides.pop(get_session, None)
        finally:
            transaction.rollback()


@pytest.mark.parametrize('caso', ['misma_placa', 'dos_vehiculos', 'salida'])
def test_concurrencia_entre_puertas(datos, caso):
    d = datos
    if caso == 'salida':
        with TestClient(app) as client:
            assert client.post('/estancias/entrada', json=entrada(d)).status_code == 201
        path = '/estancias/salida'
        payloads = [{'placa': d['placa']['carro'], 'operador_id': o} for o in d['o']]
    else:
        path = '/estancias/entrada'
        segundo = 'camioneta' if caso == 'dos_vehiculos' else 'carro'
        payloads = [entrada(d, 'carro', 0, 1), entrada(d, segundo, 1, 2)]
    barrier = Barrier(2, timeout=15)

    def sincronizar(conn, cursor, statement, parameters, context, executemany):
        # Las dos solicitudes llegan juntas al punto crítico: el bloqueo del vehículo (misma placa),
        # la inserción (dos vehículos, ya con celdas distintas bloqueadas) o el bloqueo de la salida.
        if caso == 'misma_placa' and 'FROM vehiculo' in statement and 'FOR UPDATE' in statement:
            barrier.wait()
        elif caso == 'dos_vehiculos' and statement.startswith('INSERT INTO estancia '):
            barrier.wait()
        elif caso == 'salida' and 'FROM estancia' in statement and 'FOR UPDATE' in statement:
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
    codes = sorted(r.status_code for r in responses)
    if caso == 'dos_vehiculos':
        # RN-10: nunca se envían dos vehículos a la misma celda.
        assert codes == [201, 201]
        assert responses[0].json()['celda']['id'] != responses[1].json()['celda']['id']
        assert abiertas(d) == 2
    elif caso == 'misma_placa':
        assert codes == [201, 409] and abiertas(d) == 1
        loser = next(r.json() for r in responses if r.status_code == 409)
        assert 'ya se encuentra en la celda' in loser['detail']
    else:
        assert codes == [200, 409] and abiertas(d) == 0
        loser = next(r.json() for r in responses if r.status_code == 409)
        assert 'ingreso abierto' in loser['detail']


def test_esquema_coincide_con_modelos():
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from app.models import Base
    with get_engine().connect() as connection:
        context = MigrationContext.configure(connection, opts={'compare_type': True})
        assert compare_metadata(context, Base.metadata) == []
        cupos = dict(connection.execute(text("SELECT tipo, count(*) FROM celda WHERE codigo ~ '^[0-9]{2}$' "
                                             "AND codigo::int BETWEEN 1 AND 80 GROUP BY tipo")).all())
        assert cupos == {'CARRO_CAMIONETA': 70, 'MOTO': 10}
        assert connection.execute(text('SELECT nombre FROM puerta ORDER BY id')).scalars().all() == ['Puerta 1',
                                                                                                    'Puerta 2']
