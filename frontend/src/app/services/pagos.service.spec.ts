import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import {
  ClientesMensualidadPagina,
  Pago,
  PagosPagina,
  ReporteRecaudo,
} from '../models/pago';
import { PagosService } from './pagos.service';

describe('PagosService', () => {
  let service: PagosService;
  let http: HttpTestingController;
  const pago: Pago = {
    id: 10,
    numero_recibo: 'RC-000042',
    cliente: {
      id: 1,
      documento: '123456',
      nombre: 'Cliente Prueba',
      telefono: '001',
      correo: 'cliente@example.com',
      activo: true,
      fecha_vencimiento: '2027-01-18',
    },
    detalles: [
      {
        id: 1,
        vehiculo_id: 1,
        placa: 'ABC123',
        tipo: 'MOTO',
        tarifa_aplicada: '10000.00',
        subtotal: '30000.00',
      },
    ],
    meses: 3,
    metodo: 'TRANSFERENCIA',
    referencia: 'ABC-1',
    monto: '30000.00',
    estado: 'VIGENTE',
    periodo_desde: '2026-11-18',
    periodo_hasta: '2027-01-18',
    vencimiento_anterior: null,
    reactivo_cliente: false,
    operador_id: 1,
    fecha: '2026-11-18T15:30:00Z',
    motivo: null,
    anulado_por: null,
    anulado_en: null,
  };
  const pagina: PagosPagina = {
    items: [pago],
    total: 1,
    offset: 0,
    limit: 20,
  };
  const cliente = pago.cliente;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(PagosService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('registra un pago', () => {
    const data = {
      documento: '123456',
      meses: 3,
      metodo: 'TRANSFERENCIA' as const,
      referencia: 'ABC-1',
    };
    service.registrar(data).subscribe((respuesta) => {
      expect(respuesta.monto).toBe('30000.00');
    });
    const request = http.expectOne({ method: 'POST', url: '/pagos' });
    expect(request.request.body).toEqual(data);
    request.flush(pago);
  });

  it('lista pagos con la paginación por defecto', () => {
    service.listar().subscribe((data) => expect(data).toEqual(pagina));
    http.expectOne('/pagos?offset=0&limit=20').flush(pagina);
  });

  it('lista pagos con todos los filtros', () => {
    service
      .listar({
        offset: 5,
        limit: 10,
        documento: '123456',
        estado: 'VIGENTE',
        desde: '2026-01-01',
        hasta: '2026-01-31',
      })
      .subscribe();
    http
      .expectOne(
        '/pagos?offset=5&limit=10&documento=123456&estado=VIGENTE&desde=2026-01-01&hasta=2026-01-31',
      )
      .flush(pagina);
  });

  it('obtiene el recibo de un pago', () => {
    service.recibo(10).subscribe((data) => {
      expect(data.numero_recibo).toBe('RC-000042');
    });
    http.expectOne('/pagos/10/recibo').flush(pago);
  });

  it('anula un pago con su motivo', () => {
    service.anular(10, { motivo: 'Error de digitación' }).subscribe();
    const request = http.expectOne({ method: 'POST', url: '/pagos/10/anular' });
    expect(request.request.body).toEqual({ motivo: 'Error de digitación' });
    request.flush({ ...pago, estado: 'ANULADO', motivo: 'Error de digitación' });
  });

  it('consulta la mensualidad de un cliente', () => {
    service.mensualidad(1).subscribe((data) => {
      expect(data.estado).toBe('POR_VENCER');
    });
    http.expectOne('/clientes/1/mensualidad').flush({
      cliente,
      estado: 'POR_VENCER',
    });
  });

  it('lista las alertas de mensualidad paginadas', () => {
    const alertas: ClientesMensualidadPagina = {
      items: [{ cliente, estado: 'POR_VENCER' }],
      total: 1,
      offset: 0,
      limit: 20,
    };
    service.alertas(0, 20).subscribe((data) => {
      expect(data.items[0].estado).toBe('POR_VENCER');
    });
    http
      .expectOne('/clientes/mensualidad/alertas?offset=0&limit=20')
      .flush(alertas);
  });

  it('consulta el recaudo sin rango de fechas', () => {
    const reporte: ReporteRecaudo = {
      desde: '2026-11-01',
      hasta: '2026-11-30',
      pagos: 2,
      total: '150000.00',
      por_metodo: [
        { metodo: 'EFECTIVO', pagos: 2, total: '150000.00' },
      ],
    };
    service.recaudo().subscribe((data) => {
      expect(data.total).toBe('150000.00');
    });
    http.expectOne('/reportes/recaudo').flush(reporte);
  });

  it('consulta el recaudo con rango de fechas', () => {
    service.recaudo('2026-01-01', '2026-01-31').subscribe();
    http
      .expectOne('/reportes/recaudo?desde=2026-01-01&hasta=2026-01-31')
      .flush({
        desde: '2026-01-01',
        hasta: '2026-01-31',
        pagos: 0,
        total: '0.00',
        por_metodo: [],
      });
  });
});
