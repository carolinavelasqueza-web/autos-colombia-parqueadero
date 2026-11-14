import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { Rol } from '../models/auth';
import { SESSION_STORAGE_KEY } from '../services/auth.service';
import { Layout } from './layout';

function iniciarSesion(rol: Rol): void {
  sessionStorage.setItem(
    SESSION_STORAGE_KEY,
    JSON.stringify({
      token: 'token-1',
      expiraEn: Date.now() + 60_000,
      usuario: {
        id: 7,
        nombre: 'Ana Gómez',
        usuario: 'ana.gomez',
        rol,
        activo: true,
      },
    }),
  );
}

describe('Layout', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      imports: [Layout],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    sessionStorage.clear();
  });

  it('muestra todo el menú al administrador y su nombre completo', () => {
    iniciarSesion('ADMINISTRADOR');
    const fixture = TestBed.createComponent(Layout);
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    const links = [...element.querySelectorAll('nav a')].map((link) => link.getAttribute('href'));

    expect(links).toEqual([
      '/',
      '/control-acceso',
      '/vehiculos-dentro',
      '/gestion/vehiculos',
      '/gestion/clientes',
      '/gestion/operadores',
      '/gestion/celdas',
      '/gestion/reportes',
    ]);
    expect(element.querySelector('.session-name')?.textContent).toContain('Ana Gómez');
    expect(element.querySelector('.session-detail')?.textContent).toContain('ana.gomez');
    expect(element.querySelector('.role-badge')?.textContent).toContain('Administrador');
  });

  it('limita al operador al control de acceso', () => {
    iniciarSesion('OPERADOR');
    const fixture = TestBed.createComponent(Layout);
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    const links = [...element.querySelectorAll('nav a')].map((link) => link.getAttribute('href'));

    expect(links).toEqual(['/control-acceso', '/vehiculos-dentro']);
    expect(element.querySelector('.role-badge')?.textContent).toContain('Operador');
    expect(element.querySelector('a[href="/gestion/operadores"]')).toBeNull();
    expect(element.querySelector('a[href="/gestion/celdas"]')).toBeNull();
    expect(element.querySelector('a[href="/gestion/reportes"]')).toBeNull();
  });

  it('cierra la sesión y vuelve al login', () => {
    iniciarSesion('ADMINISTRADOR');
    const router = TestBed.inject(Router);
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    const fixture = TestBed.createComponent(Layout);
    fixture.detectChanges();

    (fixture.nativeElement as HTMLElement)
      .querySelector<HTMLButtonElement>('button.logout')
      ?.click();

    const logout = http.expectOne('/api/v1/auth/logout');
    expect(logout.request.method).toBe('POST');
    expect(logout.request.headers.get('Authorization')).toBe('Bearer token-1');
    logout.flush(null, { status: 204, statusText: 'No Content' });

    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
    expect(navigate).toHaveBeenCalledWith(['/login']);
  });
});
