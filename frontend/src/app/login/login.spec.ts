import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter, Router } from '@angular/router';
import { Login } from './login';

describe('Login', () => {
  let http: HttpTestingController;
  let router: Router;
  let params: Record<string, string>;

  beforeEach(() => {
    sessionStorage.clear();
    params = {};
    TestBed.configureTestingModule({
      imports: [Login],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: {
            get snapshot() {
              return { queryParamMap: convertToParamMap(params) };
            },
          },
        },
      ],
    });
    http = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router);
  });

  afterEach(() => {
    http.verify();
    sessionStorage.clear();
  });

  it('no envía el formulario con campos vacíos', () => {
    const component = TestBed.createComponent(Login).componentInstance;
    component.form.setValue({ usuario: ' ', contrasena: '' });
    component.ingresar();

    http.expectNone('/api/v1/auth/login');
    expect(component.form.controls.usuario.touched).toBe(true);
    expect(component.form.controls.contrasena.touched).toBe(true);
  });

  it('inicia sesión y navega al inicio del administrador', () => {
    const navigate = vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    const component = TestBed.createComponent(Login).componentInstance;
    component.form.setValue({ usuario: ' admin ', contrasena: 'secreta' });
    component.ingresar();

    const login = http.expectOne('/api/v1/auth/login');
    expect(login.request.body).toEqual({ usuario: 'admin', contrasena: 'secreta' });
    login.flush({ access_token: 'token-1', token_type: 'bearer', expires_in: 60 });
    http.expectOne('/api/v1/auth/me').flush({
      id: 1,
      nombre: 'Admin',
      usuario: 'admin',
      rol: 'ADMINISTRADOR',
      activo: true,
    });

    expect(navigate).toHaveBeenCalledWith('/');
    expect(component.loading()).toBe(false);
  });

  it('respeta un returnUrl interno después del login', () => {
    params = { returnUrl: '/gestion/celdas' };
    const navigate = vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    const component = TestBed.createComponent(Login).componentInstance;
    component.form.setValue({ usuario: 'admin', contrasena: 'secreta' });
    component.ingresar();

    http
      .expectOne('/api/v1/auth/login')
      .flush({ access_token: 'token-1', token_type: 'bearer', expires_in: 60 });
    http.expectOne('/api/v1/auth/me').flush({
      id: 1,
      nombre: 'Admin',
      usuario: 'admin',
      rol: 'ADMINISTRADOR',
      activo: true,
    });

    expect(navigate).toHaveBeenCalledWith('/gestion/celdas');
  });

  it('ignora un returnUrl externo para evitar redirecciones abiertas', () => {
    params = { returnUrl: '//otro-sitio.example' };
    const navigate = vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    const component = TestBed.createComponent(Login).componentInstance;
    component.form.setValue({ usuario: 'admin', contrasena: 'secreta' });
    component.ingresar();

    http
      .expectOne('/api/v1/auth/login')
      .flush({ access_token: 'token-1', token_type: 'bearer', expires_in: 60 });
    http.expectOne('/api/v1/auth/me').flush({
      id: 1,
      nombre: 'Admin',
      usuario: 'admin',
      rol: 'ADMINISTRADOR',
      activo: true,
    });

    expect(navigate).toHaveBeenCalledWith('/');
  });

  it('muestra credenciales inválidas sin cargar el perfil', () => {
    const component = TestBed.createComponent(Login).componentInstance;
    component.form.setValue({ usuario: 'admin', contrasena: 'mala' });
    component.ingresar();

    http
      .expectOne('/api/v1/auth/login')
      .flush({ detail: 'Credenciales inválidas.' }, { status: 401, statusText: 'Unauthorized' });

    expect(component.error()).toBe('Usuario o contraseña incorrectos.');
    expect(component.loading()).toBe(false);
    http.expectNone('/api/v1/auth/me');
  });

  it('avisa cuando el servicio no responde', () => {
    const component = TestBed.createComponent(Login).componentInstance;
    component.form.setValue({ usuario: 'admin', contrasena: 'secreta' });
    component.ingresar();

    http.expectOne('/api/v1/auth/login').error(new ProgressEvent('error'));

    expect(component.error()).toContain('No se pudo conectar');
  });

  it('muestra el aviso de sesión expirada', () => {
    params = { sesionExpirada: '1' };
    const fixture = TestBed.createComponent(Login);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Tu sesión expiró');
  });
});
