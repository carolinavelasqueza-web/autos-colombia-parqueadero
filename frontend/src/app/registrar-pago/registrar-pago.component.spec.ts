import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Cliente } from '../models/cliente';
import { Pago } from '../models/pago';
import { RegistrarPago, VehiculoPago } from './registrar-pago';

describe('Registro de pago', () => {
  let fixture: ComponentFixture<RegistrarPago>;
  let component: RegistrarPago;
  let http: HttpTestingController;

  const cliente: Cliente = {
    id: 7,
    documento: '123456',
    nombre: 'Cliente Prueba',
    telefono: '3001234567',
    correo: 'cliente@example.com',
    activo: true,
  };

  // Un solo vehículo (automóvil) con tarifa 100000. Útil para las pruebas de
  // referencia, cambio y recibo que no dependen de varios vehículos.
  function unVehiculo(tarifa = 100000): VehiculoPago[] {
    return [{ id: 1, placa: 'ABC123', tipo: 'AUTOMOVIL', tarifa, seleccionado: true }];
  }

  const pago: Pago = {
    id: 42,
    numero_recibo: 'RC-000042',
    cliente: {
      id: 7,
      documento: '123456',
      nombre: 'Cliente Prueba',
      telefono: '3001234567',
      correo: 'cliente@example.com',
      activo: true,
      fecha_vencimiento: '2027-01-18',
    },
    detalles: [],
    meses: 1,
    metodo: 'TRANSFERENCIA',
    referencia: 'ABC-1',
    monto: '100000.00',
    estado: 'VIGENTE',
    periodo_desde: '2026-11-18',
    periodo_hasta: '2026-12-18',
    vencimiento_anterior: '2026-11-18',
    reactivo_cliente: false,
    operador_id: 1,
    fecha: '2026-11-18T15:30:00Z',
    motivo: null,
    anulado_por: null,
    anulado_en: null,
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RegistrarPago],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(RegistrarPago);
    component = fixture.componentInstance;
  });

  afterEach(() => http.verify());

  it('oculta la referencia para efectivo y la exige para otros métodos', () => {
    component.cliente.set(cliente);
    component.vehiculos.set(unVehiculo());
    component.paso.set(2);
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;

    const efectivo = root.querySelector<HTMLInputElement>('#referencia')!;
    expect(component.metodo()).toBe('EFECTIVO');
    expect(efectivo.disabled).toBe(true);
    expect(efectivo.required).toBe(false);

    component.cambiarMetodo('TARJETA');
    fixture.detectChanges();
    const tarjeta = root.querySelector<HTMLInputElement>('#referencia')!;
    expect(tarjeta.disabled).toBe(false);
    expect(tarjeta.required).toBe(true);

    component.cambiarMetodo('EFECTIVO');
    fixture.detectChanges();
    expect(root.querySelector<HTMLInputElement>('#referencia')!.disabled).toBe(true);
  });

  it('convierte la referencia a mayúsculas y la recorta al continuar', () => {
    component.cliente.set(cliente);
    component.vehiculos.set(unVehiculo());
    component.cambiarMetodo('TRANSFERENCIA');
    component.paso.set(2);
    component.referencia.set('  abc-9  ');

    component.continuar();

    expect(component.referencia()).toBe('ABC-9');
    expect(component.paso()).toBe(3);
  });

  it('calcula el total sumando la tarifa de cada vehículo seleccionado por los meses', () => {
    // Cliente con 2 automóviles (250) y 1 moto (100): el bug anterior sumaba por
    // tipo (350); ahora debe sumar por vehículo individual (600) × meses.
    component.cliente.set(cliente);
    component.vehiculos.set([
      { id: 1, placa: 'AAA111', tipo: 'AUTOMOVIL', tarifa: 250, seleccionado: true },
      { id: 2, placa: 'BBB222', tipo: 'AUTOMOVIL', tarifa: 250, seleccionado: true },
      { id: 3, placa: 'CCC333', tipo: 'MOTO', tarifa: 100, seleccionado: true },
    ]);
    component.cambiarMeses(3);
    component.paso.set(2);
    fixture.detectChanges();

    expect(component.tarifaMensualSeleccionada()).toBe(600);
    expect(component.total()).toBe(1800);

    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelectorAll('.vehiculo-item')).toHaveLength(3);
    expect(root.querySelector('.total-amount')?.textContent).toContain('1.800');
  });

  it('recalcula el total y exige al menos un vehículo al desmarcar', () => {
    component.cliente.set(cliente);
    component.vehiculos.set([
      { id: 1, placa: 'AAA111', tipo: 'AUTOMOVIL', tarifa: 250, seleccionado: true },
      { id: 2, placa: 'BBB222', tipo: 'MOTO', tarifa: 100, seleccionado: true },
    ]);
    component.cambiarMeses(1);
    component.paso.set(2);
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;

    expect(component.total()).toBe(350);

    // Desmarcar la moto deja solo el automóvil.
    const moto = root.querySelectorAll<HTMLInputElement>('.vehiculo-item input')[1];
    moto.checked = false;
    moto.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    expect(component.total()).toBe(250);
    expect(component.seleccionados().map((v) => v.id)).toEqual([1]);

    // Desmarcar el último deshabilita Continuar y bloquea el avance.
    const auto = root.querySelectorAll<HTMLInputElement>('.vehiculo-item input')[0];
    auto.checked = false;
    auto.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    expect(component.haySeleccion()).toBe(false);
    expect(root.querySelector<HTMLButtonElement>('button.primary')!.disabled).toBe(true);
    component.continuar();
    expect(component.paso()).toBe(2);
    expect(component.error()).toContain('al menos un vehículo');
  });

  it('calcula el cambio en efectivo y bloquea confirmar si el monto recibido es menor al total', () => {
    component.cliente.set(cliente);
    component.vehiculos.set(unVehiculo());
    component.paso.set(3);
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;

    const campo = root.querySelector<HTMLInputElement>('#monto-recibido')!;
    expect(campo).not.toBeNull();

    // Monto insuficiente: no se puede confirmar.
    campo.value = '80000';
    campo.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect(component.efectivoSuficiente()).toBe(false);
    expect(component.puedeConfirmar()).toBe(false);
    expect(root.querySelector<HTMLButtonElement>('#confirmar')!.disabled).toBe(true);
    expect(root.querySelector('#cambio')).toBeNull();

    // Monto suficiente: calcula el cambio y habilita confirmar.
    campo.value = '150000';
    campo.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect(component.cambio()).toBe(50000);
    expect(root.querySelector('#cambio')!.textContent).toContain('50.000');
    expect(component.puedeConfirmar()).toBe(true);
    expect(root.querySelector<HTMLButtonElement>('#confirmar')!.disabled).toBe(false);
  });

  it('no pide monto recibido cuando el método no es efectivo', () => {
    component.cliente.set(cliente);
    component.vehiculos.set(unVehiculo());
    component.cambiarMetodo('TRANSFERENCIA');
    component.referencia.set('ABC-1');
    component.paso.set(3);
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;

    expect(root.querySelector('#monto-recibido')).toBeNull();
    expect(component.cambio()).toBeNull();
    expect(component.puedeConfirmar()).toBe(true);
  });

  it('muestra el recibo imprimible con efectivo recibido y cambio, y permite imprimir', () => {
    const imprimir = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    component.cliente.set(cliente);
    component.vehiculos.set(unVehiculo());
    component.paso.set(3);
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;

    const campo = root.querySelector<HTMLInputElement>('#monto-recibido')!;
    campo.value = '150000';
    campo.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    root.querySelector<HTMLButtonElement>('#confirmar')!.click();
    const request = http.expectOne({ method: 'POST', url: '/pagos' });
    expect(request.request.body).toEqual({
      documento: '123456',
      meses: 1,
      metodo: 'EFECTIVO',
      referencia: null,
      vehiculo_ids: [1],
    });
    request.flush({ ...pago, metodo: 'EFECTIVO', referencia: null, monto: '100000.00' });
    fixture.detectChanges();

    expect(component.cambioPago()).toBe(50000);
    const ticket = root.querySelector('#recibo-impreso')!;
    expect(ticket.textContent).toContain('RC-000042');
    expect(ticket.textContent).toContain('Cliente Prueba');
    expect(ticket.textContent).toContain('100.000');
    expect(ticket.textContent).toContain('50.000');

    root.querySelector<HTMLButtonElement>('#imprimir-recibo')!.click();
    expect(imprimir).toHaveBeenCalledOnce();
    imprimir.mockRestore();
  });

  it('deshabilita el botón de confirmación y muestra Procesando al confirmar', () => {
    component.cliente.set(cliente);
    component.vehiculos.set(unVehiculo());
    component.cambiarMetodo('TRANSFERENCIA');
    component.referencia.set('abc-1');
    component.paso.set(3);
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;

    const boton = root.querySelector<HTMLButtonElement>('#confirmar')!;
    expect(boton.disabled).toBe(false);
    expect(boton.textContent).toContain('Confirmar Pago');

    boton.click();
    fixture.detectChanges();

    const procesando = root.querySelector<HTMLButtonElement>('#confirmar')!;
    expect(component.confirmando()).toBe(true);
    expect(procesando.disabled).toBe(true);
    expect(procesando.textContent).toContain('Procesando...');

    const request = http.expectOne({ method: 'POST', url: '/pagos' });
    expect(request.request.body).toEqual({
      documento: '123456',
      meses: 1,
      metodo: 'TRANSFERENCIA',
      referencia: 'ABC-1',
      vehiculo_ids: [1],
    });

    component.confirmar();
    http.expectNone({ method: 'POST', url: '/pagos' });

    request.flush(pago);
    fixture.detectChanges();

    expect(component.confirmando()).toBe(false);
    expect(component.resultado()?.numero_recibo).toBe('RC-000042');
    expect(root.textContent).toContain('RC-000042');
  });

  it('arma la lista individual de vehículos del cliente con su tarifa', () => {
    component.documento.set('123456');
    component.buscar();

    http.expectOne('/clientes?offset=0&limit=100').flush({
      items: [cliente],
      total: 1,
      offset: 0,
      limit: 100,
    });
    http.expectOne('/vehiculos?offset=0&limit=100').flush({
      items: [
        {
          id: 1,
          placa: 'BBB222',
          marca: 'M',
          color: 'Azul',
          modelo: 2026,
          tipo: 'AUTOMOVIL',
          cliente_id: 7,
          cliente,
        },
        {
          id: 2,
          placa: 'AAA111',
          marca: 'M',
          color: 'Rojo',
          modelo: 2026,
          tipo: 'AUTOMOVIL',
          cliente_id: 7,
          cliente,
        },
        {
          id: 3,
          placa: 'CCC333',
          marca: 'M',
          color: 'Gris',
          modelo: 2026,
          tipo: 'MOTO',
          cliente_id: 7,
          cliente,
        },
        // Vehículo de otro cliente: no debe aparecer.
        {
          id: 9,
          placa: 'ZZZ999',
          marca: 'M',
          color: 'Negro',
          modelo: 2026,
          tipo: 'MOTO',
          cliente_id: 99,
          cliente: null,
        },
      ],
      total: 4,
      offset: 0,
      limit: 100,
    });
    http.expectOne('/tarifas').flush([
      { tipo: 'AUTOMOVIL', valor: '250.00', vigente_desde: '2026-01-01T00:00:00Z' },
      { tipo: 'MOTO', valor: '100.00', vigente_desde: '2026-01-01T00:00:00Z' },
      { tipo: 'CAMIONETA', valor: '300.00', vigente_desde: '2026-01-01T00:00:00Z' },
    ]);
    fixture.detectChanges();

    expect(component.paso()).toBe(2);
    // Solo los 3 del cliente, ordenados por placa, cada uno con su tarifa.
    expect(component.vehiculos().map((v) => v.placa)).toEqual(['AAA111', 'BBB222', 'CCC333']);
    expect(component.vehiculos().map((v) => v.tarifa)).toEqual([250, 250, 100]);
    expect(component.vehiculos().every((v) => v.seleccionado)).toBe(true);
    // Total por vehículo individual: 250 + 250 + 100 = 600 (no 350 por tipo).
    expect(component.total()).toBe(600);
  });
});
