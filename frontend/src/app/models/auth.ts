export const ROLES = ['ADMINISTRADOR', 'OPERADOR'] as const;

export type Rol = (typeof ROLES)[number];

export interface LoginRequest {
  usuario: string;
  contrasena: string;
}

export interface TokenRespuesta {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
}

export interface UsuarioSesion {
  id: number;
  nombre: string;
  usuario: string;
  rol: Rol;
  activo: boolean;
}

export interface Sesion {
  token: string;
  expiraEn: number;
  usuario: UsuarioSesion;
}
