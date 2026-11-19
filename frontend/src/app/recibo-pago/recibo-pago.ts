import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, input, output, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Pago } from '../models/pago';
import { ErrorApi } from '../models/vehiculo';
import { AuthService } from '../services/auth.service';
import { PagosService } from '../services/pagos.service';

@Component({
  selector: 'app-recibo-pago',
  templateUrl: './recibo-pago.html',
  styleUrl: './recibo-pago.css',
})
export class ReciboPago {
  readonly auth = inject(AuthService);
  private readonly api = inject(PagosService);
  private readonly destroyRef = inject(DestroyRef);

  readonly pago = input.required<Pago>();
  readonly mensaje = input('');
  readonly cerrar = output<void>();
  readonly anulado = output<Pago>();

  readonly confirmandoAnulacion = signal(false);
  readonly motivo = signal('');
  readonly anulando = signal(false);
  readonly anulacionError = signal('');

  solicitarCierre(): void {
    if (!this.anulando()) this.cerrar.emit();
  }

  abrirAnulacion(): void {
    if (!this.auth.esAdministrador() || this.pago().estado !== 'VIGENTE' || this.anulando()) return;
    this.confirmandoAnulacion.set(true);
    this.motivo.set('');
    this.anulacionError.set('');
  }

  cancelarAnulacion(): void {
    if (this.anulando()) return;
    this.confirmandoAnulacion.set(false);
    this.motivo.set('');
    this.anulacionError.set('');
  }

  onMotivoInput(event: Event): void {
    this.motivo.set((event.target as HTMLTextAreaElement).value);
  }

  anular(): void {
    if (!this.auth.esAdministrador() || this.anulando()) return;

    const motivo = this.motivo().trim();
    if (!motivo) {
      this.anulacionError.set('El motivo de anulación es obligatorio.');
      return;
    }

    this.anulando.set(true);
    this.anulacionError.set('');
    this.api
      .anular(this.pago().id, { motivo })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (actualizado) => {
          this.anulando.set(false);
          this.confirmandoAnulacion.set(false);
          this.motivo.set('');
          this.anulado.emit(actualizado);
        },
        error: (error: HttpErrorResponse) => {
          this.anulando.set(false);
          this.anulacionError.set(this.mensajeError(error));
        },
      });
  }

  fecha(valor: string): string {
    return new Intl.DateTimeFormat('es-CO', {
      timeZone: 'America/Bogota',
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(valor));
  }

  formatearMonto(valor: string): string {
    const numero = Number(valor);
    if (Number.isNaN(numero)) return valor;
    return `$ ${new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 }).format(numero)}`;
  }

  private mensajeError(error: HttpErrorResponse): string {
    const cuerpo = error.error as ErrorApi | null;
    if (typeof cuerpo?.detail === 'string') return cuerpo.detail;
    if (error.status === 403) return 'No tienes permisos para anular este pago.';
    if (error.status === 404) return 'El pago ya no existe. Actualiza el listado.';
    if (error.status === 409) return 'Solo se puede anular el último pago vigente del cliente.';
    if (error.status === 422) return 'Revisa el motivo de la anulación.';
    return 'No se pudo anular el pago. Intenta de nuevo.';
  }
}
