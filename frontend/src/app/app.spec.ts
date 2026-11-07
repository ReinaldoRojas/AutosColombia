import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';

describe('Navegación', () => {
  it('ofrece entrada, salida, clientes y las gestiones existentes', async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([])],
    }).compileComponents();
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const nav = (fixture.nativeElement as HTMLElement).querySelector('nav')!;
    const enlaces = [...nav.querySelectorAll('a')].map((a) => [
      a.getAttribute('href'),
      a.textContent?.trim(),
    ]);
    expect(enlaces).toEqual([
      ['/operacion/entrada', 'Entrada'],
      ['/operacion/salida', 'Salida'],
      ['/gestion/clientes', 'Clientes'],
      ['/gestion/operadores', 'Operadores'],
      ['/gestion/celdas', 'Celdas'],
      ['/', 'Inicio'],
    ]);
  });
});
