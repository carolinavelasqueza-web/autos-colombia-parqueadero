import { HttpClient } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { Observable, catchError, of, switchMap, tap, throwError } from 'rxjs';
import { LoginRequest, ROLES, Rol, Sesion, TokenRespuesta, UsuarioSesion } from '../models/auth';
import { API_BASE_URL } from './api.service';

export const SESSION_STORAGE_KEY = 'autos-colombia.sesion';

function esSesion(value: unknown): value is Sesion {
  if (typeof value !== 'object' || value === null) return false;
  const sesion = value as Partial<Sesion>;
  const usuario = sesion.usuario;
  return (
    typeof sesion.token === 'string' &&
    sesion.token.length > 0 &&
    typeof sesion.expiraEn === 'number' &&
    typeof usuario === 'object' &&
    usuario !== null &&
    typeof usuario.id === 'number' &&
    typeof usuario.nombre === 'string' &&
    typeof usuario.usuario === 'string' &&
    typeof usuario.activo === 'boolean' &&
    ROLES.includes(usuario.rol as Rol)
  );
}

function leerSesion(): Sesion | null {
  try {
    const raw = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;
    const value: unknown = JSON.parse(raw);
    if (!esSesion(value) || value.expiraEn <= Date.now()) {
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
      return null;
    }
    return value;
  } catch {
    try {
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
    } catch {
      // Sin almacenamiento disponible: la sesión queda solo en memoria.
    }
    return null;
  }
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);
  private readonly state = signal<Sesion | null>(leerSesion());

  readonly usuario = computed<UsuarioSesion | null>(() => this.state()?.usuario ?? null);
  readonly rol = computed<Rol | null>(() => this.usuario()?.rol ?? null);
  readonly esAdministrador = computed(() => this.rol() === 'ADMINISTRADOR');

  login(data: LoginRequest): Observable<UsuarioSesion> {
    return this.http.post<TokenRespuesta>(`${this.base}/api/v1/auth/login`, data).pipe(
      switchMap((respuesta) => {
        if (!respuesta?.access_token || !Number.isFinite(respuesta.expires_in)) {
          return throwError(() => new Error('Respuesta de autenticación inválida.'));
        }
        return this.http
          .get<UsuarioSesion>(`${this.base}/api/v1/auth/me`, {
            headers: { Authorization: `Bearer ${respuesta.access_token}` },
          })
          .pipe(
            tap((usuario) => {
              this.guardar({
                token: respuesta.access_token,
                expiraEn: Date.now() + respuesta.expires_in * 1000,
                usuario,
              });
            }),
          );
      }),
    );
  }

  token(): string | null {
    const sesion = this.state();
    if (!sesion) return null;
    if (sesion.expiraEn <= Date.now()) {
      this.logout();
      return null;
    }
    return sesion.token;
  }

  estaAutenticado(): boolean {
    return this.token() !== null;
  }

  logout(): void {
    this.state.set(null);
    try {
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
    } catch {
      // La sesión en memoria ya quedó cerrada.
    }
  }

  /**
   * Cierra la sesión local de inmediato y avisa al backend para revocar el
   * token. Si el servidor no responde, la sesión local igual queda cerrada.
   */
  cerrarSesion(): void {
    const token = this.token();
    this.logout();
    if (!token) return;
    this.http
      .post<void>(`${this.base}/api/v1/auth/logout`, null, {
        headers: { Authorization: `Bearer ${token}` },
      })
      .pipe(catchError(() => of(undefined)))
      .subscribe();
  }

  rutaInicio(rol: Rol | null = this.rol()): string {
    return rol === 'ADMINISTRADOR' ? '/' : '/control-acceso';
  }

  private guardar(sesion: Sesion): void {
    this.state.set(sesion);
    try {
      sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(sesion));
    } catch {
      // La sesión sigue disponible en memoria mientras dure esta pestaña.
    }
  }
}
