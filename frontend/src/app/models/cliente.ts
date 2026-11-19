export interface ClienteBase {
  documento: string;
  nombre: string;
  telefono: string;
  correo: string;
  activo: boolean;
}
export interface ClienteCrear extends Omit<ClienteBase, 'activo'> {
  activo?: boolean;
}
export type ClienteActualizar = Partial<ClienteBase>;
export interface Cliente extends ClienteBase {
  id: number;
  // Solo lectura: la calcula el backend a partir de los pagos. Puede faltar en
  // respuestas que usan ClienteResumen (p. ej. el cliente embebido de vehículos).
  fecha_vencimiento?: string | null;
}
export interface ClientesPagina {
  items: Cliente[];
  total: number;
  offset: number;
  limit: number;
}
