import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, ValidatorFn, Validators } from '@angular/forms';
import { ApiService } from '../services/api.service';
import {
  ErrorApi,
  MENSAJE_PLACA,
  TIPOS_VEHICULO,
  TipoVehiculo,
  Vehiculo,
  VehiculoCrear,
  normalizarPlaca,
} from '../models/vehiculo';

const nonBlank: ValidatorFn = (control) =>
  typeof control.value === 'string' && control.value.trim() ? null : { required: true };
const colombianPlate: ValidatorFn = (control) =>
  typeof control.value !== 'string' || !control.value.trim() || normalizarPlaca(control.value)
    ? null
    : { placa: true };
const year: ValidatorFn = (control) =>
  Number.isInteger(control.value) && control.value >= 1 && control.value <= 9999
    ? null
    : { year: true };
type Field = keyof VehiculoCrear;

@Component({
  selector: 'app-vehiculos',
  imports: [ReactiveFormsModule],
  templateUrl: './vehiculos.html',
  styleUrl: './vehiculos.css',
})
export class Vehiculos {
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);
  readonly types = TIPOS_VEHICULO;
  readonly fields: { key: 'placa' | 'color' | 'modelo' | 'marca'; label: string; type: string }[] =
    [
      { key: 'placa', label: 'Placa', type: 'text' },
      { key: 'marca', label: 'Marca', type: 'text' },
      { key: 'modelo', label: 'Modelo (año)', type: 'number' },
      { key: 'color', label: 'Color', type: 'text' },
    ];
  readonly form = this.fb.group({
    placa: this.fb.nonNullable.control('', [nonBlank, colombianPlate]),
    color: this.fb.nonNullable.control('', nonBlank),
    modelo: this.fb.control<number | null>(null, [Validators.required, year]),
    marca: this.fb.nonNullable.control('', nonBlank),
    tipo: this.fb.nonNullable.control<TipoVehiculo | ''>('', [
      Validators.required,
      (control) => (this.types.includes(control.value) ? null : { type: true }),
    ]),
  });
  readonly items = signal<Vehiculo[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly limit = 10;
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly busy = computed(() => this.loading() || this.saving());
  readonly showForm = signal(false);
  readonly editing = signal<number | null>(null);
  readonly pendingDelete = signal<Vehiculo | null>(null);
  readonly listError = signal('');
  readonly actionError = signal('');
  readonly success = signal('');
  readonly page = computed(() => Math.floor(this.offset() / this.limit) + 1);
  readonly pages = computed(() => Math.max(1, Math.ceil(this.total() / this.limit)));

  constructor() {
    this.load();
  }

  load(offset = this.offset()): void {
    if (this.busy()) return;
    this.loading.set(true);
    this.listError.set('');
    this.api
      .list(offset, this.limit)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => {
          this.loading.set(false);
          if (offset > 0 && offset >= data.total) {
            this.load(Math.max(0, Math.floor((data.total - 1) / this.limit) * this.limit));
            return;
          }
          this.items.set(data.items);
          this.total.set(data.total);
          this.offset.set(offset);
        },
        error: (error) => {
          this.loading.set(false);
          this.listError.set(this.errorMessage(error));
        },
      });
  }

  newVehicle(): void {
    if (this.busy()) return;
    this.form.reset();
    this.editing.set(null);
    this.showForm.set(true);
    this.pendingDelete.set(null);
    this.actionError.set('');
    this.success.set('');
  }

  edit(vehicle: Vehiculo): void {
    if (this.busy()) return;
    this.loading.set(true);
    this.actionError.set('');
    this.success.set('');
    this.pendingDelete.set(null);
    this.api
      .get(vehicle.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data) => {
          this.loading.set(false);
          this.editing.set(data.id);
          this.form.reset(data);
          this.showForm.set(true);
        },
        error: (error) => {
          this.loading.set(false);
          this.actionError.set(this.errorMessage(error));
        },
      });
  }

  cancel(): void {
    if (this.busy()) return;
    this.showForm.set(false);
    this.pendingDelete.set(null);
    this.actionError.set('');
  }

  fieldError(field: Field): string {
    const control = this.form.controls[field];
    if (!control.touched || !control.errors) return '';
    if (control.errors['server']) return String(control.errors['server']);
    if (control.errors['required']) return 'Este campo es obligatorio y no puede estar vacío.';
    if (control.errors['placa']) return MENSAJE_PLACA;
    if (field === 'modelo') return 'Introduce un año entero entre 1 y 9999.';
    if (field === 'tipo') return 'Selecciona un tipo válido.';
    return 'Revisa este campo.';
  }

  save(): void {
    if (this.busy()) return;
    this.form.markAllAsTouched();
    if (this.form.invalid) {
      this.actionError.set('Revisa los campos señalados antes de guardar el vehículo.');
      return;
    }
    const value = this.form.getRawValue();
    const payload: VehiculoCrear = {
      placa: normalizarPlaca(value.placa) ?? value.placa.trim().toUpperCase(),
      color: value.color.trim(),
      marca: value.marca.trim(),
      modelo: value.modelo!,
      tipo: value.tipo as TipoVehiculo,
    };
    this.form.controls.placa.setValue(payload.placa);
    this.saving.set(true);
    this.actionError.set('');
    this.success.set('');
    const id = this.editing();
    const request = id === null ? this.api.create(payload) : this.api.update(id, payload);
    request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (vehicle) => {
        this.saving.set(false);
        this.showForm.set(false);
        this.success.set(
          `Vehículo ${vehicle.placa} ${id === null ? 'registrado' : 'actualizado'} correctamente.`,
        );
        this.load();
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.actionError.set(this.errorMessage(error));
        if (error.status === 409)
          this.setFieldError('placa', 'Ya existe un vehículo con esa placa.');
        const body = error.error as ErrorApi | null;
        if (error.status === 422 && Array.isArray(body?.detail)) {
          for (const issue of body.detail) {
            const field = issue.loc.at(-1);
            if (typeof field === 'string' && Object.hasOwn(this.form.controls, field)) {
              this.setFieldError(
                field as Field,
                'El servicio rechazó este valor. Revisa el campo.',
              );
            }
          }
        }
      },
    });
  }

  private setFieldError(field: Field, message: string): void {
    this.form.controls[field].setErrors({ server: message });
    this.form.controls[field].markAsTouched();
  }

  confirmDelete(vehicle: Vehiculo): void {
    if (this.busy()) return;
    this.pendingDelete.set(vehicle);
    this.showForm.set(false);
    this.actionError.set('');
    this.success.set('');
  }

  remove(): void {
    const vehicle = this.pendingDelete();
    if (!vehicle || this.busy()) return;
    this.saving.set(true);
    this.actionError.set('');
    this.api
      .delete(vehicle.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.pendingDelete.set(null);
          this.success.set(`Vehículo ${vehicle.placa} eliminado correctamente.`);
          this.load();
        },
        error: (error) => {
          this.saving.set(false);
          this.actionError.set(this.errorMessage(error, true));
          if (error.status === 404) {
            this.pendingDelete.set(null);
            this.load();
          }
        },
      });
  }

  private errorMessage(error: HttpErrorResponse, deleting = false): string {
    if (error.status === 404) return 'El vehículo ya no existe. Actualiza el listado.';
    if (error.status === 409)
      return deleting
        ? 'No se puede eliminar: el vehículo tiene registros relacionados o un conflicto con otros datos.'
        : 'Ya existe un vehículo con esa placa.';
    if (error.status === 422)
      return 'Revisa los datos: hay campos que no cumplen las validaciones.';
    return 'No se pudo conectar con el servicio. Comprueba la conexión y actualiza el listado antes de reintentar.';
  }
}
