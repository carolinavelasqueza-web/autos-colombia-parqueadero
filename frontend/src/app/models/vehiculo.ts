import { Cliente } from './cliente';

export const TIPOS_VEHICULO = ['MOTO', 'AUTOMOVIL', 'CAMIONETA'] as const;
export type TipoVehiculo = (typeof TIPOS_VEHICULO)[number];
export interface VehiculoBase {
  placa: string;
  color: string;
  modelo: number;
  marca: string;
  tipo: TipoVehiculo;
}
export interface VehiculoCrear extends VehiculoBase {
  cliente_id: number;
}
export type VehiculoActualizar = Partial<VehiculoCrear>;
export interface Vehiculo extends VehiculoBase {
  id: number;
  cliente_id: number | null;
  cliente: Cliente | null;
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
