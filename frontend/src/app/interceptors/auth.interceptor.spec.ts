import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { AuthService, SESSION_STORAGE_KEY } from '../services/auth.service';
import { authInterceptor } from './auth.interceptor';

const sesion = {
  token: 'token-1',
  expiraEn: Date.now() + 60_000,
  usuario: {
    id: 7,
    nombre: 'Ana Gómez',
    usuario: 'ana.gomez',
    rol: 'OPERADOR',
    activo: true,
  },
};

describe('authInterceptor', () => {
  let http: HttpTestingController;
  let client: HttpClient;
  let router: Router;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    client = TestBed.inject(HttpClient);
    router = TestBed.inject(Router);
  });

  afterEach(() => {
    http.verify();
    sessionStorage.clear();
  });

  it('adjunta el token a las peticiones del backend', () => {
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(sesion));
    TestBed.inject(AuthService);

    client.get('/celdas').subscribe();
    const req = http.expectOne('/celdas');
    expect(req.request.headers.get('Authorization')).toBe('Bearer token-1');
    req.flush({});
  });

  it('adjunta el token a clientes, puertas y reportes', () => {
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(sesion));
    TestBed.inject(AuthService);

    for (const url of ['/clientes', '/puertas', '/reportes/ocupacion']) {
      client.get(url).subscribe();
      const req = http.expectOne(url);
      expect(req.request.headers.get('Authorization')).toBe('Bearer token-1');
      req.flush({});
    }
  });

  it('no adjunta el token al login', () => {
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(sesion));
    TestBed.inject(AuthService);

    client.post('/api/v1/auth/login', { usuario: 'ana.gomez', contrasena: 'x' }).subscribe();
    const login = http.expectOne('/api/v1/auth/login');
    expect(login.request.headers.has('Authorization')).toBe(false);
    login.flush({ access_token: 'nuevo', token_type: 'bearer', expires_in: 60 });
  });

  it('no adjunta token cuando no hay sesión', () => {
    TestBed.inject(AuthService);

    client.get('/celdas').subscribe();
    const req = http.expectOne('/celdas');
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush({});
  });

  it('cierra la sesión y redirige al login ante un 401', () => {
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(sesion));
    const auth = TestBed.inject(AuthService);
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);

    client.get('/celdas').subscribe({ error: () => undefined });
    http.expectOne('/celdas').flush({}, { status: 401, statusText: 'Unauthorized' });

    expect(navigate).toHaveBeenCalledWith(['/login'], {
      queryParams: { returnUrl: '/', sesionExpirada: 1 },
    });
    expect(auth.token()).toBeNull();
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
  });
});
