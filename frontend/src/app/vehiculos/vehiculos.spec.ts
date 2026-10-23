import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Vehiculos } from './vehiculos';
import { Vehiculo } from '../models/vehiculo';

describe('Gestión de vehículos', () => {
  it('guarda los valores introducidos en los controles HTML', () => {
    flushList();
    component.newVehicle();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    for (const [field, value] of Object.entries({
      placa: ' dom123 ',
      marca: 'Prueba',
      modelo: '2025',
      color: 'Azul',
    })) {
      const input = root.querySelector<HTMLInputElement>(`#${field}`)!;
      input.value = value;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
    const select = root.querySelector<HTMLSelectElement>('#tipo')!;
    select.value = 'MOTO';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    root
      .querySelector('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    const request = http.expectOne({ method: 'POST', url: '/vehiculos' });
    expect(request.request.body.modelo).toBe(2025);
    request.flush({ ...vehicle, placa: 'DOM123' });
    flushList([{ ...vehicle, placa: 'DOM123' }]);
  });
  let fixture: ComponentFixture<Vehiculos>;
  let component: Vehiculos;
  let http: HttpTestingController;
  const vehicle: Vehiculo = {
    id: 1,
    placa: 'ABC123',
    marca: 'Marca',
    color: 'Azul',
    modelo: 2025,
    tipo: 'MOTO',
  };
  const flushList = (items: Vehiculo[] = [], total = items.length, offset = 0) => {
    http
      .expectOne(`/vehiculos?offset=${offset}&limit=10`)
      .flush({ items, total, offset, limit: 10 });
    fixture.detectChanges();
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Vehiculos],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Vehiculos);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });
  afterEach(() => http.verify());

  it('muestra carga y listado vacío', () => {
    expect(fixture.nativeElement.textContent).toContain('Cargando vehículos');
    flushList();
    expect(fixture.nativeElement.textContent).toContain('Aún no hay vehículos');
  });

  it('pagina usando offset y limit', () => {
    flushList([vehicle], 12);
    component.load(10);
    flushList([{ ...vehicle, id: 11 }], 12, 10);
    expect(component.page()).toBe(2);
  });

  it('valida campos vacíos y años no enteros sin enviar solicitudes', () => {
    flushList();
    component.newVehicle();
    component.form.patchValue({ placa: '   ', modelo: 2025.5 });
    component.save();
    expect(component.fieldError('placa')).toContain('obligatorio');
    expect(component.fieldError('modelo')).toContain('entero');
    http.expectNone((request) => request.method === 'POST');
  });

  it('rechaza placas no colombianas sin llamar al servicio y acepta ABC-123 y ABC12D', () => {
    flushList();
    component.newVehicle();
    for (const placa of ['AAAAA', 'TEST', 'ABC12', 'ABC1234', '1234AB', 'ÑBC123']) {
      component.form.patchValue({ ...vehicle, placa });
      component.save();
      expect(component.fieldError('placa')).toContain('colombiana');
    }
    http.expectNone((r) => r.method === 'POST');
    for (const placa of ['ABC-123', 'xyz 12a', 'ABC12D']) {
      component.form.patchValue({ ...vehicle, placa });
      expect(component.form.controls.placa.valid).toBe(true);
    }
  });

  it('crea con placa normalizada, bloquea doble envío y actualiza el listado', () => {
    flushList();
    component.newVehicle();
    component.form.patchValue({ ...vehicle, placa: ' abc123 ' });
    component.save();
    component.save();
    const request = http.expectOne({ method: 'POST', url: '/vehiculos' });
    expect(request.request.body.placa).toBe('ABC123');
    expect(request.request.body.id).toBeUndefined();
    expect(component.saving()).toBe(true);
    request.flush(vehicle);
    flushList([vehicle]);
    expect(component.success()).toContain('registrado');
    expect(component.showForm()).toBe(false);
  });

  it('señala placa duplicada y permite corregirla', () => {
    flushList();
    component.newVehicle();
    component.form.patchValue(vehicle);
    component.save();
    http
      .expectOne('/vehiculos')
      .flush({ detail: 'Duplicada' }, { status: 409, statusText: 'Conflict' });
    expect(component.fieldError('placa')).toContain('Ya existe');
    expect(component.saving()).toBe(false);
    component.form.controls.placa.setValue('DEF456');
    expect(component.form.controls.placa.valid).toBe(true);
  });

  it('consulta el vehículo y envía PATCH sin id', () => {
    flushList([vehicle]);
    component.edit(vehicle);
    http.expectOne({ method: 'GET', url: '/vehiculos/1' }).flush(vehicle);
    component.form.controls.color.setValue('Rojo');
    component.save();
    const request = http.expectOne({ method: 'PATCH', url: '/vehiculos/1' });
    expect(request.request.body.id).toBeUndefined();
    request.flush({ ...vehicle, color: 'Rojo' });
    flushList([{ ...vehicle, color: 'Rojo' }]);
    expect(component.success()).toContain('actualizado');
  });

  it('confirma con placa, permite cancelar y elimina una sola vez', () => {
    flushList([vehicle]);
    component.confirmDelete(vehicle);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alertdialog"]').textContent).toContain(
      'ABC123',
    );
    component.cancel();
    http.expectNone((request) => request.method === 'DELETE');
    component.confirmDelete(vehicle);
    component.remove();
    component.remove();
    http
      .expectOne({ method: 'DELETE', url: '/vehiculos/1' })
      .flush(null, { status: 204, statusText: 'No Content' });
    flushList();
    expect(component.success()).toContain('eliminado');
  });

  it('informa conflicto de eliminación sin retirar el registro', () => {
    flushList([vehicle]);
    component.confirmDelete(vehicle);
    component.remove();
    http.expectOne('/vehiculos/1').flush({}, { status: 409, statusText: 'Conflict' });
    expect(component.actionError()).toContain('registros relacionados');
    expect(component.items()).toEqual([vehicle]);
  });

  it('informa que un vehículo ya no existe', () => {
    flushList([vehicle]);
    component.edit(vehicle);
    http.expectOne('/vehiculos/1').flush({}, { status: 404, statusText: 'Not Found' });
    expect(component.actionError()).toContain('ya no existe');
  });

  it('asocia los errores 422 a los campos', () => {
    flushList();
    component.newVehicle();
    component.form.patchValue(vehicle);
    component.save();
    http
      .expectOne('/vehiculos')
      .flush(
        { detail: [{ loc: ['body', 'modelo'], msg: 'invalid', type: 'value_error' }] },
        { status: 422, statusText: 'Unprocessable Entity' },
      );
    expect(component.fieldError('modelo')).toContain('servicio rechazó');
  });

  it('muestra error de conexión y permite reintentar la carga', () => {
    http.expectOne('/vehiculos?offset=0&limit=10').error(new ProgressEvent('error'));
    expect(component.listError()).toContain('No se pudo conectar');
    component.load();
    flushList([vehicle]);
    expect(component.listError()).toBe('');
  });

  it('retrocede cuando la última página queda vacía', () => {
    flushList([vehicle], 11);
    component.load(10);
    flushList([{ ...vehicle, id: 11 }], 11, 10);
    component.confirmDelete({ ...vehicle, id: 11 });
    component.remove();
    http.expectOne('/vehiculos/11').flush(null, { status: 204, statusText: 'No Content' });
    flushList([], 10, 10);
    flushList([vehicle], 10, 0);
    expect(component.page()).toBe(1);
  });
});
