import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

const PREFIJOS_API = [
  '/api',
  '/estancias',
  '/operadores',
  '/celdas',
  '/clientes',
  '/puertas',
  '/reportes',
  '/vehiculos',
  '/pagos',
  '/tarifas',
  '/health',
];
const LOGIN = '/api/v1/auth/login';

function esRutaApi(url: string): boolean {
  return PREFIJOS_API.some(
    (prefijo) => url === prefijo || url.startsWith(`${prefijo}/`) || url.startsWith(`${prefijo}?`),
  );
}

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const esLogin = req.url.includes(LOGIN);
  const yaTieneToken = req.headers.has('Authorization');
  const token = esLogin || yaTieneToken ? null : auth.token();
  const peticion =
    token && esRutaApi(req.url)
      ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
      : req;

  return next(peticion).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401 && !esLogin) {
        const actual = router.url;
        auth.logout();
        if (!actual.startsWith('/login')) {
          void router.navigate(['/login'], {
            queryParams: { returnUrl: actual, sesionExpirada: 1 },
          });
        }
      }
      return throwError(() => error);
    }),
  );
};
