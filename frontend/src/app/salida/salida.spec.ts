import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { TurnoService } from '../shared/turno.service';
import { Salida } from './salida';

describe('Registrar salida', () => {
  let http: HttpTestingController;
  let c: Salida;
  const estancia = {
    id: 3,
    numero_recibo: 'E-000003',
    placa: 'ABC123',
    celda: { id: 12, codigo: '12', tipo: 'CARRO_CAMIONETA' },
    abierta: true,
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [Salida],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
    TestBed.inject(TurnoService).iniciar({
      operador: { id: 4, nombre: 'Laura' },
      puerta: { id: 1, nombre: 'Puerta 1' },
    });
    c = TestBed.createComponent(Salida).componentInstance;
  });
  afterEach(() => {
    TestBed.inject(TurnoService).cerrar();
    http.verify();
  });

  it('busca por placa y cierra con el operador del turno', () => {
    c.form.controls.placa.setValue('abc 123');
    c.buscar();
    http.expectOne('/estancias/vehiculo/ABC123').flush({ estancia });
    c.confirmar();
    const req = http.expectOne('/estancias/salida');
    expect(req.request.body).toEqual({ placa: 'ABC123', operador_id: 4 });
    req.flush({ ...estancia, abierta: false, salida: '2026-10-18T20:00:00Z' });
    expect(c.salida()?.celda.codigo).toBe('12');
  });

  it('avisa cuando el vehículo no tiene ingreso abierto', () => {
    c.form.controls.placa.setValue('ABC123');
    c.buscar();
    http.expectOne('/estancias/vehiculo/ABC123').flush({ estancia: null });
    expect(c.error()).toBe('Este vehículo no tiene un ingreso abierto.');
    c.confirmar();
    http.expectNone('/estancias/salida');
  });
});
