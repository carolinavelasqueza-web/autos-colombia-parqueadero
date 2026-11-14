import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { debounceTime, distinctUntilChanged } from 'rxjs';
import { EstanciaActiva } from '../models/estancia';
import { EstanciasService } from '../services/estancias.service';

@Component({
  selector: 'app-vehiculos-dentro',
  imports: [ReactiveFormsModule],
  templateUrl: './vehiculos-dentro.html',
  styleUrl: './vehiculos-dentro.css',
})
export class VehiculosDentro {
  private readonly api = inject(EstanciasService);
  private readonly destroy = inject(DestroyRef);
  private version = 0;

  readonly busqueda = new FormControl('', { nonNullable: true });
  readonly items = signal<EstanciaActiva[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly limit = 20;
  readonly page = computed(() => Math.floor(this.offset() / this.limit) + 1);
  readonly pages = computed(() => Math.max(1, Math.ceil(this.total() / this.limit)));

  private readonly formatoFecha = new Intl.DateTimeFormat('es-CO', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'America/Bogota',
  });

  constructor() {
    this.busqueda.valueChanges
      .pipe(debounceTime(300), distinctUntilChanged(), takeUntilDestroyed(this.destroy))
      .subscribe(() => this.load(0));
    this.load(0);
  }

  load(offset = 0): void {
    const version = ++this.version;
    this.loading.set(true);
    this.error.set('');
    this.api
      .activas(this.busqueda.value, offset, this.limit)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (pagina) => {
          if (version !== this.version) return;
          this.items.set(pagina.items);
          this.total.set(pagina.total);
          this.offset.set(pagina.offset);
          this.loading.set(false);
        },
        error: (error: HttpErrorResponse) => {
          if (version !== this.version) return;
          this.items.set([]);
          this.total.set(0);
          this.offset.set(0);
          this.loading.set(false);
          this.error.set(this.mensaje(error));
        },
      });
  }

  limpiar(): void {
    if (this.busqueda.value) {
      this.busqueda.setValue('');
    } else {
      this.load(0);
    }
  }

  fecha(valor: string): string {
    const fecha = new Date(valor);
    return Number.isNaN(fecha.getTime()) ? '—' : this.formatoFecha.format(fecha);
  }

  permanencia(minutos: number): string {
    const horas = Math.floor(minutos / 60);
    const resto = minutos % 60;
    return horas > 0 ? `${horas} h ${resto} min` : `${resto} min`;
  }

  private mensaje(error: HttpErrorResponse): string {
    if (error.status === 403) return 'No tienes permiso para consultar esta vista.';
    if (error.status === 0) {
      return 'No se pudo conectar con el servicio. Verifica que el backend esté activo.';
    }
    return 'No se pudieron cargar los vehículos que están dentro.';
  }
}
