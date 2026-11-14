import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, input, output, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { CeldaDisponible } from '../models/celda';
import { EstanciaAbierta, Reasignacion } from '../models/estancia';
import { EstanciasService } from '../services/estancias.service';

@Component({
  selector: 'app-reasignacion-modal',
  imports: [ReactiveFormsModule],
  templateUrl: './reasignacion-modal.html',
  styleUrl: './reasignacion-modal.css',
})
export class ReasignacionModal {
  private readonly api = inject(EstanciasService);
  private readonly fb = inject(FormBuilder);
  private readonly destroy = inject(DestroyRef);

  readonly estancia = input.required<EstanciaAbierta>();
  readonly placa = input<string>('');
  readonly celdas = input<CeldaDisponible[]>([]);
  readonly reasignada = output<Reasignacion>();
  readonly cerrar = output<void>();

  readonly saving = signal(false);
  readonly error = signal('');
  readonly form = this.fb.group({
    celda_nueva_id: this.fb.control<number | null>(null, Validators.required),
    motivo: this.fb.nonNullable.control('', Validators.maxLength(500)),
  });

  guardar(): void {
    if (this.saving()) return;
    this.form.markAllAsTouched();
    const celda = this.form.controls.celda_nueva_id.value;
    if (celda === null || this.form.invalid) return;

    const motivo = this.form.controls.motivo.value.trim() || null;
    this.saving.set(true);
    this.error.set('');
    this.api
      .reasignar(this.estancia().id, { celda_nueva_id: celda, motivo })
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (result) => {
          this.saving.set(false);
          this.reasignada.emit(result);
        },
        error: (error) => {
          this.saving.set(false);
          this.error.set(this.mensaje(error));
        },
      });
  }

  cerrarModal(): void {
    if (!this.saving()) this.cerrar.emit();
  }

  private mensaje(error: HttpErrorResponse): string {
    if ([400, 404, 409].includes(error.status) && typeof error.error?.detail === 'string') {
      return error.error.detail;
    }
    if (error.status === 422) {
      return 'Datos inválidos. Selecciona una celda libre y verifica el motivo.';
    }
    return 'No se pudo reasignar la celda. Actualiza la disponibilidad e inténtalo de nuevo.';
  }
}
