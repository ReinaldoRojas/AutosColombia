/** RN-05: celdas 01–70 para carros y camionetas y 71–80 para motos. */
export const TIPOS_CELDA = ['CARRO_CAMIONETA', 'MOTO'] as const;
export type TipoCelda = (typeof TIPOS_CELDA)[number];
export const NOMBRE_CELDA: Record<string, string> = {
  CARRO_CAMIONETA: 'Carros y camionetas',
  MOTO: 'Motos',
};
export interface CeldaCrear {
  codigo: string;
  tipo: TipoCelda;
}
export type CeldaActualizar = Partial<CeldaCrear>;
export interface Celda extends CeldaCrear {
  id: number;
}
export interface CeldasPagina {
  items: Celda[];
  total: number;
  offset: number;
  limit: number;
}
