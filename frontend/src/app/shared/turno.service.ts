import { Injectable, computed, signal } from '@angular/core';
import { OperadorResumen, Puerta } from '../models/estancia';

export interface Turno {
  operador: OperadorResumen;
  puerta: Puerta;
}

const CLAVE = 'autos-colombia.turno';

/**
 * Operador y puerta que registran los movimientos (RNF-07).
 * Reemplaza provisionalmente al inicio de sesión (RNF-05), que queda pendiente.
 */
@Injectable({ providedIn: 'root' })
export class TurnoService {
  private readonly estado = signal<Turno | null>(this.leer());
  readonly turno = this.estado.asReadonly();
  readonly activo = computed(() => this.estado() !== null);

  iniciar(turno: Turno): void {
    this.estado.set(turno);
    try {
      localStorage.setItem(CLAVE, JSON.stringify(turno));
    } catch {
      // Sin almacenamiento, el turno dura mientras la pestaña esté abierta.
    }
  }

  cerrar(): void {
    this.estado.set(null);
    try {
      localStorage.removeItem(CLAVE);
    } catch {
      // Ignorado: el estado en memoria ya se limpió.
    }
  }

  private leer(): Turno | null {
    try {
      const valor = JSON.parse(localStorage.getItem(CLAVE) ?? 'null');
      if (
        typeof valor?.operador?.id === 'number' &&
        typeof valor?.operador?.nombre === 'string' &&
        typeof valor?.puerta?.id === 'number' &&
        typeof valor?.puerta?.nombre === 'string'
      )
        return valor as Turno;
    } catch {
      // Valor ausente o dañado: se pide el turno de nuevo.
    }
    return null;
  }
}
