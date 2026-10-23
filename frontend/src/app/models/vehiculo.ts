export const TIPOS_VEHICULO = ['MOTO', 'AUTOMOVIL', 'CAMIONETA'] as const;
export type TipoVehiculo = (typeof TIPOS_VEHICULO)[number];
export interface VehiculoCrear {
  placa: string;
  color: string;
  modelo: number;
  marca: string;
  tipo: TipoVehiculo;
}
export type VehiculoActualizar = Partial<VehiculoCrear>;
export interface Vehiculo extends VehiculoCrear {
  id: number;
}
export interface VehiculosPagina {
  items: Vehiculo[];
  total: number;
  offset: number;
  limit: number;
}
export interface ErrorValidacion {
  loc: (string | number)[];
  msg: string;
  type: string;
}
export interface ErrorApi {
  detail?: string | ErrorValidacion[];
}

export const MENSAJE_PLACA =
  'Ingresa una placa colombiana: tres letras y tres números (ABC123) o, en motos, tres letras, dos números y una letra (ABC12D).';

/** Devuelve la placa en mayúsculas y sin separadores, o null si no es colombiana. */
export function normalizarPlaca(value: string): string | null {
  const placa = value.replace(/[\s-]/g, '').toUpperCase();
  return /^[A-Z]{3}\d{2}[0-9A-Z]$/.test(placa) ? placa : null;
}
