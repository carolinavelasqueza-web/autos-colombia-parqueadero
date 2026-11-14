import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import {
  ActivatedRouteSnapshot,
  provideRouter,
  RouterStateSnapshot,
  UrlTree,
} from '@angular/router';
import { Rol } from '../models/auth';
import { SESSION_STORAGE_KEY } from '../services/auth.service';
import { authGuard, guestGuard, roleGuard } from './auth.guards';

function sesion(rol: Rol) {
  return {
    token: 'token-1',
    expiraEn: Date.now() + 60_000,
    usuario: {
      id: 7,
      nombre: 'Ana Gómez',
      usuario: 'ana.gomez',
      rol,
      activo: true,
    },
  };
}

function iniciarSesion(rol: Rol): void {
  sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(sesion(rol)));
}

const route = {} as ActivatedRouteSnapshot;
const state = { url: '/gestion/celdas' } as RouterStateSnapshot;

describe('auth.guards', () => {
  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideRouter([])],
    });
  });

  afterEach(() => sessionStorage.clear());

  it('authGuard envía al login con returnUrl cuando no hay sesión', () => {
    const result = TestBed.runInInjectionContext(() => authGuard(route, state)) as UrlTree;
    expect(result.toString()).toBe('/login?returnUrl=%2Fgestion%2Fceldas');
  });

  it('authGuard permite el acceso con una sesión válida', () => {
    iniciarSesion('OPERADOR');
    expect(TestBed.runInInjectionContext(() => authGuard(route, state))).toBe(true);
  });

  it('guestGuard redirige al inicio del administrador', () => {
    iniciarSesion('ADMINISTRADOR');
    const result = TestBed.runInInjectionContext(() => guestGuard(route, state)) as UrlTree;
    expect(result.toString()).toBe('/');
  });

  it('guestGuard redirige al control de acceso del operador', () => {
    iniciarSesion('OPERADOR');
    const result = TestBed.runInInjectionContext(() => guestGuard(route, state)) as UrlTree;
    expect(result.toString()).toBe('/control-acceso');
  });

  it('roleGuard permite ADMINISTRADOR en gestión', () => {
    iniciarSesion('ADMINISTRADOR');
    expect(TestBed.runInInjectionContext(() => roleGuard(['ADMINISTRADOR'])(route, state))).toBe(
      true,
    );
  });

  it('roleGuard bloquea OPERADOR en gestión y lo envía a su pantalla', () => {
    iniciarSesion('OPERADOR');
    const result = TestBed.runInInjectionContext(() =>
      roleGuard(['ADMINISTRADOR'])(route, state),
    ) as UrlTree;
    expect(result.toString()).toBe('/control-acceso');
  });

  it('roleGuard permite a ambos roles en Control de Acceso', () => {
    iniciarSesion('OPERADOR');
    expect(
      TestBed.runInInjectionContext(() => roleGuard(['ADMINISTRADOR', 'OPERADOR'])(route, state)),
    ).toBe(true);
  });

  it('roleGuard exige sesión antes de comprobar el rol', () => {
    const result = TestBed.runInInjectionContext(() =>
      roleGuard(['ADMINISTRADOR'])(route, state),
    ) as UrlTree;
    expect(result.toString()).toBe('/login?returnUrl=%2Fgestion%2Fceldas');
  });
});
