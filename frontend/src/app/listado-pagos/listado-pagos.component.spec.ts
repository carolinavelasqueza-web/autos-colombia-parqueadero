import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal, WritableSignal } from '@angular/core';
import { Pago } from '../models/pago';
import { AuthService } from '../services/auth.service';
import { ListadoPagos } from './listado-pagos';

describe('Listado de pagos', () => {
  let fixture: ComponentFixture<ListadoPagos>;
  let component: ListadoPagos;
  let http: HttpTestingController;
  let esAdmin: WritableSignal<boolean>;

  const pagoVigente: Pago = {
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
    detalles: [
      {
        id: 1,
        vehiculo_id: 3,
        placa: 'ABC123',
        tipo: 'AUTOMOVIL',
        tarifa_aplicada: '150000.00',
        subtotal: '150000.00',
      },
    ],
    meses: 1,
    metodo: 'TRANSFERENCIA',
    referencia: 'ABC-1',
    monto: '150000.00',
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

  const pagoAnulado: Pago = {
    ...pagoVigente,
    id: 41,
    numero_recibo: 'RC-000041',
    meses: 2,
    metodo: 'EFECTIVO',
    referencia: null,
    monto: '300000.00',
    estado: 'ANULADO',
    motivo: 'Error de digitación',
    anulado_por: 1,
    anulado_en: '2026-11-18T16:00:00Z',
    detalles: [
      {
        id: 2,
        vehiculo_id: 3,
        placa: 'ABC123',
        tipo: 'AUTOMOVIL',
        tarifa_aplicada: '150000.00',
        subtotal: '300000.00',
      },
    ],
  };

  const pagina = {
    items: [pagoVigente, pagoAnulado],
    total: 2,
    offset: 0,
    limit: 20,
  };

  beforeEach(async () => {
    esAdmin = signal(true);
    await TestBed.configureTestingModule({
      imports: [ListadoPagos],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: { esAdministrador: esAdmin } },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(ListadoPagos);
    component = fixture.componentInstance;
    fixture.detectChanges();
    http.expectOne('/pagos?offset=0&limit=20').flush(pagina);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  it('renderiza la tabla con fecha, documento, recibo, meses, total, método y estado', () => {
    const root = fixture.nativeElement as HTMLElement;
    const rows = [...root.querySelectorAll<HTMLTableRowElement>('tbody tr')];

    expect(component.total()).toBe(2);
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain('123456');
    expect(rows[0].textContent).toContain('RC-000042');
    expect(rows[0].textContent).toContain('150.000');
    expect(rows[0].textContent).toContain('TRANSFERENCIA');
    expect(rows[0].textContent).toContain('VIGENTE');
    expect(rows[1].textContent).toContain('RC-000041');
    expect(rows[1].textContent).toContain('ANULADO');
  });

  it('solo ofrece Ver Recibo para los pagos vigentes', () => {
    const root = fixture.nativeElement as HTMLElement;
    const botones = [...root.querySelectorAll<HTMLButtonElement>('tbody button')];

    expect(botones).toHaveLength(1);
    expect(botones[0].textContent).toContain('Ver Recibo');
    expect(botones[0].getAttribute('aria-label')).toContain('RC-000042');
  });

  it('aplica los filtros de documento, estado y fechas', () => {
    const root = fixture.nativeElement as HTMLElement;
    const documento = root.querySelector<HTMLInputElement>('#filtro-documento')!;
    documento.value = '123456';
    documento.dispatchEvent(new Event('input'));

    const estado = root.querySelector<HTMLSelectElement>('#filtro-estado')!;
    estado.value = 'VIGENTE';
    estado.dispatchEvent(new Event('change'));

    const desde = root.querySelector<HTMLInputElement>('#filtro-desde')!;
    desde.value = '2026-11-01';
    desde.dispatchEvent(new Event('input'));

    const hasta = root.querySelector<HTMLInputElement>('#filtro-hasta')!;
    hasta.value = '2026-11-30';
    hasta.dispatchEvent(new Event('input'));

    root.querySelector<HTMLButtonElement>('button.primary')!.click();

    http
      .expectOne(
        '/pagos?offset=0&limit=20&documento=123456&estado=VIGENTE&desde=2026-11-01&hasta=2026-11-30',
      )
      .flush({ items: [pagoVigente], total: 1, offset: 0, limit: 20 });
    fixture.detectChanges();

    expect(component.items()).toEqual([pagoVigente]);
    expect(component.total()).toBe(1);
    expect(root.textContent).not.toContain('RC-000041');
  });

  it('muestra Anular Pago únicamente para el rol administrador', () => {
    component.verRecibo(pagoVigente);
    http.expectOne('/pagos/42/recibo').flush(pagoVigente);
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;

    expect(root.querySelector('#anular-pago')).not.toBeNull();

    esAdmin.set(false);
    fixture.detectChanges();

    expect(root.querySelector('#anular-pago')).toBeNull();
  });

  it('ofrece Imprimir Recibo en el modal y usa window.print sobre la tirilla', () => {
    const imprimir = vi.spyOn(window, 'print').mockImplementation(() => undefined);
    component.verRecibo(pagoVigente);
    http.expectOne('/pagos/42/recibo').flush(pagoVigente);
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;

    // El ticket lleva la clase de impresión y el botón está fuera de ella (no-print).
    const ticket = root.querySelector('.ticket')!;
    expect(ticket.classList).toContain('recibo-print');

    const boton = root.querySelector<HTMLButtonElement>('#imprimir-recibo')!;
    expect(boton).not.toBeNull();
    expect(boton.closest('.no-print')).not.toBeNull();

    boton.click();
    expect(imprimir).toHaveBeenCalledOnce();
    imprimir.mockRestore();
  });

  it('solicita motivo, bloquea el botón y anula sin duplicar la petición', () => {
    component.verRecibo(pagoVigente);
    http.expectOne('/pagos/42/recibo').flush(pagoVigente);
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;

    root.querySelector<HTMLButtonElement>('#anular-pago')!.click();
    fixture.detectChanges();

    const motivo = root.querySelector<HTMLTextAreaElement>('#motivo-anulacion')!;
    motivo.value = 'Error de digitación';
    motivo.dispatchEvent(new Event('input'));

    root.querySelector<HTMLButtonElement>('#confirmar-anulacion')!.click();
    fixture.detectChanges();

    const confirmar = root.querySelector<HTMLButtonElement>('#confirmar-anulacion')!;
    expect(component.anulando()).toBe(true);
    expect(confirmar.disabled).toBe(true);
    expect(confirmar.textContent).toContain('Anulando');

    const request = http.expectOne({ method: 'POST', url: '/pagos/42/anular' });
    expect(request.request.body).toEqual({ motivo: 'Error de digitación' });

    component.anular();
    http.expectNone({ method: 'POST', url: '/pagos/42/anular' });

    request.flush({ ...pagoVigente, estado: 'ANULADO', motivo: 'Error de digitación' });
    http.expectOne('/pagos?offset=0&limit=20').flush(pagina);
    fixture.detectChanges();

    expect(component.anulando()).toBe(false);
    expect(component.success()).toContain('anulado');
  });
});
