import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, ValidatorFn } from '@angular/forms';
import { OperadoresService } from '../services/operadores.service';
import { Operador, OperadorCrear } from '../models/operador';
import { ErrorApi } from '../models/vehiculo';

const nonBlank: ValidatorFn = (control) =>
  typeof control.value === 'string' && control.value.trim() ? null : { required: true };
type Field = keyof OperadorCrear;

/** Devuelve los 10 dígitos de un celular (3XX) o fijo con indicativo (60X), o null si no es colombiano. */
export function normalizarTelefono(value: string): string | null {
  let digits = value.replace(/[\s\-.()]/g, '');
  if (digits.startsWith('+57')) digits = digits.slice(3);
  else if (digits.startsWith('0057')) digits = digits.slice(4);
  else if (digits.length === 12 && digits.startsWith('57')) digits = digits.slice(2);
  return /^(3\d{9}|60[1-8]\d{7})$/.test(digits) ? digits : null;
}

const colombianPhone: ValidatorFn = (control) =>
  typeof control.value !== 'string' || !control.value.trim() || normalizarTelefono(control.value)
    ? null
    : { telefono: true };

@Component({
  selector: 'app-operadores',
  imports: [ReactiveFormsModule],
  templateUrl: './operadores.html',
  styleUrl: './operadores.css',
})
export class Operadores {
  private readonly api = inject(OperadoresService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);
  readonly fields = [
    { key: 'nombre' as const, label: 'Nombre' },
    { key: 'telefono' as const, label: 'Teléfono' },
  ];
  readonly form = this.fb.group({
    nombre: this.fb.nonNullable.control('', nonBlank),
    telefono: this.fb.nonNullable.control('', [nonBlank, colombianPhone]),
  });
  readonly items = signal<Operador[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly limit = 10;
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly busy = computed(() => this.loading() || this.saving());
  readonly showForm = signal(false);
  readonly editing = signal<number | null>(null);
  readonly pendingDelete = signal<Operador | null>(null);
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

  newOperator(): void {
    if (this.busy()) return;
    this.form.reset();
    this.editing.set(null);
    this.showForm.set(true);
    this.pendingDelete.set(null);
    this.actionError.set('');
    this.success.set('');
  }

  edit(operator: Operador): void {
    if (this.busy()) return;
    this.loading.set(true);
    this.actionError.set('');
    this.success.set('');
    this.pendingDelete.set(null);
    this.api
      .get(operator.id)
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
    if (control.errors['telefono'])
      return 'Ingresa un teléfono colombiano: celular de 10 dígitos que empieza por 3 (ej. 322 656 1122) o fijo con indicativo (ej. 601 234 5678). El +57 es opcional.';
    return 'Revisa este campo.';
  }

  save(): void {
    if (this.busy()) return;
    this.form.markAllAsTouched();
    if (this.form.invalid) {
      this.actionError.set('Revisa los campos señalados antes de guardar el operador.');
      return;
    }
    const value = this.form.getRawValue();
    const payload: OperadorCrear = {
      nombre: value.nombre.trim(),
      telefono: normalizarTelefono(value.telefono) ?? value.telefono.trim(),
    };
    this.form.setValue(payload);
    this.saving.set(true);
    this.actionError.set('');
    this.success.set('');
    const id = this.editing();
    const request = id === null ? this.api.create(payload) : this.api.update(id, payload);
    request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (operator) => {
        this.saving.set(false);
        this.showForm.set(false);
        this.success.set(
          `Operador ${operator.nombre} ${id === null ? 'registrado' : 'actualizado'} correctamente.`,
        );
        this.load();
      },
      error: (error: HttpErrorResponse) => {
        this.saving.set(false);
        this.actionError.set(this.errorMessage(error));
        const body = error.error as ErrorApi | null;
        if (
          error.status === 409 &&
          typeof body?.detail === 'string' &&
          /teléfono/i.test(body.detail)
        )
          this.setFieldError('telefono', body.detail);
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

  confirmDelete(operator: Operador): void {
    if (this.busy()) return;
    this.pendingDelete.set(operator);
    this.showForm.set(false);
    this.actionError.set('');
    this.success.set('');
  }

  remove(): void {
    const operator = this.pendingDelete();
    if (!operator || this.busy()) return;
    this.saving.set(true);
    this.actionError.set('');
    this.api
      .delete(operator.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.pendingDelete.set(null);
          this.success.set(`Operador ${operator.nombre} eliminado correctamente.`);
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
    if (error.status === 404) return 'El operador ya no existe. Actualiza el listado.';
    if (error.status === 409)
      return deleting
        ? 'No se puede eliminar: el operador tiene registros relacionados o un conflicto con otros datos.'
        : error.error?.detail === 'Ya existe un operador con ese teléfono.'
          ? 'Ya existe un operador con ese teléfono.'
          : 'La operación entra en conflicto con los datos existentes.';
    if (error.status === 422)
      return 'Revisa los datos: hay campos que no cumplen las validaciones.';
    return 'No se pudo conectar con el servicio. Comprueba la conexión y actualiza el listado antes de reintentar.';
  }
}
