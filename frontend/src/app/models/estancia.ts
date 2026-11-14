import { Celda } from './celda';
import { Cliente } from './cliente';
import { Puerta } from './puerta';
import { Vehiculo } from './vehiculo';

export interface EntradaCrear {
  placa: string;
  puerta_entrada_id: number;
}
export interface SalidaCrear {
  ficho_codigo: string;
  puerta_salida_id: number;
}
export interface Estancia {
  id: number;
  vehiculo_id: number;
  celda_id: number;
  entrada: string;
  salida: string | null;
  operador_entrada_id: number;
  operador_salida_id: number | null;
  ficho_codigo: string | null;
  ficho_usado_en: string | null;
  puerta_entrada_id: number | null;
  puerta_salida_id: number | null;
}
export type EstanciaAbierta = Estancia & {
  celda: Celda;
  puerta_entrada: Puerta | null;
};
export interface EstadoVehiculo {
  vehiculo: Vehiculo;
  esta_dentro: boolean;
  estancia: EstanciaAbierta | null;
}
export interface EstanciaActiva {
  id: number;
  vehiculo: Vehiculo;
  celda: Celda;
  entrada: string;
  ficho_codigo: string | null;
  permanencia_minutos: number;
}
export interface EstanciasActivasPagina {
  items: EstanciaActiva[];
  total: number;
  offset: number;
  limit: number;
}
export interface Ficho {
  id: number;
  ficho_codigo: string;
  entrada: string;
  salida: string | null;
  ficho_usado_en: string | null;
  vehiculo: Vehiculo;
  celda: Celda;
  puerta_entrada: Puerta | null;
  puerta_salida: Puerta | null;
  operador_entrada_id: number;
  operador_salida_id: number | null;
  cliente: Cliente | null;
}
export interface ReasignacionCrear {
  celda_nueva_id: number;
  motivo?: string | null;
}
export interface Reasignacion {
  id: number;
  estancia_id: number;
  celda_anterior: Celda;
  celda_nueva: Celda;
  operador_id: number;
  fecha: string;
  motivo: string | null;
  estancia: EstanciaAbierta;
}
