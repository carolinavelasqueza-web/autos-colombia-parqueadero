export interface OperadorBase {
  nombre: string;
  telefono: string;
  usuario: string;
}
export interface OperadorCrear extends OperadorBase {
  contrasena: string;
}
export interface OperadorActualizar extends Partial<OperadorBase> {
  contrasena?: string;
}
export interface Operador extends OperadorBase {
  id: number;
}
export interface OperadoresPagina {
  items: Operador[];
  total: number;
  offset: number;
  limit: number;
}
