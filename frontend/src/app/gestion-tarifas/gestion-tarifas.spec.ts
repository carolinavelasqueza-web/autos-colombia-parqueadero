import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Tarifa } from '../models/tarifa';
import { GestionTarifas } from './gestion-tarifas';

describe('Gestión de tarifas', () => {
  let fixture: ComponentFixture<GestionTarifas>;
  let http: HttpTestingController;
  const tarifas: Tarifa[] = [
    {
      id: 2,
      tipo: 'AUTOMOVIL',
      valor: '150000.00',
      vigente_desde: '2026-11-01T05:00:00Z',
      vigente_hasta: null,
    },
    {
      id: 3,
      tipo: 'CAMIONETA',
      valor: '180000.00',
      vigente_desde: '2026-11-01T05:00:00Z',
      vigente_hasta: null,
    },
    {
      id: 1,
      tipo: 'MOTO',
      valor: '80000.00',
      vigente_desde: '2026-11-01T05:00:00Z',
      vigente_hasta: null,
    },
  ];

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [GestionTarifas],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(GestionTarifas);
    fixture.detectChanges();
    http.expectOne('/tarifas').flush(tarifas);
    fixture.detectChanges();
  });
  afterEach(() => http.verify());

  it('renderiza los tres tipos en orden con su tarifa vigente', () => {
    const root = fixture.nativeElement as HTMLElement;
    const rows = [...root.querySelectorAll<HTMLTableRowElement>('tbody tr')];

    expect(rows).toHaveLength(3);
    expect(rows.map((row) => row.querySelector('th')?.textContent?.trim())).toEqual([
      'MOTO',
      'AUTOMOVIL',
      'CAMIONETA',
    ]);
    expect(rows[0].textContent).toContain('80.000');
    expect(rows[1].textContent).toContain('150.000');
    expect(rows[2].textContent).toContain('180.000');
    expect(root.querySelectorAll('[aria-label^="Editar "]')).toHaveLength(3);
  });

  it('abre el modo edición con el valor entero de la tarifa', () => {
    const root = fixture.nativeElement as HTMLElement;
    root.querySelector<HTMLButtonElement>('[aria-label="Editar MOTO"]')!.click();
    fixture.detectChanges();

    expect(fixture.componentInstance.editing()).toBe('MOTO');
    const input = root.querySelector<HTMLInputElement>('#valor')!;
    expect(input.value).toBe('80000');
    expect(root.querySelector('#form-title')?.textContent).toContain('MOTO');
  });

  it('bloquea el guardado mientras la petición PUT está en curso', () => {
    const component = fixture.componentInstance;
    const root = fixture.nativeElement as HTMLElement;
    component.editar('MOTO', tarifas[2]);
    fixture.detectChanges();
    component.form.controls.valor.setValue('95000');
    component.guardar();

    const request = http.expectOne({ method: 'PUT', url: '/tarifas/MOTO' });
    expect(request.request.body).toEqual({ valor: '95000' });
    expect(component.saving()).toBe(true);

    fixture.detectChanges();
    const submit = root.querySelector<HTMLButtonElement>('button[type="submit"]')!;
    expect(submit.disabled).toBe(true);
    expect(submit.textContent).toContain('Guardando');

    component.guardar();
    http.expectNone({ method: 'PUT', url: '/tarifas/MOTO' });

    request.flush({ ...tarifas[2], valor: '95000.00' });
    fixture.detectChanges();

    expect(component.saving()).toBe(false);
    expect(component.editing()).toBeNull();
    expect(component.success()).toContain('actualizada');
    expect(root.textContent).toContain('95.000');
  });

  it('rechaza valores con decimales y limpia caracteres no numéricos', () => {
    const component = fixture.componentInstance;
    const root = fixture.nativeElement as HTMLElement;
    component.editar('AUTOMOVIL', tarifas[0]);
    fixture.detectChanges();

    component.form.controls.valor.setValue('150000.50');
    component.guardar();
    expect(component.form.controls.valor.hasError('entero')).toBe(true);
    expect(component.actionError()).toContain('entero');
    http.expectNone((request) => request.method === 'PUT');

    const input = root.querySelector<HTMLInputElement>('#valor')!;
    input.value = '15a0b000';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    expect(component.form.controls.valor.value).toBe('150000');
  });

  it('muestra "Sin tarifa" cuando un tipo no tiene valor vigente', () => {
    const component = fixture.componentInstance;
    component.items.set(tarifas.filter((tarifa) => tarifa.tipo !== 'CAMIONETA'));
    fixture.detectChanges();

    const root = fixture.nativeElement as HTMLElement;
    const rows = [...root.querySelectorAll<HTMLTableRowElement>('tbody tr')];
    expect(rows[2].textContent).toContain('Sin tarifa');
  });
});
