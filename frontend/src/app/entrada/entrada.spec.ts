import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ConsultaVehiculo, Movimiento } from '../models/estancia';
import { TurnoService } from '../shared/turno.service';
import { Entrada } from './entrada';

const consulta: ConsultaVehiculo = {
  vehiculo: {
    id: 1,
    placa: 'KDT482',
    color: 'Gris',
    modelo: 2021,
    marca: 'Mazda',
    tipo: 'CARRO',
    cliente_id: 7,
    linea: 'Mazda 3',
    fecha_pago: '2026-10-05',
    fecha_vencimiento: '2026-11-04',
  },
  cliente: {
    id: 7,
    tipo_documento: 'CC',
    numero_documento: '1036458221',
    nombres: 'Laura',
    apellidos: 'Gómez Restrepo',
    telefono: '3001234567',
    correo: null,
    fecha_registro: '2026-10-01T10:00:00Z',
  },
  mensualidad: {
    estado: 'VIGENTE',
    fecha_pago: '2026-10-05',
    fecha_vencimiento: '2026-11-04',
    dias: 17,
    permite_ingreso: true,
    mensaje: 'Mensualidad vigente hasta 04/11/2026.',
  },
  esta_dentro: false,
  estancia: null,
  cupo: {
    tipo_celda: 'CARRO_CAMIONETA',
    nombre: 'carros y camionetas',
    total: 70,
    ocupadas: 46,
    disponibles: 24,
  },
  puede_ingresar: true,
  motivo: null,
};

const movimiento: Movimiento = {
  id: 245,
  numero_recibo: 'E-000245',
  vehiculo_id: 1,
  placa: 'KDT482',
  tipo_vehiculo: 'CARRO',
  marca: 'Mazda',
  linea: 'Mazda 3',
  color: 'Gris',
  cliente: 'Laura Gómez Restrepo',
  celda: { id: 25, codigo: '25', tipo: 'CARRO_CAMIONETA' },
  entrada: '2026-10-18T12:41:00Z',
  salida: null,
  abierta: true,
  puerta_entrada: { id: 2, nombre: 'Puerta 2' },
  puerta_salida: null,
  operador_entrada: { id: 4, nombre: 'Laura' },
  operador_salida: null,
};

describe('Registrar entrada', () => {
  let http: HttpTestingController;
  let c: Entrada;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [Entrada],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
    TestBed.inject(TurnoService).iniciar({
      operador: { id: 4, nombre: 'Laura' },
      puerta: { id: 2, nombre: 'Puerta 2' },
    });
    c = TestBed.createComponent(Entrada).componentInstance;
  });
  afterEach(() => {
    TestBed.inject(TurnoService).cerrar();
    http.verify();
  });

  it('consulta la placa normalizada y confirma sin enviar celda: la asigna el sistema', () => {
    c.form.controls.placa.setValue(' kdt-482 ');
    c.buscar();
    http.expectOne('/estancias/vehiculo/KDT482').flush(consulta);
    expect(c.consulta()?.mensualidad.estado).toBe('VIGENTE');
    c.confirmar();
    c.confirmar();
    const req = http.expectOne('/estancias/entrada');
    expect(req.request.body).toEqual({ placa: 'KDT482', operador_id: 4, puerta_id: 2 });
    req.flush(movimiento);
    expect(c.ingreso()?.numero_recibo).toBe('E-000245');
    expect(c.ingreso()?.celda.codigo).toBe('25');
  });

  it('no permite confirmar con la mensualidad vencida', () => {
    c.form.controls.placa.setValue('FRM731');
    c.buscar();
    http.expectOne('/estancias/vehiculo/FRM731').flush({
      ...consulta,
      mensualidad: { ...consulta.mensualidad, estado: 'VENCIDA', permite_ingreso: false },
      puede_ingresar: false,
      motivo: 'Mensualidad vencida hace 3 días.',
    });
    c.confirmar();
    http.expectNone('/estancias/entrada');
  });

  it('ofrece registrar cliente y vehículo cuando la placa no existe', () => {
    c.form.controls.placa.setValue('ZZZ999');
    c.buscar();
    http
      .expectOne('/estancias/vehiculo/ZZZ999')
      .flush({ detail: 'Vehículo no registrado.' }, { status: 404, statusText: 'Not Found' });
    expect(c.noRegistrada()).toBe('ZZZ999');
  });

  it('muestra el motivo del backend si otra puerta llenó el cupo', () => {
    c.form.controls.placa.setValue('KDT482');
    c.buscar();
    http.expectOne('/estancias/vehiculo/KDT482').flush(consulta);
    c.confirmar();
    http
      .expectOne('/estancias/entrada')
      .flush(
        { detail: 'No hay celdas disponibles para carros y camionetas (70/70).' },
        { status: 409, statusText: 'Conflict' },
      );
    expect(c.error()).toContain('70/70');
    expect(c.consulta()).toBeNull();
  });
});
