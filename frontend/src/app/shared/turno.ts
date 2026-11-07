import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { Puerta } from '../models/estancia';
import { Operador } from '../models/operador';
import { EstanciasService } from '../services/estancias.service';
import { OperadoresService } from '../services/operadores.service';
import { TurnoService } from './turno.service';

/** Selección del operador y la puerta que registran los movimientos. */
@Component({
  selector: 'app-turno',
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    @if (turnos.turno(); as t) {
      <div class="notice info turno-activo" role="status">
        <span
          >Turno: <b>{{ t.operador.nombre }}</b> · <b>{{ t.puerta.nombre }}</b></span
        >
        <button type="button" (click)="turnos.cerrar(); cargar()">Cambiar turno</button>
      </div>
    } @else {
      <section class="panel turno" aria-labelledby="turno-title">
        <h2 id="turno-title">Inicia tu turno</h2>
        <p class="hint">
          Cada entrada, salida y cambio de celda queda registrado con el operador y la puerta.
        </p>
        @if (error()) {
          <p class="notice error" role="alert">{{ error() }}</p>
        }
        <form [formGroup]="form" (ngSubmit)="iniciar()">
          <div class="form-grid">
            <div class="field">
              <label for="turno-operador">Operador</label>
              <select id="turno-operador" formControlName="operador">
                <option [ngValue]="null">Selecciona tu nombre</option>
                @for (o of operadores(); track o.id) {
                  <option [ngValue]="o">{{ o.nombre }}</option>
                }
              </select>
            </div>
            <div class="field">
              <label for="turno-puerta">Puerta</label>
              <select id="turno-puerta" formControlName="puerta">
                <option [ngValue]="null">Selecciona la puerta</option>
                @for (p of puertas(); track p.id) {
                  <option [ngValue]="p">{{ p.nombre }}</option>
                }
              </select>
            </div>
            <div class="field turno-boton">
              <button class="primary" type="submit" [disabled]="form.invalid">Iniciar turno</button>
            </div>
          </div>
        </form>
        @if (!cargando() && !operadores().length && !error()) {
          <p class="hint">
            No hay operadores registrados.
            <a routerLink="/gestion/operadores">Registra uno</a> para comenzar.
          </p>
        }
      </section>
    }
  `,
  styles: `
    .turno-activo {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
      margin: 0 0 20px;
    }
    .turno-boton {
      justify-content: flex-end;
    }
  `,
})
export class TurnoComponent {
  readonly turnos = inject(TurnoService);
  private readonly api = inject(EstanciasService);
  private readonly operadoresApi = inject(OperadoresService);
  private readonly destroy = inject(DestroyRef);
  readonly form = inject(FormBuilder).group({
    operador: [null as Operador | null, Validators.required],
    puerta: [null as Puerta | null, Validators.required],
  });
  readonly operadores = signal<Operador[]>([]);
  readonly puertas = signal<Puerta[]>([]);
  readonly cargando = signal(false);
  readonly error = signal('');

  constructor() {
    if (!this.turnos.activo()) this.cargar();
  }

  cargar(): void {
    this.cargando.set(true);
    this.error.set('');
    forkJoin({ o: this.operadoresApi.list(0, 100), p: this.api.puertas() })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: ({ o, p }) => {
          this.operadores.set(o.items);
          this.puertas.set(p);
          this.cargando.set(false);
        },
        error: () => {
          this.cargando.set(false);
          this.error.set('No se pudieron cargar los operadores y las puertas. Recarga la página.');
        },
      });
  }

  iniciar(): void {
    const { operador, puerta } = this.form.getRawValue();
    if (!operador || !puerta) return;
    this.turnos.iniciar({ operador: { id: operador.id, nombre: operador.nombre }, puerta });
  }
}
