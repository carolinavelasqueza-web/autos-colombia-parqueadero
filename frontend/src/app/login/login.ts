import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, ValidatorFn } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

const nonBlank: ValidatorFn = (control) =>
  typeof control.value === 'string' && control.value.trim() ? null : { required: true };

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule],
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly destroy = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);

  readonly form = this.fb.group({
    usuario: this.fb.nonNullable.control('', nonBlank),
    contrasena: this.fb.nonNullable.control('', nonBlank),
  });
  readonly loading = signal(false);
  readonly error = signal('');
  readonly sesionExpirada = signal(this.route.snapshot.queryParamMap.get('sesionExpirada') === '1');

  ingresar(): void {
    if (this.loading()) return;
    this.form.markAllAsTouched();
    if (this.form.invalid) return;

    const { usuario, contrasena } = this.form.getRawValue();
    this.loading.set(true);
    this.error.set('');
    this.auth
      .login({ usuario: usuario.trim(), contrasena })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: () => {
          this.loading.set(false);
          void this.router.navigateByUrl(this.urlDestino());
        },
        error: (error: HttpErrorResponse) => {
          this.loading.set(false);
          this.error.set(this.mensaje(error));
        },
      });
  }

  private urlDestino(): string {
    const solicitada = this.route.snapshot.queryParamMap.get('returnUrl');
    if (
      solicitada &&
      solicitada.startsWith('/') &&
      !solicitada.startsWith('//') &&
      !solicitada.startsWith('/login')
    ) {
      return solicitada;
    }
    return this.auth.rutaInicio();
  }

  private mensaje(error: HttpErrorResponse): string {
    if (error.status === 401) return 'Usuario o contraseña incorrectos.';
    if (error.status === 422) return 'Revisa el usuario y la contraseña.';
    if (error.status === 0) {
      return 'No se pudo conectar con el servicio. Verifica que el backend esté activo.';
    }
    if (error.status === 503 && typeof error.error?.detail === 'string') {
      return error.error.detail;
    }
    return 'No se pudo iniciar sesión. Inténtalo de nuevo.';
  }
}
