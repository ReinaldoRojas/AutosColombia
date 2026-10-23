import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, ValidatorFn, Validators } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { Celda } from '../models/celda';
import { Operador } from '../models/operador';
import { MENSAJE_PLACA, normalizarPlaca } from '../models/vehiculo';
import { EstadoVehiculo } from '../models/estancia';
import { EstanciasService } from '../services/estancias.service';

const nonBlank: ValidatorFn = (c) =>
  typeof c.value === 'string' && c.value.trim() ? null : { required: true };
const placa = (value: string) => normalizarPlaca(value) ?? value.trim().toUpperCase();
const colombianPlate: ValidatorFn = (c) =>
  typeof c.value !== 'string' || !c.value.trim() || normalizarPlaca(c.value)
    ? null
    : { placa: true };

@Component({
  selector: 'app-control-acceso',
  imports: [ReactiveFormsModule],
  templateUrl: './control-acceso.html',
  styleUrl: './control-acceso.css',
})
export class ControlAcceso {
  readonly mensajePlaca = MENSAJE_PLACA;
  private readonly api = inject(EstanciasService);
  private readonly fb = inject(FormBuilder);
  private readonly destroy = inject(DestroyRef);
  private version = 0;
  readonly entrada = this.fb.group({
    placa: this.fb.nonNullable.control('', [nonBlank, colombianPlate]),
    celda_id: this.fb.control<number | null>(null, Validators.required),
    operador_id: this.fb.control<number | null>(null, Validators.required),
  });
  readonly consulta = this.fb.group({
    placa: this.fb.nonNullable.control('', [nonBlank, colombianPlate]),
    operador_id: this.fb.control<number | null>(null, Validators.required),
  });
  readonly celdas = signal<Celda[]>([]);
  readonly operadores = signal<Operador[]>([]);
  readonly catalogLoading = signal(false);
  readonly catalogError = signal('');
  readonly saving = signal(false);
  readonly querying = signal(false);
  readonly busy = computed(() => this.saving() || this.querying());
  readonly estado = signal<EstadoVehiculo | null>(null);
  readonly errorEntrada = signal('');
  readonly errorConsulta = signal('');
  readonly exitoEntrada = signal('');
  readonly exitoSalida = signal('');

  constructor() {
    this.consulta.controls.placa.valueChanges
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe(() => {
        this.version++;
        this.estado.set(null);
        this.errorConsulta.set('');
        this.exitoSalida.set('');
      });
    this.cargarCatalogos();
  }

  cargarCatalogos(): void {
    if (this.catalogLoading() || this.saving()) return;
    this.catalogLoading.set(true);
    this.catalogError.set('');
    this.entrada.controls.celda_id.reset();
    this.entrada.controls.operador_id.reset();
    this.consulta.controls.operador_id.reset();
    forkJoin({ celdas: this.api.celdas(), operadores: this.api.operadores() })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (data) => {
          this.celdas.set(data.celdas);
          this.operadores.set(data.operadores);
          this.catalogLoading.set(false);
        },
        error: () => {
          this.catalogLoading.set(false);
          this.celdas.set([]);
          this.operadores.set([]);
          this.catalogError.set(
            'No se pudieron cargar todas las opciones. Reintenta actualizar catálogos.',
          );
        },
      });
  }

  registrarEntrada(): void {
    if (this.busy() || this.catalogLoading() || this.catalogError()) return;
    this.entrada.markAllAsTouched();
    if (this.entrada.invalid) return;
    const raw = this.entrada.getRawValue();
    const data = {
      placa: placa(raw.placa),
      celda_id: raw.celda_id!,
      operador_id: raw.operador_id!,
    };
    const codigo =
      this.celdas().find((c) => c.id === data.celda_id)?.codigo ?? String(data.celda_id);
    this.entrada.controls.placa.setValue(data.placa);
    this.saving.set(true);
    this.errorEntrada.set('');
    this.exitoEntrada.set('');
    this.version++;
    this.estado.set(null);
    this.api
      .entrada(data)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (result) => {
          this.saving.set(false);
          this.exitoEntrada.set(
            `Entrada registrada: ${data.placa}, celda ${codigo}, ${this.fecha(result.entrada)}.`,
          );
        },
        error: (error) => {
          this.saving.set(false);
          this.errorEntrada.set(this.mensaje(error));
        },
      });
  }

  buscar(): void {
    if (this.busy()) return;
    this.consulta.controls.placa.markAsTouched();
    if (this.consulta.controls.placa.invalid) return;
    const value = placa(this.consulta.controls.placa.value);
    this.consulta.controls.placa.setValue(value, { emitEvent: false });
    const version = ++this.version;
    this.estado.set(null);
    this.errorConsulta.set('');
    this.querying.set(true);
    this.api
      .consultar(value)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (result) => {
          this.querying.set(false);
          if (version === this.version) this.estado.set(result);
        },
        error: (error) => {
          this.querying.set(false);
          if (version === this.version)
            this.errorConsulta.set(
              error.status === 404 ? 'Vehículo no registrado.' : this.mensaje(error),
            );
        },
      });
  }

  registrarSalida(): void {
    if (this.busy() || this.catalogLoading() || this.catalogError()) return;
    this.consulta.markAllAsTouched();
    const state = this.estado();
    const value = placa(this.consulta.controls.placa.value);
    if (
      this.consulta.invalid ||
      !state?.estancia ||
      !state.esta_dentro ||
      state.vehiculo.placa !== value
    )
      return;
    const version = this.version;
    this.saving.set(true);
    this.errorConsulta.set('');
    this.exitoSalida.set('');
    this.api
      .salida({ placa: value, operador_id: this.consulta.controls.operador_id.value! })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (result) => {
          this.saving.set(false);
          this.estado.set(null);
          if (version !== this.version) return;
          this.exitoSalida.set(
            `Salida registrada: ${value}, celda ${state.estancia!.celda.codigo}, ${this.fecha(result.salida!)}.`,
          );
          this.buscar();
        },
        error: (error) => {
          this.saving.set(false);
          this.estado.set(null);
          if (version === this.version)
            this.errorConsulta.set(
              this.mensaje(error) + ' Consulta nuevamente antes de confirmar otra salida.',
            );
        },
      });
  }

  fecha(value: string): string {
    return (
      new Intl.DateTimeFormat('es-CO', {
        timeZone: 'America/Bogota',
        dateStyle: 'medium',
        timeStyle: 'medium',
      }).format(new Date(value)) + ' (Bogotá)'
    );
  }

  private mensaje(error: HttpErrorResponse): string {
    if ([404, 409].includes(error.status) && typeof error.error?.detail === 'string')
      return error.error.detail;
    if (error.status === 422)
      return 'Datos inválidos. Revisa la placa y selecciona una celda y un operador válidos según la operación.';
    return 'No se pudo conectar con el servicio. Consulta el vehículo antes de reintentar: la operación podría haberse completado.';
  }
}
