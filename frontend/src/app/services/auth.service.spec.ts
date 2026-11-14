import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { UsuarioSesion } from '../models/auth';
import { AuthService, SESSION_STORAGE_KEY } from './auth.service';

const perfil: UsuarioSesion = {
  id: 7,
  nombre: 'Ana Gómez',
  usuario: 'ana.gomez',
  rol: 'OPERADOR',
  activo: true,
};

describe('AuthService', () => {
  let http: HttpTestingController;
  let auth: AuthService;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
  });

  afterEach(() => {
    http.verify();
    sessionStorage.clear();
  });

  it('guarda token y perfil después de autenticarse', () => {
    let resultado: UsuarioSesion | undefined;
    auth.login({ usuario: 'ana.gomez', contrasena: 'secreta' }).subscribe((value) => {
      resultado = value;
    });

    const login = http.expectOne('/api/v1/auth/login');
    expect(login.request.method).toBe('POST');
    expect(login.request.body).toEqual({ usuario: 'ana.gomez', contrasena: 'secreta' });
    login.flush({ access_token: 'token-1', token_type: 'bearer', expires_in: 120 });

    const me = http.expectOne('/api/v1/auth/me');
    expect(me.request.headers.get('Authorization')).toBe('Bearer token-1');
    me.flush(perfil);

    expect(resultado).toEqual(perfil);
    expect(auth.usuario()).toEqual(perfil);
    expect(auth.rol()).toBe('OPERADOR');
    expect(auth.esAdministrador()).toBe(false);
    expect(auth.token()).toBe('token-1');
    expect(JSON.parse(sessionStorage.getItem(SESSION_STORAGE_KEY) ?? '{}').token).toBe('token-1');
  });

  it('no deja sesión cuando el perfil no se puede cargar', () => {
    let fallo = false;
    auth.login({ usuario: 'ana.gomez', contrasena: 'secreta' }).subscribe({
      error: () => {
        fallo = true;
      },
    });

    http
      .expectOne('/api/v1/auth/login')
      .flush({ access_token: 'token-1', token_type: 'bearer', expires_in: 120 });
    http
      .expectOne('/api/v1/auth/me')
      .flush({ detail: 'Sesión no válida.' }, { status: 401, statusText: 'Unauthorized' });

    expect(fallo).toBe(true);
    expect(auth.token()).toBeNull();
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
  });

  it('cierra la sesión y elimina el almacenamiento', () => {
    sessionStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({ token: 'token-1', expiraEn: Date.now() + 60_000, usuario: perfil }),
    );
    const nuevo = TestBed.runInInjectionContext(() => new AuthService());
    expect(nuevo.token()).toBe('token-1');

    nuevo.logout();

    expect(nuevo.token()).toBeNull();
    expect(nuevo.usuario()).toBeNull();
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
  });

  it('revoca la sesión en el servidor al cerrar sesión', () => {
    sessionStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({ token: 'token-1', expiraEn: Date.now() + 60_000, usuario: perfil }),
    );
    const nuevo = TestBed.runInInjectionContext(() => new AuthService());

    nuevo.cerrarSesion();

    expect(nuevo.token()).toBeNull();
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
    const logout = http.expectOne('/api/v1/auth/logout');
    expect(logout.request.method).toBe('POST');
    expect(logout.request.headers.get('Authorization')).toBe('Bearer token-1');
    logout.flush(null, { status: 204, statusText: 'No Content' });
  });

  it('cierra la sesión local aunque falle la revocación del servidor', () => {
    sessionStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({ token: 'token-1', expiraEn: Date.now() + 60_000, usuario: perfil }),
    );
    const nuevo = TestBed.runInInjectionContext(() => new AuthService());

    nuevo.cerrarSesion();
    http
      .expectOne('/api/v1/auth/logout')
      .flush({ detail: 'Error' }, { status: 500, statusText: 'Server Error' });

    expect(nuevo.token()).toBeNull();
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
  });

  it('no llama al servidor si no hay una sesión activa', () => {
    auth.cerrarSesion();
    http.expectNone('/api/v1/auth/logout');
  });

  it('descarta una sesión vencida o corrupta al iniciar', () => {
    sessionStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({ token: 'viejo', expiraEn: Date.now() - 1, usuario: perfil }),
    );
    const vencida = TestBed.runInInjectionContext(() => new AuthService());
    expect(vencida.token()).toBeNull();
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();

    sessionStorage.setItem(SESSION_STORAGE_KEY, '{no-json');
    const corrupta = TestBed.runInInjectionContext(() => new AuthService());
    expect(corrupta.token()).toBeNull();
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
  });

  it('calcula la ruta de inicio según el rol', () => {
    expect(auth.rutaInicio('ADMINISTRADOR')).toBe('/');
    expect(auth.rutaInicio('OPERADOR')).toBe('/control-acceso');
  });
});
