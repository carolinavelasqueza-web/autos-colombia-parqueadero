import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, ValidatorFn } from '@angular/forms';
import { TIPOS_TARIFA, Tarifa, TipoTarifa } from '../models/tarifa';
import { TarifasService } from '../services/tarifas.service';

const enteroPositivo: ValidatorFn = (control) => {
  const valor = String(control.value ?? '').trim();
  if (!valor) return { required: true };
  if (!/^\d+$/.test(valor)) return { entero: true };
  return Number(valor) > 0 ? null : { positivo: true };
};

@Component({
  selector: 'app-gestion-tarifas',
  imports: [ReactiveFormsModule],
  templateUrl: './gestion-tarifas.html',
  styleUrl: './gestion-tarifas.css',
})
export class GestionTarifas {
  private readonly api = inject(TarifasService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly fb = inject(FormBuilder);

  readonly tipos = TIPOS_TARIFA;
  readonly items = signal<Tarifa[]>([]);
  readonly filas = computed(() =>
    TIPOS_TARIFA.map((tipo) => ({
      tipo,
      tarifa: this.items().find((item) => item.tipo === tipo) ?? null,
    })),
  );
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly busy = computed(() => this.loading() || this.saving());
  readonly editing = signal<TipoTarifa | null>(null);
  readonly listError = signal('');
  readonly actionError = signal('');
  readonly success = signal('');

  readonly form = this.fb.nonNullable.group({
    valor: this.fb.nonNullable.control('', enteroPositivo),
  });

  constructor() {
    this.cargar();
  }

  cargar(): void {
    if (this.busy()) return;
    this.loading.set(true);
    this.listError.set('');
    this.api
      .listar()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (tarifas) => {
          this.loading.set(false);
          this.items.set(tarifas);
        },
        error: (error: HttpErrorResponse) => {
          this.loading.set(false);
          this.listError.set(this.mensajeError(error));
        },
      });
  }

  editar(tipo: TipoTarifa, tarifa: Tarifa | null): void {
    if (this.busy()) return;
    this.form.reset({ valor: tarifa ? this.valorEntero(tarifa.valor) : '' });
    this.editing.set(tipo);
    this.actionError.set('');
    this.success.set('');
  }

  cancelar(): void {
    if (this.saving()) return;
    this.editing.set(null);
    this.actionError.set('');
  }

  guardar(): void {
    const tipo = this.editing();
    if (!tipo || this.busy()) return;

    this.form.markAllAsTouched();
    if (this.form.invalid) {
      this.actionError.set('Ingresa un valor entero mayor que cero.');
      return;
    }

    const valor = this.form.controls.valor.value.trim();
    this.saving.set(true);
    this.actionError.set('');
    this.success.set('');
    this.api
      .actualizar(tipo, { valor })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (tarifa) => {
          this.saving.set(false);
          this.editing.set(null);
          this.items.update((items) => [
            ...items.filter((item) => item.tipo !== tarifa.tipo),
            tarifa,
          ]);
          this.success.set(`Tarifa de ${tarifa.tipo} actualizada correctamente.`);
        },
        error: (error: HttpErrorResponse) => {
          this.saving.set(false);
          this.actionError.set(this.mensajeError(error));
        },
      });
  }

  onValorInput(): void {
    const control = this.form.controls.valor;
    const limpio = control.value.replace(/\D/g, '');
    if (control.value !== limpio) control.setValue(limpio, { emitEvent: false });
  }

  campoError(): string {
    const control = this.form.controls.valor;
    if (!control.touched || !control.errors) return '';
    if (control.errors['required']) return 'El valor es obligatorio.';
    if (control.errors['entero']) return 'Ingresa solo dígitos, sin puntos ni decimales.';
    if (control.errors['positivo']) return 'El valor debe ser mayor que cero.';
    return 'Revisa el valor ingresado.';
  }

  valorEntero(valor: string): string {
    return String(Number.parseInt(valor, 10));
  }

  formatearValor(valor: string): string {
    const entero = Number.parseInt(valor, 10);
    if (Number.isNaN(entero)) return valor;
    return new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 }).format(entero);
  }

  private mensajeError(error: HttpErrorResponse): string {
    if (error.status === 403)
      return 'No tienes permisos para modificar las tarifas.';
    if (error.status === 422)
      return 'El valor no cumple las validaciones del servicio.';
    return 'No se pudo conectar con el servicio. Comprueba la conexión e intenta de nuevo.';
  }
}
