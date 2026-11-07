import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ConsultaVehiculo, Movimiento } from '../models/estancia';
import { MENSAJE_PLACA, NOMBRE_TIPO, normalizarPlaca } from '../models/vehiculo';
import { EstanciasService } from '../services/estancias.service';
import {
  NOMBRE_MENSUALIDAD,
  claseMensualidad,
  fechaDia,
  mensajeError,
  noVacio,
  placaColombiana,
} from '../shared/formato';
import { ReciboComponent } from '../shared/recibo';
import { TurnoComponent } from '../shared/turno';
import { TurnoService } from '../shared/turno.service';

/** HU-03 a HU-06: digitar placa, verificar datos y confirmar (máximo 3 pasos, RNF-08). */
@Component({
  selector: 'app-entrada',
  imports: [ReactiveFormsModule, RouterLink, TurnoComponent, ReciboComponent],
  templateUrl: './entrada.html',
  styleUrl: './entrada.css',
})
export class Entrada {
  readonly mensajePlaca = MENSAJE_PLACA;
  readonly turnos = inject(TurnoService);
  private readonly api = inject(EstanciasService);
  private readonly destroy = inject(DestroyRef);
  readonly form = inject(FormBuilder).nonNullable.group({
    placa: ['', [noVacio, placaColombiana]],
  });
  readonly consulta = signal<ConsultaVehiculo | null>(null);
  readonly noRegistrada = signal<string | null>(null);
  readonly ingreso = signal<Movimiento | null>(null);
  readonly error = signal('');
  readonly buscando = signal(false);
  readonly guardando = signal(false);
  readonly ocupado = computed(() => this.buscando() || this.guardando());
  readonly fechaDia = fechaDia;
  readonly claseMensualidad = claseMensualidad;
  readonly nombreMensualidad = NOMBRE_MENSUALIDAD;
  private version = 0;

  constructor() {
    this.form.controls.placa.valueChanges.pipe(takeUntilDestroyed(this.destroy)).subscribe(() => {
      if (this.buscando()) return;
      this.version++;
      this.consulta.set(null);
      this.noRegistrada.set(null);
      this.error.set('');
    });
  }

  claseAviso(estado: string): string {
    const clase = claseMensualidad(estado);
    return clase === 'ok' ? 'success' : clase === 'warn' ? 'warning' : 'error';
  }

  tipo(value: string): string {
    return NOMBRE_TIPO[value] ?? value;
  }

  buscar(): void {
    if (this.ocupado()) return;
    this.form.controls.placa.markAsTouched();
    if (this.form.invalid) return;
    const placa = normalizarPlaca(this.form.controls.placa.value)!;
    this.form.controls.placa.setValue(placa, { emitEvent: false });
    const version = ++this.version;
    this.consulta.set(null);
    this.noRegistrada.set(null);
    this.ingreso.set(null);
    this.error.set('');
    this.buscando.set(true);
    this.api
      .consultar(placa)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (result) => {
          this.buscando.set(false);
          if (version === this.version) this.consulta.set(result);
        },
        error: (error: HttpErrorResponse) => {
          this.buscando.set(false);
          if (version !== this.version) return;
          if (error.status === 404) this.noRegistrada.set(placa);
          else this.error.set(mensajeError(error));
        },
      });
  }

  confirmar(): void {
    const consulta = this.consulta();
    const turno = this.turnos.turno();
    if (this.ocupado() || !consulta?.puede_ingresar || !turno) return;
    this.guardando.set(true);
    this.error.set('');
    this.api
      .entrada({
        placa: consulta.vehiculo.placa,
        operador_id: turno.operador.id,
        puerta_id: turno.puerta.id,
      })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (movimiento) => {
          this.guardando.set(false);
          this.consulta.set(null);
          this.ingreso.set(movimiento);
        },
        error: (error: HttpErrorResponse) => {
          this.guardando.set(false);
          this.error.set(mensajeError(error));
          // Otra puerta pudo cambiar el cupo o la estancia: se vuelve a consultar.
          if (error.status === 409) this.consulta.set(null);
        },
      });
  }

  imprimir(): void {
    window.print();
  }

  nuevo(): void {
    this.ingreso.set(null);
    this.consulta.set(null);
    this.form.reset();
  }
}
