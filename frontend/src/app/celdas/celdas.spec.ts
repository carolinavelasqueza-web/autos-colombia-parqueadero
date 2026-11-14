import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Celdas } from './celdas';

describe('Gestión de celdas', () => {
  let fixture: ComponentFixture<Celdas>;
  let http: HttpTestingController;
  const cell = { id: 1, codigo: 'A-01', tipo: 'Categoría libre', activo: true };
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Celdas],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Celdas);
    fixture.detectChanges();
    http
      .expectOne('/celdas?offset=0&limit=10')
      .flush({ items: [cell], total: 1, offset: 0, limit: 10 });
  });
  afterEach(() => http.verify());

  it('crea desde el formulario HTML con código normalizado y tipo libre', () => {
    fixture.componentInstance.newCell();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    for (const [id, value] of Object.entries({
      codigo: ' a-02 ',
      tipo: 'Categoría sin catálogo',
    })) {
      const input = root.querySelector<HTMLInputElement>(`#${id}`)!;
      input.value = value;
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }
    root
      .querySelector('form')!
      .dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    fixture.componentInstance.save();
    const request = http.expectOne({ method: 'POST', url: '/celdas' });
    expect(request.request.body).toEqual({ codigo: 'A-02', tipo: 'Categoría sin catálogo' });
    request.flush({ ...cell, codigo: 'A-02' });
    http
      .expectOne('/celdas?offset=0&limit=10')
      .flush({ items: [cell], total: 1, offset: 0, limit: 10 });
    expect(fixture.componentInstance.success()).toContain('registrada');
  });

  it('rechaza blancos y muestra duplicados junto al código', () => {
    const c = fixture.componentInstance;
    c.newCell();
    c.form.setValue({ codigo: ' ', tipo: ' ' });
    c.save();
    expect(c.form.invalid).toBe(true);
    c.form.setValue({ codigo: 'A-01', tipo: 'Libre' });
    c.save();
    http.expectOne('/celdas').flush({}, { status: 409, statusText: 'Conflict' });
    expect(c.fieldError('codigo')).toContain('Ya existe');
  });

  it('edita mediante PATCH y recarga la lista', () => {
    const c = fixture.componentInstance;
    c.edit(cell);
    http.expectOne('/celdas/1').flush(cell);
    c.form.controls.tipo.setValue('Nuevo tipo');
    c.save();
    const request = http.expectOne({ method: 'PATCH', url: '/celdas/1' });
    expect(request.request.body.id).toBeUndefined();
    request.flush({ ...cell, tipo: 'Nuevo tipo' });
    http
      .expectOne('/celdas?offset=0&limit=10')
      .flush({ items: [cell], total: 1, offset: 0, limit: 10 });
  });

  it('muestra un icono según el tipo de celda', () => {
    const c = fixture.componentInstance;
    c.items.set([
      { id: 1, codigo: 'C-01', tipo: 'AUTOMOVIL', activo: true },
      { id: 2, codigo: 'M-01', tipo: 'moto', activo: true },
      { id: 3, codigo: 'X-01', tipo: 'Libre', activo: true },
    ]);
    fixture.detectChanges();
    const tags = [...(fixture.nativeElement as HTMLElement).querySelectorAll('.type-tag')].map(
      (tag) => tag.textContent?.replace(/\s+/g, ' ').trim(),
    );
    expect(tags).toEqual(['🚗AUTOMOVIL', '🏍️moto', '🅿️Libre']);
  });

  it('requiere confirmación y permite cancelar antes de eliminar', () => {
    const c = fixture.componentInstance;
    c.confirmDelete(cell);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alertdialog"]').textContent).toContain(
      'A-01',
    );
    c.cancel();
    http.expectNone((request) => request.method === 'DELETE');
    c.confirmDelete(cell);
    c.remove();
    http
      .expectOne({ method: 'DELETE', url: '/celdas/1' })
      .flush(null, { status: 204, statusText: 'No Content' });
    http
      .expectOne('/celdas?offset=0&limit=10')
      .flush({ items: [], total: 0, offset: 0, limit: 10 });
    expect(c.success()).toContain('eliminada');
  });

  it('muestra el estado y solo ofrece reactivar en celdas inactivas', () => {
    const c = fixture.componentInstance;
    c.items.set([
      { ...cell, id: 1, codigo: 'A-01', activo: true },
      { ...cell, id: 2, codigo: 'A-02', activo: false },
    ]);
    fixture.detectChanges();
    const rows = [
      ...(fixture.nativeElement as HTMLElement).querySelectorAll<HTMLTableRowElement>(
        'tbody tr',
      ),
    ];
    expect(rows[0].textContent).toContain('Activa');
    expect(rows[1].textContent).toContain('Inactiva');
    expect(rows[0].querySelector('[aria-label="Reactivar A-01"]')).toBeNull();
    expect(rows[1].querySelector('[aria-label="Reactivar A-02"]')).not.toBeNull();
    expect(rows[0].querySelector('[aria-label="Eliminar A-01"]')).not.toBeNull();
    expect(rows[1].querySelector('[aria-label="Eliminar A-02"]')).not.toBeNull();
  });

  it('alterna Mostrar inactivas y recarga desde la primera página', () => {
    const c = fixture.componentInstance;
    c.load(10);
    http
      .expectOne('/celdas?offset=10&limit=10')
      .flush({ items: [cell], total: 11, offset: 10, limit: 10 });
    c.toggleInactivas();
    expect(c.mostrarInactivas()).toBe(true);
    http
      .expectOne('/celdas?offset=0&limit=10&incluir_inactivas=true')
      .flush({ items: [cell], total: 1, offset: 0, limit: 10 });
    expect(c.offset()).toBe(0);
    c.toggleInactivas();
    http
      .expectOne('/celdas?offset=0&limit=10')
      .flush({ items: [cell], total: 1, offset: 0, limit: 10 });
  });

  it('requiere confirmación y permite cancelar antes de reactivar', () => {
    const c = fixture.componentInstance;
    const inactive = { ...cell, activo: false };
    c.confirmReactivate(inactive);
    fixture.detectChanges();
    expect(
      (fixture.nativeElement as HTMLElement).querySelector('[role="alertdialog"]')!.textContent,
    ).toContain('A-01');
    c.cancel();
    http.expectNone((request) => request.method === 'PATCH');
    c.confirmReactivate(inactive);
    c.reactivate();
    const request = http.expectOne({ method: 'PATCH', url: '/celdas/1' });
    expect(request.request.body).toEqual({ activo: true });
    request.flush({ ...inactive, activo: true });
    http
      .expectOne('/celdas?offset=0&limit=10')
      .flush({ items: [cell], total: 1, offset: 0, limit: 10 });
    expect(c.success()).toContain('reactivada');
  });

  it('no reactiva una celda activa ni repite la solicitud', () => {
    const c = fixture.componentInstance;
    c.confirmReactivate(cell);
    expect(c.pendingReactivation()).toBeNull();
    c.confirmReactivate({ ...cell, activo: false });
    c.reactivate();
    http
      .expectOne({ method: 'PATCH', url: '/celdas/1' })
      .flush({ ...cell, activo: true });
    http
      .expectOne('/celdas?offset=0&limit=10')
      .flush({ items: [cell], total: 1, offset: 0, limit: 10 });
    c.reactivate();
    http.expectNone({ method: 'PATCH', url: '/celdas/1' });
  });

  it('informa 404 al reactivar y actualiza el listado', () => {
    const c = fixture.componentInstance;
    c.confirmReactivate({ ...cell, activo: false });
    c.reactivate();
    http
      .expectOne({ method: 'PATCH', url: '/celdas/1' })
      .flush({}, { status: 404, statusText: 'Not Found' });
    expect(c.actionError()).toContain('ya no existe');
    expect(c.pendingReactivation()).toBeNull();
    http
      .expectOne('/celdas?offset=0&limit=10')
      .flush({ items: [], total: 0, offset: 0, limit: 10 });
  });
});
