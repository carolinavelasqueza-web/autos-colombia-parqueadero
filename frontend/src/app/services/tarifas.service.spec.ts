import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Tarifa } from '../models/tarifa';
import { TarifasService } from './tarifas.service';

describe('TarifasService', () => {
  let service: TarifasService;
  let http: HttpTestingController;
  const tarifa: Tarifa = {
    id: 1,
    tipo: 'AUTOMOVIL',
    valor: '150000.00',
    vigente_desde: '2026-11-01T05:00:00Z',
    vigente_hasta: null,
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(TarifasService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('lista las tarifas vigentes', () => {
    service.list().subscribe((data) => {
      expect(data).toEqual([tarifa]);
      expect(data[0].valor).toBe('150000.00');
    });
    http.expectOne({ method: 'GET', url: '/tarifas' }).flush([tarifa]);
  });

  it('actualiza una tarifa con el tipo en la ruta', () => {
    service.actualizar('MOTO', { valor: '80000.00' }).subscribe((data) => {
      expect(data.tipo).toBe('AUTOMOVIL');
    });
    const request = http.expectOne({ method: 'PUT', url: '/tarifas/MOTO' });
    expect(request.request.body).toEqual({ valor: '80000.00' });
    request.flush(tarifa);
  });
});
