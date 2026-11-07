import { Vehiculo } from './vehiculo';

export const TIPOS_DOCUMENTO = [
  { valor: 'CC', nombre: 'Cédula de ciudadanía' },
  { valor: 'CE', nombre: 'Cédula de extranjería' },
  { valor: 'TI', nombre: 'Tarjeta de identidad' },
  { valor: 'PA', nombre: 'Pasaporte' },
  { valor: 'NIT', nombre: 'NIT' },
] as const;
export type TipoDocumento = (typeof TIPOS_DOCUMENTO)[number]['valor'];

export interface ClienteCrear {
  tipo_documento: TipoDocumento;
  numero_documento: string;
  nombres: string;
  apellidos: string;
  telefono: string;
  correo: string | null;
}
export type ClienteActualizar = Partial<ClienteCrear>;
export interface Cliente extends ClienteCrear {
  id: number;
  fecha_registro: string;
}
export interface ClienteDetalle extends Cliente {
  vehiculos: Vehiculo[];
}
export interface ClientesPagina {
  items: Cliente[];
  total: number;
  offset: number;
  limit: number;
}
