import { Celda, TipoCelda } from './celda';
import { Cliente } from './cliente';
import { Vehiculo } from './vehiculo';

export interface Puerta {
  id: number;
  nombre: string;
}
export interface OperadorResumen {
  id: number;
  nombre: string;
}
export interface EntradaCrear {
  placa: string;
  operador_id: number;
  puerta_id: number;
}
export interface SalidaCrear {
  placa: string;
  operador_id: number;
}
/** Estancia con los datos del recibo de ingreso. */
export interface Movimiento {
  id: number;
  numero_recibo: string;
  vehiculo_id: number;
  placa: string;
  tipo_vehiculo: string;
  marca: string;
  linea: string | null;
  color: string;
  cliente: string | null;
  celda: Celda;
  entrada: string;
  salida: string | null;
  abierta: boolean;
  puerta_entrada: Puerta;
  puerta_salida: Puerta | null;
  operador_entrada: OperadorResumen;
  operador_salida: OperadorResumen | null;
}
export type EstadoMensualidad = 'VIGENTE' | 'VENCE_HOY' | 'VENCIDA' | 'SIN_PAGO' | 'SIN_CLIENTE';
export interface Mensualidad {
  estado: EstadoMensualidad;
  fecha_pago: string | null;
  fecha_vencimiento: string | null;
  dias: number | null;
  permite_ingreso: boolean;
  mensaje: string;
}
export interface Cupo {
  tipo_celda: TipoCelda;
  nombre: string;
  total: number;
  ocupadas: number;
  disponibles: number;
}
export interface ConsultaVehiculo {
  vehiculo: Vehiculo;
  cliente: Cliente | null;
  mensualidad: Mensualidad;
  esta_dentro: boolean;
  estancia: Movimiento | null;
  cupo: Cupo;
  puede_ingresar: boolean;
  motivo: string | null;
}
