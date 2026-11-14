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
}
export interface ClientesPagina {
  items: Cliente[];
  total: number;
  offset: number;
  limit: number;
}
