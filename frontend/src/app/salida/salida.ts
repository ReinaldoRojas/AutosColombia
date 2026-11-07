import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { Movimiento } from '../models/estancia';
import { MENSAJE_PLACA, NOMBRE_TIPO, normalizarPlaca } from '../models/vehiculo';
import { EstanciasService } from '../services/estancias.service';
import { fechaHora, mensajeError, noVacio, placaColombiana } from '../shared/formato';
import { TurnoComponent } from '../shared/turno';
import { TurnoService } from '../shared/turno.service';

/** Salida por placa con el operador del turno. Sus mejoras (recibo, puerta) corresponden a RF-07. */
@Component({
  selector: 'app-salida',
  imports: [ReactiveFormsModule, TurnoComponent],
  templateUrl: './salida.html',
  styleUrl: './salida.css',
})
export class Salida {
  readonly mensajePlaca = MENSAJE_PLACA;
  readonly turnos = inject(TurnoService);
  private readonly api = inject(EstanciasService);
  private readonly destroy = inject(DestroyRef);
  readonly form = inject(FormBuilder).nonNullable.group({
    placa: ['', [noVacio, placaColombiana]],
  });
  readonly registro = signal<Movimiento | null>(null);
  readonly salida = signal<Movimiento | null>(null);
  readonly error = signal('');
  readonly buscando = signal(false);
  readonly guardando = signal(false);
  readonly ocupado = computed(() => this.buscando() || this.guardando());
  readonly fecha = fechaHora;
  private version = 0;

  constructor() {
    this.form.controls.placa.valueChanges.pipe(takeUntilDestroyed(this.destroy)).subscribe(() => {
      if (this.buscando()) return;
      this.version++;
      this.registro.set(null);
      this.error.set('');
    });
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
    this.salida.set(null);
    this.registro.set(null);
    this.error.set('');
    this.buscando.set(true);
    this.api
      .consultar(placa)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (consulta) => {
          this.buscando.set(false);
          if (version !== this.version) return;
          if (consulta.estancia) this.registro.set(consulta.estancia);
          else this.error.set('Este vehículo no tiene un ingreso abierto.');
        },
        error: (error: HttpErrorResponse) => {
          this.buscando.set(false);
          if (version === this.version) this.error.set(mensajeError(error));
        },
      });
  }

  confirmar(): void {
    const registro = this.registro();
    const turno = this.turnos.turno();
    if (this.ocupado() || !registro || !turno) return;
    this.guardando.set(true);
    this.error.set('');
    this.api
      .salida({ placa: registro.placa, operador_id: turno.operador.id })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (movimiento) => {
          this.guardando.set(false);
          this.registro.set(null);
          this.salida.set(movimiento);
          this.form.reset();
        },
        error: (error: HttpErrorResponse) => {
          this.guardando.set(false);
          this.error.set(mensajeError(error));
        },
      });
  }
}
