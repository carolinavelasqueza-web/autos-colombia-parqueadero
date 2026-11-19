import { Routes } from '@angular/router';
import { authGuard, guestGuard, roleGuard } from './guards/auth.guards';

export const routes: Routes = [
  {
    path: 'login',
    title: 'Iniciar sesión | Autos Colombia',
    canActivate: [guestGuard],
    loadComponent: () => import('./login/login').then((m) => m.Login),
  },
  {
    path: '',
    canActivate: [authGuard],
    loadComponent: () => import('./layout/layout').then((m) => m.Layout),
    children: [
      {
        path: '',
        pathMatch: 'full',
        canActivate: [roleGuard(['ADMINISTRADOR'])],
        title: 'Inicio | Autos Colombia',
        loadComponent: () => import('./home/home').then((m) => m.Home),
      },
      {
        path: 'control-acceso',
        title: 'Control de acceso | Autos Colombia',
        canActivate: [roleGuard(['ADMINISTRADOR', 'OPERADOR'])],
        loadComponent: () => import('./control-acceso/control-acceso').then((m) => m.ControlAcceso),
      },
      {
        path: 'vehiculos-dentro',
        title: 'Vehículos dentro | Autos Colombia',
        canActivate: [roleGuard(['ADMINISTRADOR', 'OPERADOR'])],
        loadComponent: () =>
          import('./vehiculos-dentro/vehiculos-dentro').then((m) => m.VehiculosDentro),
      },
      {
        path: 'gestion/tarifas',
        title: 'Tarifas | Autos Colombia',
        canActivate: [roleGuard(['ADMINISTRADOR'])],
        loadComponent: () =>
          import('./gestion-tarifas/gestion-tarifas').then((m) => m.GestionTarifas),
      },
      {
        path: 'gestion/pagos',
        title: 'Pagos | Autos Colombia',
        canActivate: [roleGuard(['ADMINISTRADOR', 'OPERADOR'])],
        loadComponent: () =>
          import('./listado-pagos/listado-pagos').then((m) => m.ListadoPagos),
      },
      {
        path: 'gestion/pagos/nuevo',
        title: 'Registrar pago | Autos Colombia',
        canActivate: [roleGuard(['ADMINISTRADOR', 'OPERADOR'])],
        loadComponent: () =>
          import('./registrar-pago/registrar-pago').then((m) => m.RegistrarPago),
      },
      {
        path: 'gestion/reportes',
        title: 'Reportes | Autos Colombia',
        canActivate: [roleGuard(['ADMINISTRADOR'])],
        loadComponent: () => import('./reportes/reportes').then((m) => m.Reportes),
      },
      {
        path: 'gestion/vehiculos',
        title: 'Vehículos | Autos Colombia',
        canActivate: [roleGuard(['ADMINISTRADOR'])],
        loadComponent: () => import('./vehiculos/vehiculos').then((m) => m.Vehiculos),
      },
      {
        path: 'gestion/clientes',
        title: 'Clientes | Autos Colombia',
        canActivate: [roleGuard(['ADMINISTRADOR', 'OPERADOR'])],
        loadComponent: () => import('./clientes/clientes').then((m) => m.Clientes),
      },
      {
        path: 'gestion/operadores',
        title: 'Operadores | Autos Colombia',
        canActivate: [roleGuard(['ADMINISTRADOR'])],
        loadComponent: () => import('./operadores/operadores').then((m) => m.Operadores),
      },
      {
        path: 'gestion/celdas',
        title: 'Celdas | Autos Colombia',
        canActivate: [roleGuard(['ADMINISTRADOR'])],
        loadComponent: () => import('./celdas/celdas').then((m) => m.Celdas),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
