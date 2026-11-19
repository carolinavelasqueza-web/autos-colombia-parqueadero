import { TipoTarifa } from './tarifa';

export const METODOS_PAGO = ['EFECTIVO', 'TRANSFERENCIA', 'TARJETA'] as const;
export type MetodoPago = (typeof METODOS_PAGO)[number];

export const ESTADOS_PAGO = ['VIGENTE', 'ANULADO'] as const;
export type EstadoPago = (typeof ESTADOS_PAGO)[number];

export const ESTADOS_MENSUALIDAD = ['SIN_PAGO', 'VENCIDA', 'POR_VENCER', 'AL_DIA'] as const;
export type MensualidadEstado = (typeof ESTADOS_MENSUALIDAD)[number];

/** Todos los montos viajan como texto con dos decimales para evitar redondeos. */
export type Monto = string;

export interface PagoCrear {
  documento: string;
  meses: number;
  metodo: MetodoPago;
  referencia?: string | null;
  // Vehículos a liquidar. Si se omite, el backend cobra todos los del cliente.
  vehiculo_ids?: number[];
}

export interface PagoAnular {
  motivo: string;
}

export interface ClientePago {
  id: number;
  documento: string;
  nombre: string;
  telefono: string;
  correo: string;
  activo: boolean;
  fecha_vencimiento: string | null;
}

export interface PagoDetalle {
  id: number;
  vehiculo_id: number;
  placa: string;
  tipo: TipoTarifa;
  tarifa_aplicada: Monto;
  subtotal: Monto;
}

export interface Pago {
  id: number;
  numero_recibo: string;
  cliente: ClientePago;
  detalles: PagoDetalle[];
  meses: number;
  metodo: MetodoPago;
  referencia: string | null;
  monto: Monto;
  estado: EstadoPago;
  periodo_desde: string;
  periodo_hasta: string;
  vencimiento_anterior: string | null;
  reactivo_cliente: boolean;
  operador_id: number;
  fecha: string;
  motivo: string | null;
  anulado_por: number | null;
  anulado_en: string | null;
}

export interface PagosPagina {
  items: Pago[];
  total: number;
  offset: number;
  limit: number;
}

export interface FiltrosPagos {
  documento?: string;
  estado?: EstadoPago;
  desde?: string;
  hasta?: string;
  offset?: number;
  limit?: number;
}

export interface Mensualidad {
  cliente: ClientePago;
  estado: MensualidadEstado;
}

export interface ClientesMensualidadPagina {
  items: Mensualidad[];
  total: number;
  offset: number;
  limit: number;
}

export interface RecaudoPorMetodo {
  metodo: MetodoPago;
  pagos: number;
  total: Monto;
}

export interface ReporteRecaudo {
  desde: string;
  hasta: string;
  pagos: number;
  total: Monto;
  por_metodo: RecaudoPorMetodo[];
}
