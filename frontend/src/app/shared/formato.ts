import { HttpErrorResponse } from '@angular/common/http';
import { ValidatorFn } from '@angular/forms';
import { normalizarPlaca } from '../models/vehiculo';

const ZONA = 'America/Bogota';

/** Fecha y hora en la zona horaria de Colombia (RNF-11). */
export function fechaHora(value: string | null | undefined): string {
  if (!value) return '—';
  return new Intl.DateTimeFormat('es-CO', {
    timeZone: ZONA,
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(new Date(value));
}

export function hora(value: string): string {
  return new Intl.DateTimeFormat('es-CO', { timeZone: ZONA, timeStyle: 'short' }).format(
    new Date(value),
  );
}

/** Fechas ISO de solo día (AAAA-MM-DD) mostradas como DD/MM/AAAA, sin desfases de zona. */
export function fechaDia(value: string | null | undefined): string {
  if (!value) return '—';
  const [y, m, d] = value.split('-');
  return `${d}/${m}/${y}`;
}

/** Hoy en Colombia como AAAA-MM-DD. */
export function hoyColombia(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: ZONA }).format(new Date());
}

export const noVacio: ValidatorFn = (c) =>
  typeof c.value === 'string' && c.value.trim() ? null : { required: true };

export const placaColombiana: ValidatorFn = (c) =>
  typeof c.value !== 'string' || !c.value.trim() || normalizarPlaca(c.value)
    ? null
    : { placa: true };

/** Mensaje público del backend o uno genérico que no expone detalles. */
export function mensajeError(error: HttpErrorResponse, fallback422 = 'Revisa los datos.'): string {
  const detail = error.error?.detail;
  if ([404, 409, 422].includes(error.status) && typeof detail === 'string') return detail;
  if (error.status === 422 && Array.isArray(detail) && typeof detail[0]?.msg === 'string')
    return detail[0].msg.replace(/^Value error, /, '');
  if (error.status === 422) return fallback422;
  return 'No se pudo conectar con el servicio. Verifica antes de reintentar: la operación podría haberse completado.';
}

export function claseMensualidad(estado: string): string {
  if (estado === 'VIGENTE') return 'ok';
  if (estado === 'VENCE_HOY') return 'warn';
  return 'bad';
}

export const NOMBRE_MENSUALIDAD: Record<string, string> = {
  VIGENTE: 'Vigente',
  VENCE_HOY: 'Vence hoy',
  VENCIDA: 'Vencida',
  SIN_PAGO: 'Sin pago',
  SIN_CLIENTE: 'Sin cliente',
};
