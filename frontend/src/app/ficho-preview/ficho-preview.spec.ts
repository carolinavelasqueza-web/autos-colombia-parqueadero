import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FichoPreview } from './ficho-preview';

describe('FichoPreview', () => {
  let component: FichoPreview;
  let fixture: ComponentFixture<FichoPreview>;

  const cliente = {
    id: 7,
    documento: '123456',
    nombre: 'Cliente Prueba',
    telefono: '001',
    correo: 'cliente@example.com',
    activo: true,
  };
  const ficho = {
    id: 3,
    ficho_codigo: 'AC-20261019-0001',
    entrada: '2026-10-19T15:00:00Z',
    salida: null,
    ficho_usado_en: null,
    vehiculo: {
      id: 1,
      placa: 'TEST-A',
      marca: 'Prueba',
      color: 'Azul',
      modelo: 2026,
      tipo: 'MOTO' as const,
      cliente_id: cliente.id,
      cliente,
    },
    celda: { id: 5, codigo: 'M-01', tipo: 'MOTO', activo: true },
    puerta_entrada: { id: 1, codigo: 'NORTE', ubicacion: 'Entrada Norte', activo: true },
    puerta_salida: null,
    operador_entrada_id: 4,
    operador_salida_id: null,
    cliente,
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FichoPreview],
    }).compileComponents();

    fixture = TestBed.createComponent(FichoPreview);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('ficho', ficho);
    fixture.detectChanges();
  });

  it('presenta el código, la celda y la puerta de entrada', () => {
    const text = (fixture.nativeElement as HTMLElement).textContent;
    expect(text).toContain('AC-20261019-0001');
    expect(text).toContain('M-01');
    expect(text).toContain('NORTE');
    expect(text).toContain('Cliente Prueba');
    expect(component.fecha('2026-10-19T15:00:00Z')).toContain('2026');
  });

  it('imprime el comprobante con window.print', () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('.print')!.click();
    expect(print).toHaveBeenCalled();
  });
});
