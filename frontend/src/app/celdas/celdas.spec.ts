import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Celdas } from './celdas';

describe('Gestión de celdas', () => {
  let fixture: ComponentFixture<Celdas>;
  let http: HttpTestingController;
  const cell = { id: 1, codigo: 'A-01', tipo: 'MOTO' as const };
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Celdas],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Celdas);
    fixture.detectChanges();
    http
      .expectOne('/celdas?offset=0&limit=10')
      .flush({ items: [cell], total: 1, offset: 0, limit: 10 });
  });
  afterEach(() => http.verify());

  it('crea desde el formulario HTML con código normalizado y tipo de la lista', () => {
    fixture.componentInstance.newCell();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    const codigo = root.querySelector<HTMLInputElement>('#codigo')!;
    codigo.value = ' a-02 ';
    codigo.dispatchEvent(new Event('input', { bubbles: true }));
    const tipo = root.querySelector<HTMLSelectElement>('#tipo')!;
    expect([...tipo.options].map((o) => o.value)).toEqual(['', 'CARRO_CAMIONETA', 'MOTO']);
    tipo.value = 'CARRO_CAMIONETA';
    tipo.dispatchEvent(new Event('change', { bubbles: true }));
    root
      .querySelector('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    fixture.componentInstance.save();
    const request = http.expectOne({ method: 'POST', url: '/celdas' });
    expect(request.request.body).toEqual({ codigo: 'A-02', tipo: 'CARRO_CAMIONETA' });
    request.flush({ ...cell, codigo: 'A-02' });
    http
      .expectOne('/celdas?offset=0&limit=10')
      .flush({ items: [cell], total: 1, offset: 0, limit: 10 });
    expect(fixture.componentInstance.success()).toContain('registrada');
  });

  it('rechaza blancos y muestra duplicados junto al código', () => {
    const c = fixture.componentInstance;
    c.newCell();
    c.form.setValue({ codigo: ' ', tipo: ' ' });
    c.save();
    expect(c.form.invalid).toBe(true);
    c.form.setValue({ codigo: 'A-01', tipo: 'MOTO' });
    c.save();
    http.expectOne('/celdas').flush({}, { status: 409, statusText: 'Conflict' });
    expect(c.fieldError('codigo')).toContain('Ya existe');
  });

  it('edita mediante PATCH y recarga la lista', () => {
    const c = fixture.componentInstance;
    c.edit(cell);
    http.expectOne('/celdas/1').flush(cell);
    c.form.controls.tipo.setValue('CARRO_CAMIONETA');
    c.save();
    const request = http.expectOne({ method: 'PATCH', url: '/celdas/1' });
    expect(request.request.body.id).toBeUndefined();
    request.flush({ ...cell, tipo: 'CARRO_CAMIONETA' });
    http
      .expectOne('/celdas?offset=0&limit=10')
      .flush({ items: [cell], total: 1, offset: 0, limit: 10 });
  });

  it('requiere confirmación y permite cancelar antes de eliminar', () => {
    const c = fixture.componentInstance;
    c.confirmDelete(cell);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alertdialog"]').textContent).toContain(
      'A-01',
    );
    c.cancel();
    http.expectNone((request) => request.method === 'DELETE');
    c.confirmDelete(cell);
    c.remove();
    http
      .expectOne({ method: 'DELETE', url: '/celdas/1' })
      .flush(null, { status: 204, statusText: 'No Content' });
    http
      .expectOne('/celdas?offset=0&limit=10')
      .flush({ items: [], total: 0, offset: 0, limit: 10 });
    expect(c.success()).toContain('eliminada');
  });
});
