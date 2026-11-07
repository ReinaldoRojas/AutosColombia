import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AbstractControl, FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Cliente, ClienteDetalle, TIPOS_DOCUMENTO, TipoDocumento } from '../models/cliente';
import {
  MENSAJE_PLACA,
  NOMBRE_TIPO,
  TIPOS_VEHICULO,
  TipoVehiculo,
  Vehiculo,
  normalizarPlaca,
} from '../models/vehiculo';
import { ApiService } from '../services/api.service';
import { ClientesService } from '../services/clientes.service';
import {
  NOMBRE_MENSUALIDAD,
  claseMensualidad,
  fechaDia,
  hoyColombia,
  mensajeError,
  noVacio,
  placaColombiana,
} from '../shared/formato';

const TELEFONO = /^(\+?57)?(3\d{9}|60[1-8]\d{7})$/;
const CORREO = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/** HU-01 y HU-02: registrar al cliente y asociarle uno o varios vehículos con su mensualidad. */
@Component({
  selector: 'app-clientes',
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './clientes.html',
  styleUrl: './clientes.css',
})
export class Clientes {
  readonly tiposDocumento = TIPOS_DOCUMENTO;
  readonly tiposVehiculo = TIPOS_VEHICULO;
  readonly mensajePlaca = MENSAJE_PLACA;
  readonly nombreTipo = NOMBRE_TIPO;
  readonly nombreMensualidad = NOMBRE_MENSUALIDAD;
  readonly claseMensualidad = claseMensualidad;
  readonly fechaDia = fechaDia;
  private readonly api = inject(ClientesService);
  private readonly vehiculosApi = inject(ApiService);
  private readonly destroy = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);
  readonly busqueda = this.fb.nonNullable.control('');
  readonly clientes = signal<Cliente[]>([]);
  readonly total = signal(0);
  readonly ficha = signal<ClienteDetalle | null>(null);
  readonly creando = signal(false);
  readonly agregandoVehiculo = signal(false);
  readonly guardando = signal(false);
  readonly error = signal('');
  readonly exito = signal('');
  /** Placa que llegó desde «Registrar entrada» cuando el vehículo no existía. */
  readonly placaPendiente = signal<string | null>(null);

  readonly cliente = this.fb.nonNullable.group({
    tipo_documento: ['CC' as TipoDocumento, Validators.required],
    numero_documento: ['', [noVacio, Validators.pattern(/^[\s.\-0-9A-Za-z]{3,30}$/)]],
    nombres: ['', noVacio],
    apellidos: ['', noVacio],
    telefono: ['', [noVacio, Validators.pattern(TELEFONO)]],
    correo: ['', Validators.pattern(CORREO)],
  });
  readonly vehiculo = this.fb.nonNullable.group({
    placa: ['', [noVacio, placaColombiana]],
    tipo: ['CARRO' as TipoVehiculo, Validators.required],
    marca: ['', noVacio],
    linea: ['', noVacio],
    modelo: [
      new Date().getFullYear(),
      [Validators.required, Validators.min(1950), Validators.max(2100)],
    ],
    color: ['', noVacio],
    fecha_pago: [hoyColombia(), Validators.required],
  });

  constructor() {
    const placa = normalizarPlaca(inject(ActivatedRoute).snapshot.queryParamMap.get('placa') ?? '');
    if (placa) {
      this.placaPendiente.set(placa);
      this.nuevoCliente();
    }
    this.buscar();
  }

  buscar(): void {
    this.api
      .list(this.busqueda.value, 0, 20)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (page) => {
          this.clientes.set(page.items);
          this.total.set(page.total);
        },
        error: (error: HttpErrorResponse) => this.error.set(mensajeError(error)),
      });
  }

  nuevoCliente(): void {
    this.ficha.set(null);
    this.cliente.reset();
    this.creando.set(true);
    this.error.set('');
    this.exito.set('');
  }

  abrir(id: number, mensaje = ''): void {
    this.api
      .get(id)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (ficha) => {
          this.ficha.set(ficha);
          this.creando.set(false);
          this.exito.set(mensaje);
          this.error.set('');
          if (this.placaPendiente()) this.agregarVehiculo();
          else this.agregandoVehiculo.set(false);
        },
        error: (error: HttpErrorResponse) => this.error.set(mensajeError(error)),
      });
  }

  guardarCliente(): void {
    this.cliente.markAllAsTouched();
    if (this.guardando() || this.cliente.invalid) return;
    const raw = this.cliente.getRawValue();
    this.guardando.set(true);
    this.error.set('');
    this.api
      .create({ ...raw, correo: raw.correo.trim() || null })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (ficha) => {
          this.guardando.set(false);
          this.buscar();
          this.abrir(ficha.id, 'Cliente registrado correctamente. Ahora agrega su vehículo.');
        },
        error: (error: HttpErrorResponse) => {
          this.guardando.set(false);
          const existente = error.status === 409 ? error.error?.cliente_id : null;
          // HU-01 criterio 2: si ya existe, se abre su información.
          if (typeof existente === 'number')
            this.abrir(existente, 'El cliente ya está registrado.');
          else this.error.set(mensajeError(error));
        },
      });
  }

  agregarVehiculo(): void {
    this.vehiculo.reset();
    const placa = this.placaPendiente();
    if (placa) this.vehiculo.controls.placa.setValue(placa);
    this.agregandoVehiculo.set(true);
  }

  guardarVehiculo(): void {
    const ficha = this.ficha();
    this.vehiculo.markAllAsTouched();
    if (this.guardando() || !ficha || this.vehiculo.invalid) return;
    const raw = this.vehiculo.getRawValue();
    const placa = normalizarPlaca(raw.placa)!;
    this.guardando.set(true);
    this.error.set('');
    this.vehiculosApi
      .create({ ...raw, placa, modelo: Number(raw.modelo), cliente_id: ficha.id })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (v) => {
          this.guardando.set(false);
          this.placaPendiente.set(null);
          this.abrir(
            ficha.id,
            `Vehículo ${v.placa} registrado. Mensualidad vence el ${fechaDia(v.fecha_vencimiento)}.`,
          );
        },
        error: (error: HttpErrorResponse) => {
          this.guardando.set(false);
          this.error.set(
            error.status === 409 ? 'La placa ya está registrada.' : mensajeError(error),
          );
        },
      });
  }

  estado(v: Vehiculo): string {
    if (!v.fecha_vencimiento) return 'SIN_PAGO';
    const hoy = hoyColombia();
    if (v.fecha_vencimiento > hoy) return 'VIGENTE';
    return v.fecha_vencimiento === hoy ? 'VENCE_HOY' : 'VENCIDA';
  }

  invalido(grupo: 'cliente' | 'vehiculo', campo: string): boolean {
    const form: AbstractControl = grupo === 'cliente' ? this.cliente : this.vehiculo;
    const control = form.get(campo);
    return !!control && control.touched && control.invalid;
  }
}
