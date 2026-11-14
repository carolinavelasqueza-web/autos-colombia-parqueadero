import { HttpErrorResponse } from '@angular/common/http';
import {
  Component,
  DestroyRef,
  ElementRef,
  afterRenderEffect,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import Chart from 'chart.js/auto';
import type { ChartConfiguration } from 'chart.js';
import { ReporteOcupacion } from '../models/reporte';
import { ReportesService } from '../services/reportes.service';

const DIAS_POR_DEFECTO = 7;
const DIAS_MAXIMOS = 31;
const MILISEGUNDOS_DIA = 86_400_000;

function hoyEnBogota(): string {
  const partes = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Bogota',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date());
  const valor = (tipo: string) => partes.find((parte) => parte.type === tipo)?.value ?? '';
  return `${valor('year')}-${valor('month')}-${valor('day')}`;
}

function restarDias(iso: string, dias: number): string {
  const [anio, mes, dia] = iso.split('-').map(Number);
  const fecha = new Date(Date.UTC(anio, mes - 1, dia));
  fecha.setUTCDate(fecha.getUTCDate() - dias);
  return fecha.toISOString().slice(0, 10);
}

function diasInclusive(desde: string, hasta: string): number {
  const [anioA, mesA, diaA] = desde.split('-').map(Number);
  const [anioB, mesB, diaB] = hasta.split('-').map(Number);
  const inicio = Date.UTC(anioA, mesA - 1, diaA);
  const fin = Date.UTC(anioB, mesB - 1, diaB);
  return Math.floor((fin - inicio) / MILISEGUNDOS_DIA) + 1;
}

function fechaCorta(iso: string): string {
  const [anio, mes, dia] = iso.split('-').map(Number);
  return new Intl.DateTimeFormat('es-CO', {
    day: '2-digit',
    month: 'short',
    timeZone: 'UTC',
  }).format(new Date(Date.UTC(anio, mes - 1, dia)));
}

function fechaLarga(iso: string): string {
  const [anio, mes, dia] = iso.split('-').map(Number);
  return new Intl.DateTimeFormat('es-CO', {
    dateStyle: 'long',
    timeZone: 'UTC',
  }).format(new Date(Date.UTC(anio, mes - 1, dia)));
}

@Component({
  selector: 'app-reportes',
  imports: [ReactiveFormsModule],
  templateUrl: './reportes.html',
  styleUrl: './reportes.css',
})
export class Reportes {
  private readonly api = inject(ReportesService);
  private readonly destroy = inject(DestroyRef);
  private readonly canvasOcupacion = viewChild<ElementRef<HTMLCanvasElement>>('graficoOcupacion');
  private readonly canvasHistorico = viewChild<ElementRef<HTMLCanvasElement>>('graficoHistorico');
  private graficoOcupacion?: Chart;
  private graficoHistorico?: Chart;
  private version = 0;

  private readonly hoy = hoyEnBogota();
  readonly desde = new FormControl(restarDias(this.hoy, DIAS_POR_DEFECTO - 1), {
    nonNullable: true,
  });
  readonly hasta = new FormControl(this.hoy, { nonNullable: true });
  readonly reporte = signal<ReporteOcupacion | null>(null);
  readonly loading = signal(false);
  readonly error = signal('');
  readonly diasMaximos = DIAS_MAXIMOS;

  readonly fechaLarga = fechaLarga;

  private readonly formatoGenerado = new Intl.DateTimeFormat('es-CO', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'America/Bogota',
  });

  constructor() {
    afterRenderEffect(() => {
      const reporte = this.reporte();
      if (!reporte) {
        this.destruirGraficos();
        return;
      }
      this.dibujarOcupacion(reporte);
      this.dibujarHistorico(reporte);
    });
    this.destroy.onDestroy(() => this.destruirGraficos());
    this.consultar();
  }

  consultar(): void {
    const desde = this.desde.value;
    const hasta = this.hasta.value;
    if (!desde || !hasta) {
      this.error.set('Selecciona la fecha inicial y la final.');
      this.reporte.set(null);
      return;
    }
    if (desde > hasta) {
      this.error.set('La fecha inicial no puede ser posterior a la final.');
      this.reporte.set(null);
      return;
    }
    if (diasInclusive(desde, hasta) > DIAS_MAXIMOS) {
      this.error.set(`El rango del reporte no puede superar ${DIAS_MAXIMOS} días.`);
      this.reporte.set(null);
      return;
    }

    const version = ++this.version;
    this.loading.set(true);
    this.error.set('');
    this.reporte.set(null);
    this.api
      .ocupacion(desde, hasta)
      .pipe(takeUntilDestroyed(this.destroy))
      .subscribe({
        next: (reporte) => {
          if (version !== this.version) return;
          this.reporte.set(reporte);
          this.loading.set(false);
        },
        error: (error: HttpErrorResponse) => {
          if (version !== this.version) return;
          this.loading.set(false);
          this.reporte.set(null);
          this.error.set(this.mensaje(error));
        },
      });
  }

  private mensaje(error: HttpErrorResponse): string {
    if (error.status === 403) return 'No tienes permiso para consultar los reportes.';
    if (error.status === 422 && typeof error.error?.detail === 'string') {
      return error.error.detail;
    }
    if (error.status === 0) {
      return 'No se pudo conectar con el servicio. Verifica que el backend esté activo.';
    }
    return 'No se pudo generar el reporte. Inténtalo de nuevo.';
  }

  generado(valor: string): string {
    const fecha = new Date(valor);
    return Number.isNaN(fecha.getTime()) ? '—' : this.formatoGenerado.format(fecha);
  }

  permanencia(minutos: number): string {
    const redondeados = Math.round(minutos);
    const horas = Math.floor(redondeados / 60);
    const resto = redondeados % 60;
    return horas > 0 ? `${horas} h ${resto} min` : `${resto} min`;
  }

  private dibujarOcupacion(reporte: ReporteOcupacion): void {
    const canvas = this.canvasOcupacion()?.nativeElement;
    if (!canvas) return;
    this.graficoOcupacion?.destroy();
    this.graficoOcupacion = undefined;
    if (canvas.clientWidth === 0 && canvas.clientHeight === 0) return;

    const config: ChartConfiguration<'doughnut'> = {
      type: 'doughnut',
      data: {
        labels: reporte.por_tipo.map(
          (item) => `${item.familia} (${item.ocupadas}/${item.capacidad})`,
        ),
        datasets: [
          {
            label: 'Vehículos ocupados',
            data: reporte.por_tipo.map((item) => item.ocupadas),
            backgroundColor: ['#214c43', '#aa7b2e', '#5d7f8c'],
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom' },
          title: {
            display: true,
            text: 'Ocupación actual por familia',
          },
        },
      },
    };
    try {
      this.graficoOcupacion = new Chart(canvas, config);
    } catch {
      this.graficoOcupacion = undefined;
    }
  }

  private dibujarHistorico(reporte: ReporteOcupacion): void {
    const canvas = this.canvasHistorico()?.nativeElement;
    if (!canvas) return;
    this.graficoHistorico?.destroy();
    this.graficoHistorico = undefined;
    if (canvas.clientWidth === 0 && canvas.clientHeight === 0) return;

    const config: ChartConfiguration<'line'> = {
      type: 'line',
      data: {
        labels: reporte.historico.map((dia) => fechaCorta(dia.fecha)),
        datasets: [
          {
            label: 'Entradas',
            data: reporte.historico.map((dia) => dia.entradas),
            borderColor: '#214c43',
            backgroundColor: 'rgba(33, 76, 67, 0.12)',
            fill: true,
            tension: 0.3,
          },
          {
            label: 'Salidas',
            data: reporte.historico.map((dia) => dia.salidas),
            borderColor: '#aa7b2e',
            backgroundColor: 'rgba(170, 123, 46, 0.12)',
            fill: true,
            tension: 0.3,
          },
          {
            label: '% ocupación',
            data: reporte.historico.map((dia) => dia.porcentaje),
            borderColor: '#a03930',
            backgroundColor: '#a03930',
            yAxisID: 'y1',
            tension: 0.3,
            pointRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'bottom' },
          title: { display: true, text: 'Movimiento histórico del parqueadero' },
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { precision: 0 },
            title: { display: true, text: 'Movimientos' },
          },
          y1: {
            beginAtZero: true,
            max: 100,
            position: 'right',
            grid: { drawOnChartArea: false },
            title: { display: true, text: '% ocupación' },
          },
        },
      },
    };
    try {
      this.graficoHistorico = new Chart(canvas, config);
    } catch {
      this.graficoHistorico = undefined;
    }
  }

  private destruirGraficos(): void {
    this.graficoOcupacion?.destroy();
    this.graficoHistorico?.destroy();
    this.graficoOcupacion = undefined;
    this.graficoHistorico = undefined;
  }
}
