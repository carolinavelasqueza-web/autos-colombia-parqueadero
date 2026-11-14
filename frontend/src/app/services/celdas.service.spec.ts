import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { CeldasService } from './celdas.service';

describe('CeldasService', () => {
  let service: CeldasService;
  let http: HttpTestingController;
  const page = {
    items: [{ id: 1, codigo: 'A-01', tipo: 'Libre', activo: true }],
    total: 1,
    offset: 0,
    limit: 10,
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(CeldasService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('no envía incluir_inactivas por defecto', () => {
    service.list(0, 10).subscribe((data) => expect(data).toEqual(page));
    http.expectOne('/celdas?offset=0&limit=10').flush(page);
  });

  it('envía incluir_inactivas=true cuando se solicita', () => {
    service.list(0, 10, true).subscribe((data) => expect(data).toEqual(page));
    http.expectOne('/celdas?offset=0&limit=10&incluir_inactivas=true').flush(page);
  });

  it('reactiva mediante PATCH con solo el estado', () => {
    service.update(1, { activo: true }).subscribe();
    const request = http.expectOne({ method: 'PATCH', url: '/celdas/1' });
    expect(request.request.body).toEqual({ activo: true });
    request.flush({ ...page.items[0], activo: true });
  });
});
