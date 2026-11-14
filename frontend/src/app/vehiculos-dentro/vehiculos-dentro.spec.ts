import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { EstanciaActiva, EstanciasActivasPagina } from '../models/estancia';
import { VehiculosDentro } from './vehiculos-dentro';

function activa(placa = 'ABC123'): EstanciaActiva {
  return {
    id: 1,
    vehiculo: {
      id: 1,
      placa,
      color: 'Azul',
      modelo: 2026,
      marca: 'Marca',
      tipo: 'AUTOMOVIL',
      cliente_id: 5,
      cliente: {
        id: 5,
        documento: '123',
        nombre: 'Cliente Uno',
        telefono: '3001234567',
        correo: 'cliente@example.com',
        activo: true,
      },
    },
    celda: { id: 1, codigo: 'C-01', tipo: 'AUTOMOVIL', activo: true },
    entrada: '2026-01-01T12:00:00Z',
    ficho_codigo: 'AC-20260101-0001',
    permanencia_minutos: 90,
  };
}

function pagina(
  items: EstanciaActiva[] = [],
  total = items.length,
  offset = 0,
): EstanciasActivasPagina {
  return { items, total, offset, limit: 20 };
}

describe('Vehículos dentro', () => {
  let fixture: ComponentFixture<VehiculosDentro>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [VehiculosDentro],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(VehiculosDentro);
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function root(): HTMLElement {
    return fixture.nativeElement as HTMLElement;
  }

  function inicial(): void {
    http.expectOne('/estancias/activas?offset=0&limit=20').flush(pagina([activa()], 1));
    fixture.detectChanges();
  }

  it('lista los vehículos con celda, ficho y permanencia', () => {
    inicial();
    const filas = root().querySelectorAll('tbody tr');
    expect(filas.length).toBe(1);
    const texto = filas[0].textContent ?? '';
    expect(texto).toContain('ABC123');
    expect(texto).toContain('C-01');
    expect(texto).toContain('AC-20260101-0001');
    expect(texto).toContain('1 h 30 min');
    expect(texto).toContain('Cliente Uno');
    expect(root().querySelector('.count')?.textContent).toContain('1');
  });

  it('muestra un estado vacío cuando no hay vehículos dentro', () => {
    http.expectOne('/estancias/activas?offset=0&limit=20').flush(pagina());
    fixture.detectChanges();
    expect(root().textContent).toContain('No hay vehículos dentro');
  });

  it('informa el error cuando la consulta falla', () => {
    http
      .expectOne('/estancias/activas?offset=0&limit=20')
      .flush({ detail: 'Error' }, { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();
    expect(root().querySelector('[role="alert"]')?.textContent).toContain(
      'No se pudieron cargar los vehículos',
    );
  });

  it('busca por placa después del retardo de escritura', async () => {
    http.expectOne('/estancias/activas?offset=0&limit=20').flush(pagina());
    fixture.detectChanges();

    const input = root().querySelector<HTMLInputElement>('#busqueda')!;
    input.value = ' abc ';
    input.dispatchEvent(new Event('input'));

    await new Promise((resolve) => setTimeout(resolve, 350));

    const busqueda = http.expectOne('/estancias/activas?placa=ABC&offset=0&limit=20');
    busqueda.flush(pagina([activa()], 1));
    fixture.detectChanges();
    expect(root().querySelector('tbody')?.textContent).toContain('ABC123');
  });

  it('pagina los resultados y deshabilita los extremos', () => {
    http.expectOne('/estancias/activas?offset=0&limit=20').flush(pagina([activa()], 45));
    fixture.detectChanges();

    const botones = [...root().querySelectorAll<HTMLButtonElement>('.pagination button')];
    const anterior = botones.find((boton) => boton.textContent?.includes('Anterior'))!;
    const siguiente = botones.find((boton) => boton.textContent?.includes('Siguiente'))!;
    expect(anterior.disabled).toBe(true);
    expect(siguiente.disabled).toBe(false);

    siguiente.click();
    http.expectOne('/estancias/activas?offset=20&limit=20').flush(pagina([activa()], 45, 20));
    fixture.detectChanges();

    expect(root().textContent).toContain('Página 2 de 3');
    expect(
      [...root().querySelectorAll<HTMLButtonElement>('.pagination button')].find((boton) =>
        boton.textContent?.includes('Anterior'),
      )?.disabled,
    ).toBe(false);
  });
});
