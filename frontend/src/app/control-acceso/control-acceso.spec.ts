import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ControlAcceso } from './control-acceso';

describe('Control de acceso', () => {
  let http: HttpTestingController;
  let c: ControlAcceso;
  const celda = { id: 2, codigo: 'TEST-C', tipo: 'Libre' };
  const stay = {
    id: 3,
    vehiculo_id: 1,
    celda_id: 2,
    entrada: '2026-10-19T15:00:00Z',
    salida: null,
    operador_entrada_id: 4,
    operador_salida_id: null,
  };
  const state = {
    vehiculo: {
      id: 1,
      placa: 'ABC123',
      marca: 'Prueba',
      color: 'Azul',
      modelo: 2026,
      tipo: 'MOTO',
    },
    esta_dentro: true,
    estancia: { ...stay, celda },
  };
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ControlAcceso],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    c = TestBed.createComponent(ControlAcceso).componentInstance;
    http
      .expectOne('/celdas?offset=0&limit=100')
      .flush({ items: [celda], total: 2, offset: 0, limit: 100 });
    http
      .expectOne('/celdas?offset=1&limit=100')
      .flush({ items: [{ ...celda, id: 5 }], total: 2, offset: 1, limit: 100 });
    http.expectOne('/operadores?offset=0&limit=100').flush({
      items: [{ id: 4, nombre: 'Prueba', telefono: '001' }],
      total: 1,
      offset: 0,
      limit: 100,
    });
  });
  afterEach(() => http.verify());

  it('recorre todas las páginas y registra entrada normalizada sin fecha ni doble envío', () => {
    expect(c.celdas().length).toBe(2);
    c.entrada.setValue({ placa: ' abc-123 ', celda_id: 2, operador_id: 4 });
    c.registrarEntrada();
    c.registrarEntrada();
    const req = http.expectOne('/estancias/entrada');
    expect(req.request.body).toEqual({ placa: 'ABC123', celda_id: 2, operador_id: 4 });
    req.flush(stay);
    expect(c.exitoEntrada()).toContain('TEST-C');
    expect(c.exitoEntrada()).toContain('Bogotá');
  });
  it('rechaza blancos y muestra los conflictos de ocupación y referencias', () => {
    c.entrada.setValue({ placa: ' ', celda_id: 2, operador_id: 4 });
    c.registrarEntrada();
    http.expectNone('/estancias/entrada');
    for (const [status, detail] of [
      [409, 'El vehículo ya está dentro.'],
      [409, 'La celda está ocupada.'],
      [404, 'Operador no encontrado.'],
    ] as const) {
      c.entrada.controls.placa.setValue('ABC123');
      c.registrarEntrada();
      http.expectOne('/estancias/entrada').flush({ detail }, { status, statusText: 'Error' });
      expect(c.errorEntrada()).toBe(detail);
      expect(c.saving()).toBe(false);
    }
  });
  it('descarta respuestas antiguas y no permite salida al cambiar de placa', () => {
    c.consulta.setValue({ placa: 'ABC123', operador_id: 4 });
    c.buscar();
    c.consulta.controls.placa.setValue('DEF456');
    http.expectOne('/estancias/vehiculo/ABC123').flush(state);
    expect(c.estado()).toBeNull();
    c.registrarSalida();
    http.expectNone('/estancias/salida');
    c.consulta.controls.placa.setValue('ABC123');
    c.buscar();
    http.expectOne('/estancias/vehiculo/ABC123').flush(state);
    c.consulta.controls.placa.setValue('DEF456');
    expect(c.estado()).toBeNull();
  });
  it('consulta antes de salir, envía solo placa y operador y consulta fuera tras cerrar', () => {
    c.consulta.setValue({ placa: 'abc 123', operador_id: 4 });
    c.buscar();
    http.expectOne('/estancias/vehiculo/ABC123').flush(state);
    c.registrarSalida();
    c.registrarSalida();
    const req = http.expectOne('/estancias/salida');
    expect(req.request.body).toEqual({ placa: 'ABC123', operador_id: 4 });
    req.flush({ ...stay, salida: '2026-10-19T16:00:00Z', operador_salida_id: 4 });
    http
      .expectOne('/estancias/vehiculo/ABC123')
      .flush({ ...state, esta_dentro: false, estancia: null });
    expect(c.estado()?.esta_dentro).toBe(false);
    expect(c.exitoSalida()).toContain('Salida registrada');
  });
  it('distingue no registrado y conexión fallida e invalida salida rechazada', () => {
    c.consulta.setValue({ placa: 'ABC123', operador_id: 4 });
    c.buscar();
    http
      .expectOne('/estancias/vehiculo/ABC123')
      .flush({}, { status: 404, statusText: 'Not Found' });
    expect(c.errorConsulta()).toBe('Vehículo no registrado.');
    c.buscar();
    http.expectOne('/estancias/vehiculo/ABC123').error(new ProgressEvent('error'));
    expect(c.errorConsulta()).toContain('No se pudo conectar');
    c.buscar();
    http.expectOne('/estancias/vehiculo/ABC123').flush(state);
    c.registrarSalida();
    http
      .expectOne('/estancias/salida')
      .flush({ detail: 'Sin estancia abierta.' }, { status: 409, statusText: 'Conflict' });
    expect(c.estado()).toBeNull();
    expect(c.errorConsulta()).toContain('Consulta nuevamente');
  });
  it('interpreta el offset recibido y presenta el mismo instante en Bogotá', () => {
    expect(c.fecha('2026-10-19T15:00:00Z')).toBe(c.fecha('2026-10-19T10:00:00-05:00'));
    expect(c.fecha('2026-10-19T15:00:00Z')).toContain('10:00:00');
  });
});
