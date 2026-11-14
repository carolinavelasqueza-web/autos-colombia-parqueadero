import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ReasignacionModal } from './reasignacion-modal';

describe('ReasignacionModal', () => {
  let component: ReasignacionModal;
  let fixture: ComponentFixture<ReasignacionModal>;
  let http: HttpTestingController;

  const celda = { id: 5, codigo: 'M-01', tipo: 'MOTO', activo: true };
  const estancia = {
    id: 3,
    vehiculo_id: 1,
    celda_id: 5,
    entrada: '2026-10-19T15:00:00Z',
    salida: null,
    operador_entrada_id: 4,
    operador_salida_id: null,
    ficho_codigo: 'AC-20261019-0001',
    ficho_usado_en: null,
    puerta_entrada_id: 1,
    puerta_salida_id: null,
    celda,
    puerta_entrada: { id: 1, codigo: 'NORTE', ubicacion: 'Entrada Norte', activo: true },
  };
  const celdas = [{ id: 7, codigo: 'M-03', tipo: 'MOTO', disponible: true }];

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ReasignacionModal],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(ReasignacionModal);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('estancia', estancia);
    fixture.componentRef.setInput('placa', 'TEST-A');
    fixture.componentRef.setInput('celdas', celdas);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  it('muestra la celda actual y las opciones compatibles', () => {
    const text = (fixture.nativeElement as HTMLElement).textContent;
    expect(text).toContain('M-01');
    expect(text).toContain('TEST-A');
    expect(text).toContain('M-03');
  });

  it('exige elegir una celda de destino', () => {
    component.guardar();
    http.expectNone('/estancias/3/reasignar');
    expect(component.form.controls.celda_nueva_id.invalid).toBe(true);
  });

  it('envía la reasignación con motivo recortado y emite el resultado', () => {
    const emitida: unknown[] = [];
    component.reasignada.subscribe((result) => emitida.push(result));
    component.form.setValue({ celda_nueva_id: 7, motivo: '  Cambio operativo  ' });
    component.guardar();
    const req = http.expectOne('/estancias/3/reasignar');
    expect(req.request.body).toEqual({ celda_nueva_id: 7, motivo: 'Cambio operativo' });
    const nueva = { id: 7, codigo: 'M-03', tipo: 'MOTO', activo: true };
    const result = {
      id: 11,
      estancia_id: 3,
      celda_anterior: celda,
      celda_nueva: nueva,
      operador_id: 4,
      fecha: '2026-10-19T17:00:00Z',
      motivo: 'Cambio operativo',
      estancia: { ...estancia, celda_id: 7, celda: nueva },
    };
    req.flush(result);
    expect(emitida).toEqual([result]);
    expect(component.saving()).toBe(false);
  });

  it('presenta el error del backend sin cerrar el modal', () => {
    let cerrado = false;
    component.cerrar.subscribe(() => (cerrado = true));
    component.form.setValue({ celda_nueva_id: 7, motivo: '' });
    component.guardar();
    http
      .expectOne('/estancias/3/reasignar')
      .flush({ detail: 'La celda está ocupada.' }, { status: 409, statusText: 'Conflict' });
    expect(component.error()).toBe('La celda está ocupada.');
    expect(component.saving()).toBe(false);
    expect(cerrado).toBe(false);
  });
});
