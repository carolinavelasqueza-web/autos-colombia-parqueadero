import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ReporteOcupacion } from '../models/reporte';
import { Reportes } from './reportes';

function reporte(): ReporteOcupacion {
  return {
    generado_en: '2026-01-03T18:00:00Z',
    desde: '2026-01-01',
    hasta: '2026-01-03',
    capacidad_total: 3,
    ocupadas: 1,
    disponibles: 2,
    porcentaje: 33.3,
    entradas: 2,
    salidas: 1,
    permanencia_promedio_minutos: 1440,
    por_tipo: [
      { familia: 'AUTOS', capacidad: 2, ocupadas: 1, disponibles: 1, porcentaje: 50 },
      { familia: 'MOTOS', capacidad: 1, ocupadas: 0, disponibles: 1, porcentaje: 0 },
    ],
    historico: [
      { fecha: '2026-01-01', entradas: 1, salidas: 0, ocupadas: 1, porcentaje: 33.3 },
      { fecha: '2026-01-02', entradas: 1, salidas: 1, ocupadas: 1, porcentaje: 33.3 },
      { fecha: '2026-01-03', entradas: 0, salidas: 0, ocupadas: 1, porcentaje: 33.3 },
    ],
  };
}

function diasEntre(desde: string, hasta: string): number {
  const [anioA, mesA, diaA] = desde.split('-').map(Number);
  const [anioB, mesB, diaB] = hasta.split('-').map(Number);
  return (
    Math.floor((Date.UTC(anioB, mesB - 1, diaB) - Date.UTC(anioA, mesA - 1, diaA)) / 86_400_000) + 1
  );
}

describe('Reportes', () => {
  let fixture: ComponentFixture<Reportes>;
  let http: HttpTestingController;
  let componente: Reportes;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Reportes],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Reportes);
    componente = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function root(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function solicitud() {
    return http.expectOne((req) => req.url === '/reportes/ocupacion');
  }

  function sinSolicitudes(): void {
    http.expectNone((req) => req.url === '/reportes/ocupacion');
  }

  it('consulta los últimos siete días y muestra los indicadores', () => {
    const req = solicitud();
    const desde = req.request.params.get('desde') ?? '';
    const hasta = req.request.params.get('hasta') ?? '';
    expect(diasEntre(desde, hasta)).toBe(7);

    req.flush(reporte());
    fixture.detectChanges();

    const kpis = [...root().querySelectorAll('.kpi')].map((kpi) => kpi.textContent ?? '');
    expect(kpis.some((texto) => texto.includes('Capacidad total') && texto.includes('3'))).toBe(
      true,
    );
    expect(kpis.some((texto) => texto.includes('Ocupadas') && texto.includes('33.3%'))).toBe(true);
    expect(kpis.some((texto) => texto.includes('Permanencia promedio'))).toBe(true);
    expect(root().textContent).toContain('24 h 0 min');
  });

  it('muestra el detalle por familia y la fecha de generación', () => {
    solicitud().flush(reporte());
    fixture.detectChanges();

    const filas = [...root().querySelectorAll('tbody tr')].map((fila) => fila.textContent ?? '');
    expect(filas).toHaveLength(2);
    expect(filas[0]).toContain('AUTOS');
    expect(filas[0]).toContain('50%');
    expect(filas[1]).toContain('MOTOS');
    expect(root().textContent).toContain('Reporte generado el');
  });

  it('envía el rango elegido al generar el reporte', () => {
    solicitud().flush(reporte());
    componente.desde.setValue('2026-02-01');
    componente.hasta.setValue('2026-02-05');

    componente.consultar();

    const req = solicitud();
    expect(req.request.params.get('desde')).toBe('2026-02-01');
    expect(req.request.params.get('hasta')).toBe('2026-02-05');
    req.flush(reporte());
  });

  it('rechaza un rango invertido sin consultar la API', () => {
    solicitud().flush(reporte());
    componente.desde.setValue('2026-02-10');
    componente.hasta.setValue('2026-02-01');

    componente.consultar();
    fixture.detectChanges();

    expect(root().querySelector('[role="alert"]')?.textContent).toContain('no puede ser posterior');
    sinSolicitudes();
  });

  it('rechaza un rango mayor al máximo permitido', () => {
    solicitud().flush(reporte());
    componente.desde.setValue('2026-01-01');
    componente.hasta.setValue('2026-02-15');

    componente.consultar();
    fixture.detectChanges();

    expect(root().querySelector('[role="alert"]')?.textContent).toContain('no puede superar');
    sinSolicitudes();
  });

  it('muestra el mensaje del backend ante un rango inválido', () => {
    solicitud().flush(
      { detail: 'El rango del reporte no puede superar 31 días.' },
      { status: 422, statusText: 'Unprocessable Content' },
    );
    fixture.detectChanges();

    expect(root().querySelector('[role="alert"]')?.textContent).toContain(
      'no puede superar 31 días',
    );
  });

  it('muestra un mensaje de error cuando falla la consulta', () => {
    solicitud().flush({ detail: 'Error' }, { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();

    expect(root().querySelector('[role="alert"]')?.textContent).toContain(
      'No se pudo generar el reporte',
    );
  });
});
