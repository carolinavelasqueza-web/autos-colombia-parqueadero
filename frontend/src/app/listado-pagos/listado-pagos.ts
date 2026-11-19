import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EstadoPago, FiltrosPagos, Pago, PagosPagina } from '../models/pago';
import { ErrorApi } from '../models/vehiculo';
import { AuthService } from '../services/auth.service';
import { PagosService } from '../services/pagos.service';

const ESTADOS: readonly EstadoPago[] = ['VIGENTE', 'ANULADO'];

@Component({
  selector: 'app-listado-pagos',
  templateUrl: './listado-pagos.html',
  styleUrl: './listado-pagos.css',
})
export class ListadoPagos {
  readonly auth = inject(AuthService);
  private readonly api = inject(PagosService);
  private readonly destroyRef = inject(DestroyRef);

  readonly estados = ESTADOS;
  readonly limit = 20;

  readonly items = signal<Pago[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly loading = signal(false);
  readonly listError = signal('');
  readonly success = signal('');

  readonly documento = signal('');
  readonly estado = signal<EstadoPago | ''>('');
  readonly desde = signal('');
  readonly hasta = signal('');

  readonly pagoSeleccionado = signal<Pago | null>(null);
  readonly cargandoRecibo = signal(false);
  readonly reciboError = signal('');

  readonly confirmandoAnulacion = signal(false);
  readonly motivo = signal('');
  readonly anulando = signal(false);
  readonly anulacionError = signal('');

  readonly page = computed(() => Math.floor(this.offset() / this.limit) + 1);
  readonly pages = computed(() => Math.ceil(this.total() / this.limit) || 1);
  readonly busy = computed(() => this.loading() || this.anulando());

  constructor() {
    this.load();
  }

  load(offset = this.offset()): void {
    if (this.loading()) return;
    this.loading.set(true);
    this.listError.set('');
    this.api
      .listar(this.filtros(offset))
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (data: PagosPagina) => {
          this.loading.set(false);
          if (offset > 0 && offset >= data.total) {
            this.load(Math.max(0, Math.floor((data.total - 1) / this.limit) * this.limit));
            return;
          }
          this.items.set(data.items);
          this.total.set(data.total);
          this.offset.set(offset);
        },
        error: (error: HttpErrorResponse) => {
          this.loading.set(false);
          this.listError.set(this.mensajeError(error));
        },
      });
  }

  aplicarFiltros(): void {
    const desde = this.desde();
    const hasta = this.hasta();
    if (desde && hasta && desde > hasta) {
      this.listError.set('La fecha "desde" no puede ser posterior a la fecha "hasta".');
      return;
    }
    this.success.set('');
    this.offset.set(0);
    this.load(0);
  }

  limpiarFiltros(): void {
    this.documento.set('');
    this.estado.set('');
    this.desde.set('');
    this.hasta.set('');
    this.success.set('');
    this.offset.set(0);
    this.load(0);
  }

  onDocumentoInput(event: Event): void {
    this.documento.set((event.target as HTMLInputElement).value);
  }

  onEstadoChange(event: Event): void {
    this.estado.set((event.target as HTMLSelectElement).value as EstadoPago | '');
  }

  onDesdeChange(event: Event): void {
    this.desde.set((event.target as HTMLInputElement).value);
  }

  onHastaChange(event: Event): void {
    this.hasta.set((event.target as HTMLInputElement).value);
  }

  verRecibo(pago: Pago): void {
    if (this.cargandoRecibo()) return;
    this.cargandoRecibo.set(true);
    this.reciboError.set('');
    this.api
      .recibo(pago.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (recibo) => {
          this.cargandoRecibo.set(false);
          this.pagoSeleccionado.set(recibo);
          this.confirmandoAnulacion.set(false);
          this.anulacionError.set('');
          this.motivo.set('');
        },
        error: (error: HttpErrorResponse) => {
          this.cargandoRecibo.set(false);
          this.reciboError.set(this.mensajeError(error));
        },
      });
  }

  cerrarRecibo(): void {
    if (this.cargandoRecibo() || this.anulando()) return;
    this.pagoSeleccionado.set(null);
    this.confirmandoAnulacion.set(false);
    this.motivo.set('');
    this.anulacionError.set('');
    this.reciboError.set('');
  }

  imprimirRecibo(): void {
    window.print();
  }

  abrirAnulacion(): void {
    const pago = this.pagoSeleccionado();
    if (!pago || pago.estado !== 'VIGENTE' || !this.auth.esAdministrador() || this.anulando()) {
      return;
    }
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
    const pago = this.pagoSeleccionado();
    if (!pago || !this.auth.esAdministrador() || this.anulando()) return;

    const motivo = this.motivo().trim();
    if (!motivo) {
      this.anulacionError.set('El motivo de anulación es obligatorio.');
      return;
    }

    this.anulando.set(true);
    this.anulacionError.set('');
    this.api
      .anular(pago.id, { motivo })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (actualizado) => {
          this.anulando.set(false);
          this.confirmandoAnulacion.set(false);
          this.motivo.set('');
          this.pagoSeleccionado.set(actualizado);
          this.success.set(`Pago ${actualizado.numero_recibo} anulado correctamente.`);
          this.load();
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

  private filtros(offset: number): FiltrosPagos {
    const filtros: FiltrosPagos = { offset, limit: this.limit };
    const documento = this.documento().trim();
    if (documento) filtros.documento = documento;
    const estado = this.estado();
    if (estado) filtros.estado = estado;
    const desde = this.desde();
    if (desde) filtros.desde = desde;
    const hasta = this.hasta();
    if (hasta) filtros.hasta = hasta;
    return filtros;
  }

  private mensajeError(error: HttpErrorResponse): string {
    const cuerpo = error.error as ErrorApi | null;
    if (typeof cuerpo?.detail === 'string') return cuerpo.detail;
    if (error.status === 403) return 'No tienes permisos para realizar esta acción.';
    if (error.status === 404) return 'El pago ya no existe. Actualiza el listado.';
    if (error.status === 409) return 'La operación entra en conflicto con otros datos.';
    if (error.status === 422) return 'Revisa los filtros o los datos ingresados.';
    return 'No se pudo conectar con el servicio. Actualiza el listado e intenta de nuevo.';
  }
}
